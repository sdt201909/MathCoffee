"""Model-free conditioning checks; these do not certify audible voice identity."""

import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from mathcoffee.speech.qwen_context import (
    _validate_runtime,
    configure_custom_voice_context,
    full_text_prefill,
)


class FakeTalker:
    def __init__(self):
        self.codec_lookups = []

    @staticmethod
    def text_projection(value):
        return value

    @staticmethod
    def get_text_embeddings():
        return lambda ids: np.stack([ids * 10, ids * 10 + 1], axis=-1).astype(np.float32)

    def get_input_embeddings(self):
        def embed(ids):
            self.codec_lookups.append(ids.tolist())
            return np.stack([ids, ids + 1], axis=-1).astype(np.float32)
        return embed


class FakeModel:
    def __init__(self):
        self.config = SimpleNamespace(
            tts_model_type="custom_voice",
            talker_config=SimpleNamespace(codec_pad_id=5, codec_bos_id=6),
        )
        self.tokenizer = SimpleNamespace(encode=lambda _: [90, 91, 92, 1, 2, 93, 94, 95, 96, 97])
        self.talker = FakeTalker()
        self.legacy_calls = []
        self.prefix = np.array([[[101, 102], [201, 202]]], dtype=np.float32)
        self.legacy_inputs = np.concatenate(
            [self.prefix, np.array([[[16, 18]]], dtype=np.float32)], axis=1,
        )
        self.trailing = np.array([[[20, 21], [30, 31]]], dtype=np.float32)
        self.pad = np.array([[[40, 41]]], dtype=np.float32)
        # Avoid importing MLX/starting Metal during fixture tests.
        self._mathcoffee_custom_voice_context = {
            "original": self._prepare_generation_inputs, "array_module": np,
        }

    def _prepare_generation_inputs(self, text, language="auto", speaker=None,
                                   ref_audio=None, ref_text=None, instruct=None):
        self.legacy_calls.append((text, language, speaker, ref_audio, ref_text, instruct))
        return self.legacy_inputs, self.trailing, self.pad


class QwenContextTests(unittest.TestCase):
    def setUp(self):
        self.runtime = patch("mathcoffee.speech.qwen_context._validate_runtime", return_value={
            "mlx_audio_version": "fixture", "upstream_source_sha256": "fixture",
        })
        self.runtime.start()
        self.addCleanup(self.runtime.stop)

    def test_official_layout_and_full_text_already_present_before_first_codec(self):
        model = FakeModel()
        receipt = configure_custom_voice_context(model, "full_text")
        inputs, trailing, pad = model._prepare_generation_inputs(
            "两句话。", language="Chinese", speaker="Serena", instruct="轻松讲述。",
        )
        # Official layout: unchanged prefix; both text tokens + codecPAD;
        # EOS + codecPAD; then ttsPAD + codecBOS. No text trails decoding.
        expected = np.array([[[101, 102], [201, 202], [15, 17], [25, 27],
                              [35, 37], [46, 48]]], dtype=np.float32)
        np.testing.assert_array_equal(inputs, expected)
        self.assertIs(trailing, model.pad)
        self.assertIs(pad, model.pad)
        self.assertEqual(model.legacy_calls, [
            ("两句话。", "Chinese", "Serena", None, None, "轻松讲述。"),
        ])
        self.assertEqual(model.talker.codec_lookups, [[[5, 6]]])
        self.assertTrue(receipt["full_text_prefill"])
        self.assertFalse(receipt["preset_speaker_changed"])

    def test_legacy_is_exact_original_and_switching_does_not_nest_wrappers(self):
        model = FakeModel()
        for _ in range(2):
            configure_custom_voice_context(model, "full_text")
        model._prepare_generation_inputs("甲。")
        self.assertEqual(len(model.legacy_calls), 1)
        receipt = configure_custom_voice_context(model, "legacy_streaming_text")
        values = model._prepare_generation_inputs("乙。")
        self.assertIs(values[0], model.legacy_inputs)
        self.assertIs(values[1], model.trailing)
        self.assertIs(values[2], model.pad)
        self.assertFalse(receipt["full_text_prefill"])

    def test_uncombined_text_is_used_even_when_legacy_sum_loses_precision(self):
        model = FakeModel()
        model.legacy_inputs[:, -1, :] = 1e9
        configure_custom_voice_context(model, "full_text")
        inputs, _, _ = model._prepare_generation_inputs("甲乙。")
        np.testing.assert_array_equal(inputs[:, 2:4], [[[15, 17], [25, 27]]])

    def test_reference_conditioning_empty_text_and_other_models_rejected(self):
        model = FakeModel()
        configure_custom_voice_context(model, "full_text")
        for kwargs in ({"ref_audio": np.zeros(4)}, {"ref_text": "参考"}):
            with self.assertRaises(ValueError):
                model._prepare_generation_inputs("正文", **kwargs)
        with self.assertRaises(ValueError):
            model._prepare_generation_inputs(" ")
        model.config.tts_model_type = "base"
        with self.assertRaises(ValueError):
            configure_custom_voice_context(model, "full_text")

    def test_unknown_mode_and_unverified_runtime_fail_before_patching(self):
        model = FakeModel()
        original = model._prepare_generation_inputs
        with self.assertRaises(ValueError):
            configure_custom_voice_context(model, "non_streaming_mode")
        with patch("mathcoffee.speech.qwen_context._validate_runtime", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                configure_custom_voice_context(model, "full_text")
        self.assertEqual(model._prepare_generation_inputs, original)

    def test_incompatible_array_contract_is_rejected(self):
        model = FakeModel()
        args = dict(prefix=model.prefix, text_embeddings=model.trailing[:, :1],
                    eos_embedding=model.trailing[:, -1:], text_pad=model.pad,
                    codec_pad=model.pad, codec_bos=model.pad, array_module=np)
        with self.assertRaises(ValueError):
            full_text_prefill(**{**args, "text_embeddings": np.zeros((1, 0, 2))})
        with self.assertRaises(ValueError):
            full_text_prefill(**{**args, "prefix": np.zeros((2, 3, 2))})
        with self.assertRaises(ValueError):
            full_text_prefill(**{**args, "codec_bos": np.zeros((1, 2, 2))})
        with self.assertRaises(ValueError):
            full_text_prefill(**{**args, "codec_pad": np.zeros((1, 1, 3))})


class RuntimeShapeModel:
    """Signature fixture; never imports MLX or loads a model."""

    def _prepare_generation_inputs(self, text, language, speaker, ref_audio,
                                   ref_text, instruct):
        pass

    def generate_custom_voice(self, text, speaker, language, instruct, temperature,
                              max_tokens, top_k, top_p, repetition_penalty, verbose,
                              stream, streaming_interval):
        pass


RuntimeShapeModel.__module__ = "mlx_audio.tts.models.qwen3_tts.qwen3_tts"


class RuntimeGuardTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "qwen3_tts.py"
        self.path.write_text("# reviewed fixture implementation\n")
        self.source_hash = hashlib.sha256(self.path.read_bytes()).hexdigest()
        for name, value in (
            ("importlib.metadata.version", "0.5.7"),
            ("inspect.getfile", str(self.path)),
        ):
            patcher = patch(f"mathcoffee.speech.qwen_context.{name}", return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch("mathcoffee.speech.qwen_context.UPSTREAM_SHA256", self.source_hash)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_exact_package_source_and_api_return_identity(self):
        result = _validate_runtime(RuntimeShapeModel())
        self.assertEqual(result["upstream_source_sha256"], self.source_hash)
        self.assertTrue(result["upstream_api_verified"])

    def test_modified_upstream_source_or_package_version_rejected(self):
        with patch(
            "mathcoffee.speech.qwen_context.importlib.metadata.version", return_value="0.5.8",
        ):
            with self.assertRaisesRegex(RuntimeError, "requires mlx-audio"):
                _validate_runtime(RuntimeShapeModel())
        self.path.write_text("# externally modified implementation\n")
        with self.assertRaisesRegex(RuntimeError, "source hash changed"):
            _validate_runtime(RuntimeShapeModel())

    def test_changed_signature_or_model_class_rejected(self):
        with patch.object(RuntimeShapeModel, "generate_custom_voice", lambda self, **kwargs: None):
            with self.assertRaisesRegex(RuntimeError, "API changed"):
                _validate_runtime(RuntimeShapeModel())
        with self.assertRaisesRegex(RuntimeError, "pinned MLX Qwen Model"):
            _validate_runtime(FakeModel())


if __name__ == "__main__":
    unittest.main()

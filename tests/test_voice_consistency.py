"""Provider/manifest regressions using a fake backend, never audible acceptance.

These tests exercise the real adapter and manifest writer without model weights,
Metal, network access, or speech claims. Identical waveform fixtures intentionally
ensure that same speaker/seed/signal never promotes listening review to passed.
Run with .venv-speech (the actual WAV writer requires its existing soundfile).
"""

import contextlib
import importlib.util
import io
import json
import tempfile
import types
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import numpy as np

from mathcoffee.speech.providers import QwenMLXProvider

ROOT = Path(__file__).resolve().parents[1]
PROFILE = {
    "speaker": "Serena", "language": "Chinese", "instruct": "自然、温柔地讲述。",
    "temperature": 0.7, "max_tokens": 1024, "top_k": 50, "top_p": 1.0,
    "repetition_penalty": 1.05, "stream": False, "streaming_interval": 2.0,
    "text_conditioning": "full_text",
}


class FakeCustomVoice:
    sample_rate = 24000
    tokenizer = object()
    speech_tokenizer = object()

    def __init__(self):
        self.calls = []

    @staticmethod
    def get_supported_speakers():
        return ["Serena"]

    @staticmethod
    def get_supported_languages():
        return ["auto", "Chinese"]

    def generate_custom_voice(self, text, speaker, language="auto", instruct=None,
                              temperature=0.9, max_tokens=4096, top_k=50, top_p=1.0,
                              repetition_penalty=1.05, verbose=False, stream=False,
                              streaming_interval=2.0):
        self.calls.append({
            "text": text, "speaker": speaker, "language": language, "instruct": instruct,
            "temperature": temperature, "max_tokens": max_tokens, "top_k": top_k,
            "top_p": top_p, "repetition_penalty": repetition_penalty,
            "verbose": verbose, "stream": stream, "streaming_interval": streaming_interval,
        })
        wave = (0.1 * np.sin(np.arange(4 * 1920) * 0.05)).astype(np.float32)
        yield types.SimpleNamespace(
            audio=wave, samples=len(wave), token_count=4, peak_memory_usage=0.0,
        )


def load_script(name):
    spec = importlib.util.spec_from_file_location(f"test_{name}", ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VoiceConsistencyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.model_dir = self.directory / "model"
        self.model_dir.mkdir()
        (self.model_dir / "config.json").write_text(json.dumps({
            "tts_model_type": "custom_voice", "tts_model_size": "1b7",
        }))
        self.backend = FakeCustomVoice()
        self.seeds = []
        mx = types.ModuleType("mlx.core")
        mx.random = types.SimpleNamespace(seed=self.seeds.append)
        mx.default_device = lambda: "fixture"
        mx.eval = lambda *args: None
        mx.get_peak_memory = lambda: 0
        mlx = types.ModuleType("mlx")
        mlx.core = mx
        audio = types.ModuleType("mlx_audio")
        tts = types.ModuleType("mlx_audio.tts")
        utils = types.ModuleType("mlx_audio.tts.utils")
        utils.load_model = lambda *args, **kwargs: self.backend
        self.source_hash = "reviewed-fixture-source"
        self.codec_source_hash = "reviewed-fixture-tokenizer"
        self.context_calls = []

        def context(model, mode):
            self.assertIs(model, self.backend)
            self.context_calls.append(mode)
            return {
                "effective_text_context": mode, "adapter_revision": "fixture-v1",
                "upstream_source_sha256": self.source_hash,
                "full_text_prefill": mode == "full_text",
            }

        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict("sys.modules", {
            "mlx": mlx, "mlx.core": mx, "mlx_audio": audio,
            "mlx_audio.tts": tts, "mlx_audio.tts.utils": utils,
        }))
        self.stack.enter_context(patch("mathcoffee.speech.providers.offline"))
        self.stack.enter_context(patch(
            "mathcoffee.speech.providers.local_model_manifest", return_value={
                "content_sha256": "same-fixture-checkpoint", "files": [],
            },
        ))
        self.stack.enter_context(patch(
            "mathcoffee.speech.providers.pinned_model_source", return_value={
                "status": "matched_pinned_source", "repo": "fixture/CustomVoice",
                "revision": "fixture-revision",
            },
        ))
        self.stack.enter_context(patch(
            "mathcoffee.speech.providers.runtime_versions", return_value={"mlx-audio": "fixture"},
        ))
        self.stack.enter_context(patch(
            "mathcoffee.speech.qwen_context.configure_custom_voice_context", side_effect=context,
        ))
        self.stack.enter_context(patch(
            "mathcoffee.speech.qwen_codec_length.configure_codec_length",
            side_effect=lambda *a, **kw: {
                "adapter_revision": "codec-fixture-v1", "samples_per_codec_frame": 1920,
                "tokenizer_source_sha256": self.codec_source_hash,
            },
        ))
        self.stack.enter_context(patch("mathcoffee.speech.qwen_codec_length.begin_codec_request"))
        self.stack.enter_context(patch(
            "mathcoffee.speech.qwen_codec_length.codec_request_records", return_value=[{
                "codec_frames": 4, "complete_decoder_samples": 7680, "valid_samples": 7680,
                "legacy_mask_samples": 7680, "valid_first_code_zero_frames": 0,
                "explicit_padding_frames": 0,
            }],
        ))

    def provider(self, profile=None):
        selected = deepcopy(PROFILE if profile is None else profile)
        return QwenMLXProvider(selected, [], {}, self.model_dir)

    def test_unsupported_library_and_typo_kwargs_never_reach_backend(self):
        for option in ("non_streaming_mode", "subtalker_temperature", "temprature", "seed"):
            with self.subTest(option=option):
                with self.assertRaisesRegex(ValueError, "unsupported"):
                    self.provider({**PROFILE, option: 1})
        self.assertEqual(self.backend.calls, [])

    def test_profile_cannot_override_authored_spoken_text(self):
        with self.assertRaisesRegex(ValueError, "text|reserved"):
            self.provider({**PROFILE, "text": "不能替换正文"})
        self.assertEqual(self.backend.calls, [])

    def test_caller_profile_mutation_cannot_change_effective_receipt_or_generation(self):
        requested = deepcopy(PROFILE)
        provider = QwenMLXProvider(requested, [], {}, self.model_dir)
        requested["speaker"] = "different_voice"
        requested["instruct"] = "different_instruction"
        requested["text_conditioning"] = "legacy_streaming_text"
        _, details = provider.synthesize({"spoken_text": "原来的正文。"}, 42)
        self.assertEqual(provider.metadata["parameters"]["speaker"], "Serena")
        self.assertEqual(provider.profile["text_conditioning"], "full_text")
        self.assertEqual(self.backend.calls[0]["speaker"], "Serena")
        self.assertEqual(details["speaker"], "Serena")
        self.assertEqual(details["instruct"], PROFILE["instruct"])

    def test_conditioning_routes_to_adapter_and_effective_metadata_not_generate_kwargs(self):
        provider = self.provider()
        waveform, details = provider.synthesize({"spoken_text": "同一个声音。"}, 42)
        self.assertEqual(len(waveform), 7680)
        self.assertEqual(self.context_calls, ["full_text"])
        self.assertEqual(self.seeds, [42])
        self.assertEqual(self.backend.calls[0]["text"], "同一个声音。")
        self.assertEqual(self.backend.calls[0]["speaker"], "Serena")
        self.assertNotIn("text_conditioning", provider.generation_parameters)
        self.assertEqual(provider.metadata["parameters"]["text_conditioning"], "full_text")
        self.assertEqual(details["text_conditioning"], provider.metadata["text_conditioning"])
        self.assertEqual(details["effective_generation_parameters"], provider.generation_parameters)
        self.assertEqual(details["codec_length"], provider.metadata["codec_length"])
        self.assertEqual(details["results"][0]["expected_samples_from_codecs"], 7680)

    def run_manifest(self, *, mode, name):
        script = load_script("synthesize_voice")
        profile_path = self.directory / "profiles.json"
        profile_path.write_text(json.dumps({
            "profiles": {"soft_female": {"qwen_mlx": {**PROFILE, "text_conditioning": mode}}},
        }, ensure_ascii=False))
        output = self.directory / name
        argv = [
            "synthesize_voice.py", "--provider", "qwen_mlx", "--text", "同一个声音。",
            "--profile", "soft_female",
            "--profiles", str(profile_path), "--model-path", str(self.model_dir),
            "--output-dir", str(output), "--seed", "42",
        ]
        with patch("sys.argv", argv), contextlib.redirect_stdout(io.StringIO()):
            script.main()
        return json.loads((output / "manifest.json").read_text())

    def test_actual_manifest_identity_changes_with_context_and_runtime_source(self):
        legacy = self.run_manifest(mode="legacy_streaming_text", name="legacy")
        full = self.run_manifest(mode="full_text", name="full")
        self.source_hash = "changed-fixture-runtime-source"
        changed = self.run_manifest(mode="full_text", name="changed_source")
        self.assertNotEqual(legacy["synthesis_identity_sha256"], full["synthesis_identity_sha256"])
        # Same requested profile/model/seed/waveform; effective implementation differs.
        self.assertEqual(full["parameters"], changed["parameters"])
        self.assertEqual(full["inputs"], changed["inputs"])
        self.assertEqual(full["output"]["audio_sha256"], changed["output"]["audio_sha256"])
        self.assertNotEqual(full["synthesis_identity_sha256"], changed["synthesis_identity_sha256"])

    def test_same_speaker_seed_and_successful_signal_do_not_approve_listening(self):
        first = self.run_manifest(mode="full_text", name="first")
        second = self.run_manifest(mode="full_text", name="second")
        self.assertEqual(first["seed"], second["seed"])
        self.assertEqual(first["parameters"]["speaker"], second["parameters"]["speaker"])
        self.assertEqual(first["output"]["audio_sha256"], second["output"]["audio_sha256"])
        for manifest in (first, second):
            self.assertEqual(manifest["status"], "generated_signal_checked")
            self.assertEqual(manifest["review_status"], "pending_human_listening")
            self.assertEqual(manifest["cases"][0]["review_status"], "pending_human_listening")
            self.assertEqual(
                manifest["cases"][0]["signal"]["semantic_accuracy"], "pending_human_listening",
            )

    def test_codec_implementation_identity_changes_manifest_even_with_same_waveform(self):
        first = self.run_manifest(mode="full_text", name="codec_first")
        self.codec_source_hash = "changed-fixture-tokenizer"
        second = self.run_manifest(mode="full_text", name="codec_second")
        self.assertEqual(first["output"]["audio_sha256"], second["output"]["audio_sha256"])
        self.assertNotEqual(first["synthesis_identity_sha256"], second["synthesis_identity_sha256"])

    def test_streaming_and_wrong_codec_clock_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "stream=False"):
            self.provider({**PROFILE, "stream": True})
        provider = self.provider()
        provider.codec_receipt["samples_per_codec_frame"] = 1921
        with self.assertRaisesRegex(RuntimeError, "lost samples"):
            provider.synthesize({"spoken_text": "完整的句子。"}, 42)


if __name__ == "__main__":
    unittest.main()

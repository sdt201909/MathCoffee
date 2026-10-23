"""Codec-clock regressions. Signal preservation is not a listening verdict."""

import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from mathcoffee.speech.qwen_codec_length import (
    _validate_runtime,
    begin_codec_request,
    codec_request_records,
    configure_codec_length,
    valid_codec_lengths,
)


class FakeTokenizer:
    decode_upsample_rate = 1920

    def __init__(self):
        self.input_codes = []
        self.short_decoder = False

    def decode(self, audio_codes):
        self.input_codes.append(audio_codes.copy())
        count = audio_codes.shape[1] * self.decode_upsample_rate
        if self.short_decoder:
            count -= 1
        # Fixed known waveform; metadata change must not alter these samples.
        wave = np.sin(np.arange(count, dtype=np.float32) * .03)[None, :]
        return wave, (audio_codes[..., 0] > 0).sum(axis=1) * self.decode_upsample_rate


class CodecLengthTests(unittest.TestCase):
    def test_valid_zero_code_is_counted_and_explicit_padding_is_not(self):
        cases = [
            ([[[4, 2], [0, 3], [9, 1]]], [5760]),
            ([[[0, 0], [0, 0], [0, 0]]], [5760]),
            ([[[4, 2], [0, 3], [-1, -1]]], [3840]),
            ([[[4, 2], [9, 3], [8, 1]]], [5760]),
            ([[[4, 2], [0, 3], [-1, -1]], [[0, 2], [-1, -1], [-1, -1]]], [3840, 1920]),
        ]
        for codes, expected in cases:
            with self.subTest(codes=codes):
                self.assertEqual(valid_codec_lengths(np.array(codes), 1920, np).tolist(), expected)
        unsigned = np.array([[[0, 1], [2, 0]]], dtype=np.uint32)
        self.assertEqual(valid_codec_lengths(unsigned, 1920, np).tolist(), [3840])

    def test_shape_dtype_and_malformed_padding_rejected(self):
        for codes in [np.zeros((0, 1, 2), dtype=int), np.zeros((1, 0, 2), dtype=int),
                      np.zeros((1, 2), dtype=int), np.zeros((1, 2, 2)),
                      np.array([[[-1, -1], [0, 3]]]), np.array([[[0, -1]]]),
                      np.array([[[-1, 0]]]), np.array([[[-2, -2]]]),
                      np.array([[[-1, -1]]])]:
            with self.subTest(codes=codes.tolist()), self.assertRaises(ValueError):
                valid_codec_lengths(codes, 1920, np)
        for rate in [0, -1, True, 1920.0]:
            with self.assertRaises(ValueError):
                valid_codec_lengths(np.zeros((1, 2, 2), dtype=int), rate, np)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tokenizer = FakeTokenizer()
        self.model = SimpleNamespace(
            config=SimpleNamespace(
                tts_model_type="custom_voice",
                talker_config=SimpleNamespace(num_code_groups=16, vocab_size=3072),
            ),
            speech_tokenizer=self.tokenizer,
        )
        self.runtime = {"tokenizer_source_sha256": "fixture", "upstream_api_verified": True}
        patches = [
            patch("mathcoffee.speech.qwen_codec_length._validate_runtime",
                  return_value=self.runtime),
            patch.dict("sys.modules", {"mlx": SimpleNamespace(core=np), "mlx.core": np}),
        ]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_adapter_retains_full_wave_with_zero_codes_and_records_source_identity(self):
        codes = np.ones((1, 4, 16), dtype=np.int32)
        codes[0, 1, 0] = codes[0, 3, 0] = 0
        reference, legacy = self.tokenizer.decode(codes)
        receipt = configure_codec_length(self.model)
        actual, lengths = self.tokenizer.decode(codes)
        np.testing.assert_array_equal(reference, actual)
        np.testing.assert_array_equal(lengths, [7680])
        np.testing.assert_array_equal(legacy, [3840])
        self.assertEqual(receipt["tokenizer_source_sha256"], "fixture")
        self.assertEqual(receipt["samples_per_codec_frame"], 1920)
        record = codec_request_records(self.model)[0]
        self.assertEqual(record["valid_first_code_zero_frames"], 2)
        self.assertEqual(record["complete_decoder_samples"], 7680)
        self.assertEqual(record["legacy_mask_samples"], 3840)

    def test_explicit_padding_is_clamped_without_modifying_original_codes(self):
        codes = np.ones((1, 4, 16), dtype=np.int32)
        codes[0, 1, 0] = 0
        codes[0, 3] = -1
        original = codes.copy()
        configure_codec_length(self.model)
        _, length = self.tokenizer.decode(codes)
        np.testing.assert_array_equal(codes, original)
        np.testing.assert_array_equal(self.tokenizer.input_codes[-1][0, 3], 0)
        self.assertEqual(length.tolist(), [5760])
        self.assertEqual(codec_request_records(self.model)[0]["explicit_padding_frames"], 1)

    def test_idempotence_and_per_request_records_not_nested_or_leaked(self):
        first = configure_codec_length(self.model)
        second = configure_codec_length(self.model)
        self.assertEqual(first, second)
        self.tokenizer.decode(np.ones((1, 2, 16), dtype=int))
        self.assertEqual(len(self.tokenizer.input_codes), 1)
        record = codec_request_records(self.model)
        record[0]["valid_samples"] = 1
        self.assertEqual(codec_request_records(self.model)[0]["valid_samples"], 3840)
        begin_codec_request(self.model)
        self.assertEqual(codec_request_records(self.model), [])

    def test_reject_stream_other_model_codebook_and_unknown_patch(self):
        for stream in [True, 1, None]:
            with self.assertRaisesRegex(ValueError, "stream=False"):
                configure_codec_length(self.model, stream=stream)
        self.model.config.tts_model_type = "base"
        with self.assertRaisesRegex(ValueError, "CustomVoice"):
            configure_codec_length(self.model)
        self.model.config.tts_model_type = "custom_voice"
        self.model.config.talker_config.num_code_groups = 8
        with self.assertRaisesRegex(RuntimeError, "codebook"):
            configure_codec_length(self.model)

    def test_reject_multibatch_group_count_reserved_ids_and_short_wave(self):
        configure_codec_length(self.model)
        for codes in [np.ones((2, 4, 16), dtype=int), np.ones((1, 4, 8), dtype=int),
                      np.full((1, 4, 16), 2150, dtype=int)]:
            with self.assertRaises(ValueError):
                self.tokenizer.decode(codes)
        self.tokenizer.short_decoder = True
        with self.assertRaisesRegex(RuntimeError, "codec clock"):
            self.tokenizer.decode(np.ones((1, 4, 16), dtype=int))


class Qwen3TTSSpeechTokenizer:
    decode_upsample_rate = 1920

    def decode(self, audio_codes):
        pass


Qwen3TTSSpeechTokenizer.__module__ = "mlx_audio.tts.models.qwen3_tts.speech_tokenizer"


class RuntimeGuardTests(unittest.TestCase):
    def test_source_version_class_api_and_clock_are_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "speech_tokenizer.py"
            source.write_text("reviewed source")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            with (
                patch("mathcoffee.speech.qwen_codec_length.importlib.metadata.version",
                      return_value="0.5.7"),
                patch("mathcoffee.speech.qwen_codec_length.inspect.getfile",
                      return_value=str(source)),
                patch("mathcoffee.speech.qwen_codec_length.UPSTREAM_TOKENIZER_SHA256", digest),
            ):
                result = _validate_runtime(Qwen3TTSSpeechTokenizer())
                self.assertEqual(result["tokenizer_source_sha256"], digest)
                with self.assertRaises(RuntimeError):
                    _validate_runtime(FakeTokenizer())
                with patch.object(Qwen3TTSSpeechTokenizer, "decode", lambda self, **kwargs: None):
                    with self.assertRaisesRegex(RuntimeError, "API"):
                        _validate_runtime(Qwen3TTSSpeechTokenizer())
                with patch.object(Qwen3TTSSpeechTokenizer, "decode_upsample_rate", 1):
                    with self.assertRaisesRegex(RuntimeError, "clock"):
                        _validate_runtime(Qwen3TTSSpeechTokenizer())
                with patch("mathcoffee.speech.qwen_codec_length.importlib.metadata.version",
                           return_value="0.6"):
                    with self.assertRaisesRegex(RuntimeError, "requires"):
                        _validate_runtime(Qwen3TTSSpeechTokenizer())
                source.write_text("changed source")
                with self.assertRaisesRegex(RuntimeError, "hash changed"):
                    _validate_runtime(Qwen3TTSSpeechTokenizer())


if __name__ == "__main__":
    unittest.main()

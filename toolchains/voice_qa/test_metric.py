"""Meaningful local QA checks; does not synthesize or alter narration."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "speaker_metric", ROOT / "scripts/audit_speaker_embeddings.py"
)
metric = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(metric)


class MetricTests(unittest.TestCase):
    def test_fbank_frame_count_and_mean_normalization(self):
        wave = np.random.default_rng(51).normal(0, 0.06, 48000).astype(np.float32)
        features = metric.features(wave, 16000)
        self.assertEqual(features.shape, (298, 80))
        self.assertLess(float(np.max(np.abs(features.mean(axis=0)))), 1e-4)
        lower_gain = metric.features(wave * 0.5, 16000)
        # Pure overall gain should vanish after CMN, not look like a new speaker.
        self.assertLess(float(np.max(np.abs(features - lower_gain))), 1e-4)

    def test_resampling_duration_and_invalid_audio(self):
        wave = np.random.default_rng(52).normal(0, 0.06, 72000).astype(np.float32)
        self.assertEqual(metric.features(wave, 24000).shape, (298, 80))
        with self.assertRaises(ValueError):
            metric.features(np.zeros(100), 16000)
        wave[500] = np.nan
        with self.assertRaises(ValueError):
            metric.features(wave, 24000)

    def test_manifest_preserves_active_bounds_and_rejects_duplicates(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "manifest.json"
            row = {
                "id": "x",
                "audio": {"path": "x.wav", "sha256": "abc"},
                "signal": {"active_start_sample": 12, "active_end_sample": 100},
                "spoken_text": "test",
            }
            path.write_text(json.dumps({"cases": [row]}))
            item = metric.load_items(path, set())[0]
            self.assertEqual(item["active_start_sample"], 12)
            self.assertEqual(item["active_end_sample"], 100)
            self.assertEqual(item["expected_sha256"], "abc")
            path.write_text(json.dumps({"cases": [row, row]}))
            with self.assertRaises(ValueError):
                metric.load_items(path, set())

    def test_audio_hash_checked_before_inference(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "wave.wav"
            sf.write(path, np.zeros(16000), 16000)
            with self.assertRaisesRegex(ValueError, "Audio hash mismatch"):
                metric.embed({"id": "x", "path": str(path), "expected_sha256": "bad"}, None)



if __name__ == "__main__":
    unittest.main()

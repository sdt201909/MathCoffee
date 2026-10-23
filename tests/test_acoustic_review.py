"""Validate proxy mathematics/invalid-input handling, not speaker identity."""

import json
import unittest

import numpy as np

from mathcoffee.speech.acoustic_review import acoustic_features, group_dispersion


def tone(frequency=220, rate=24_000, amplitude=0.1):
    return amplitude * np.sin(2 * np.pi * frequency * np.arange(rate) / rate)


class AcousticReviewTests(unittest.TestCase):
    def test_silence_is_missing_measurement_not_consistency_pass(self):
        result = acoustic_features(np.zeros(24_000), 24_000)
        self.assertEqual(result["measurement_status"], "no_active_energy")
        self.assertIsNone(result["mfcc_median"])
        self.assertIsNone(result["f0_median_hz"])
        self.assertEqual(result["review_status"], "proxy_only")
        json.dumps(result, allow_nan=False)

    def test_invalid_pcm_is_rejected(self):
        for wave in (np.zeros((24_000, 2)), np.array([]), np.array([np.nan]),
                     np.array([2.0]), np.array([42], dtype=np.int16)):
            with self.subTest(shape=wave.shape), self.assertRaises(ValueError):
                acoustic_features(wave, 24_000)
        with self.assertRaises(ValueError):
            acoustic_features(tone(), 24_000.0)

    def test_pitch_estimate_and_rate_conversion(self):
        at24 = acoustic_features(tone(), 24_000)
        at48 = acoustic_features(tone(rate=48_000), 48_000)
        self.assertAlmostEqual(at24["f0_median_hz"], 220, delta=2)
        self.assertAlmostEqual(at48["f0_median_hz"], at24["f0_median_hz"], delta=0.1)
        self.assertEqual(at24["energy_windows"], 100)
        self.assertGreater(at24["voiced_frames"], 80)
        json.dumps(at24, allow_nan=False)

    def test_gain_does_not_become_a_cepstral_voice_change(self):
        # Broadband noise avoids the log floor confound of pure tones.
        wave = np.random.default_rng(5).normal(0, 0.08, 24_000)
        loud = acoustic_features(wave, 24_000)
        quiet = acoustic_features(wave * 0.5, 24_000)
        np.testing.assert_allclose(loud["mfcc_median"], quiet["mfcc_median"], atol=1e-9)
        self.assertAlmostEqual(loud["active_rms_dbfs"] - quiet["active_rms_dbfs"],
                               20 * np.log10(2), places=6)

    def test_groups_require_same_cues_and_measured_speech(self):
        good = {"a": acoustic_features(tone(200), 24_000),
                "b": acoustic_features(tone(250), 24_000)}
        with self.assertRaises(ValueError):
            group_dispersion({"old": good, "new": {"a": good["a"]}}, "old")
        bad = {**good, "b": acoustic_features(np.zeros(24_000), 24_000)}
        with self.assertRaises(ValueError):
            group_dispersion({"old": good, "new": bad}, "old")

    def test_group_scale_is_shared_and_uniform_shift_remains_visible(self):
        old = {"a": acoustic_features(tone(200), 24_000),
               "b": acoustic_features(tone(250), 24_000)}
        moved = {key: {**value, "mfcc_median": (np.array(value["mfcc_median"]) + 1).tolist()}
                 for key, value in old.items()}
        report = group_dispersion({"old": old, "same": old, "shifted": moved}, "old")
        conditions = report["conditions"]
        self.assertAlmostEqual(conditions["old"]["mfcc_dispersion_rms"],
                               conditions["shifted"]["mfcc_dispersion_rms"])
        self.assertTrue(all(value == 0 for value in
                            conditions["same"]["paired_mfcc_distance_to_baseline"].values()))
        self.assertTrue(all(value > 0 for value in
                            conditions["shifted"]["paired_mfcc_distance_to_baseline"].values()))
        self.assertNotIn("passed", report)
        self.assertEqual(report["review_status"], "proxy_only")
        json.dumps(report, allow_nan=False)


if __name__ == "__main__":
    unittest.main()

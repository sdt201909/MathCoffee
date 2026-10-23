"""Check energy timing and honest text comparison, not perceived speaking style."""

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/measure_speech_pacing.py"
SPEC = importlib.util.spec_from_file_location("measure_speech_pacing", SCRIPT)
pacing = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pacing)


def pulse_wave(rate=24000):
    # 0.1 initial silence; 0.2 pulse; 0.05 micro-gap; 0.2 pulse;
    # 0.3 long pause; 0.1 pulse; 0.05 terminal silence.
    durations = [(0.1, 0), (0.2, 0.1), (0.05, 0), (0.2, 0.1),
                 (0.3, 0), (0.1, 0.1), (0.05, 0)]
    return np.concatenate([np.full(round(seconds * rate), value, dtype=float)
                           for seconds, value in durations])


class SpeechPacingTests(unittest.TestCase):
    def test_known_pulses_and_micro_pause_merging(self):
        m = pacing.measure_wave(pulse_wave(), 24000)
        for field, expected in {"duration_seconds": 1, "energy_active_seconds": 0.5,
                                "articulation_proxy_seconds": 0.55,
                                "active_envelope_seconds": 0.85,
                                "internal_pause_seconds": 0.3,
                                "leading_silence_seconds": 0.1,
                                "trailing_silence_seconds": 0.05}.items():
            self.assertAlmostEqual(m[field], expected, places=7)
        self.assertEqual(m["internal_pause_count"], 1)
        self.assertAlmostEqual(m["internal_pause_ratio"], 0.3 / 0.85)

    def test_sample_rate_independence(self):
        base = pacing.measure_wave(pulse_wave(), 24000)
        for rate in (8000, 16000, 22050, 44100, 48000, 96000):
            measured = pacing.measure_wave(pulse_wave(rate), rate)
            for field in ("energy_active_seconds", "articulation_proxy_seconds",
                          "active_envelope_seconds", "internal_pause_ratio"):
                self.assertAlmostEqual(measured[field], base[field], delta=0.011)

    def test_partial_last_frame_is_not_padded_in_duration(self):
        wave = np.full(2447, 0.1)
        m = pacing.measure_wave(wave, 24000)
        self.assertEqual(m["samples"], 2447)
        self.assertEqual(m["energy_active_seconds"], 2447 / 24000)
        self.assertEqual(m["trailing_silence_seconds"], 0)

    def test_gap_rule_is_inclusive_and_only_internal(self):
        at80 = np.r_[np.zeros(2400), np.ones(2400) * 0.1, np.zeros(1920),
                     np.ones(2400) * 0.1, np.zeros(2400)]
        merged = pacing.measure_wave(at80, 24000)
        separate = pacing.measure_wave(at80, 24000, merge_gap_seconds=0.07)
        self.assertEqual(merged["internal_pause_count"], 0)
        self.assertEqual(separate["internal_pause_count"], 1)
        self.assertEqual(merged["leading_silence_seconds"], 0.1)
        self.assertEqual(merged["trailing_silence_seconds"], 0.1)

    def test_invalid_or_silent_pcm_fails(self):
        invalid = [np.zeros(2400), np.array([]), np.array([np.nan]), np.array([np.inf]),
                   np.array([1.1]), np.array([2], dtype=np.int16), np.ones((100, 2))]
        for wave in invalid:
            with self.subTest(shape=wave.shape), self.assertRaises(ValueError):
                pacing.measure_wave(wave, 24000)
        for rate in (24000.0, True, 100, 500000):
            with self.assertRaises(ValueError):
                pacing.measure_wave(pulse_wave(), rate)
        for gap in (-1, float("nan"), 1):
            with self.assertRaises(ValueError):
                pacing.measure_wave(pulse_wave(), 24000, merge_gap_seconds=gap)

    def test_text_counts_do_not_invent_syllables(self):
        counts = pacing.text_counts("求导得到 derivative，再用 gradient descent 更新参数。")
        self.assertEqual(counts["han_characters"], 10)
        self.assertEqual(counts["english_words"], 3)
        self.assertEqual(counts["language_class"], "mixed_or_unresolved")
        self.assertEqual(counts["syllable_estimation"], "not_performed")
        self.assertIsNone(pacing.rate_fields(counts, pacing.measure_wave(
            pulse_wave(), 24000))["within_language_review_unit"])
        self.assertEqual(pacing.text_counts("六十五分钟")["han_characters"], 5)
        raw = pacing.text_counts("65分钟")
        self.assertEqual(raw["unexpanded_numeric_tokens"], ["65"])
        self.assertEqual(raw["language_class"], "mixed_or_unresolved")

    def make_manifest(self, directory, text="六十五分钟", duplicate=False, bogus_hash=False):
        wav = directory / "cue.wav"
        sf.write(wav, pulse_wave(), 24000, subtype="PCM_24")
        cue = {"id": "cue", "subtitle_text": "65分钟", "spoken_text": text,
               "audio": {"path": str(wav), "sha256": "0" * 64 if bogus_hash else pacing.sha(wav)},
               "signal": {"samples": 24000, "sample_rate": 24000, "channels": 1}}
        path = directory / "manifest.json"
        path.write_text(json.dumps({"cases": [cue, cue] if duplicate else [cue]}))
        return path

    def test_manifest_reads_pcm_and_hashes_actual_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_manifest(Path(tmp))
            report = pacing.measure_input(path)
            cue = report["cues"][0]
            pcm, _ = sf.read(cue["path"], dtype="float64")
            self.assertEqual(cue["pcm_sha256_f64le"], hashlib.sha256(
                pcm.astype("<f8").tobytes()).hexdigest())
            self.assertEqual(cue["text_counts"]["han_characters"], 5)
            self.assertEqual(cue["text"], "65分钟")
            json.dumps(report, allow_nan=False)

    def test_manifest_hash_duplicate_and_missing_spoken_text_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            for options in ({"bogus_hash": True}, {"duplicate": True}, {"text": None}):
                with self.subTest(options=options), self.assertRaises(ValueError):
                    pacing.measure_input(self.make_manifest(Path(tmp), **options))

    def test_chapter_index_and_pcm_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_manifest(Path(tmp))
            cue = json.loads(path.read_text())["cases"][0]
            index_cue = {"id": cue["id"], "text": cue["subtitle_text"],
                         "spoken_text": cue["spoken_text"], **cue["audio"], **cue["signal"]}
            path.write_text(json.dumps({"chapters": [{"id": "ch01", "cues": [index_cue]}]}))
            self.assertEqual(pacing.measure_input(path)["cues"][0]["chapter"], "ch01")
            index_cue["samples"] += 1
            path.write_text(json.dumps({"chapters": [{"id": "ch01", "cues": [index_cue]}]}))
            with self.assertRaises(ValueError):
                pacing.measure_input(path)

    def test_same_text_pairing_uses_duration_not_mixed_fake_units(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = pacing.measure_input(self.make_manifest(Path(tmp), "这是 user equilibrium。"))
            new = json.loads(json.dumps(base))
            for key in ("duration_seconds", "active_envelope_seconds", "articulation_proxy_seconds",
                        "energy_active_seconds"):
                new["cues"][0]["acoustic"][key] /= 1.1
            result = pacing.compare_inputs(new, base)
            self.assertAlmostEqual(
                result["pairs"][0]["articulation_proxy_seconds_speed_ratio"], 1.1)
            new["cues"][0]["spoken_text"] += "不同"
            with self.assertRaises(ValueError):
                pacing.compare_inputs(new, base)

    def test_unmatched_cue_is_disclosed_and_not_paired(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = pacing.measure_input(self.make_manifest(Path(tmp)))
            new = json.loads(json.dumps(base))
            new["cues"][0]["id"] = "new"
            result = pacing.compare_inputs(new, base)
            self.assertEqual(result["same_spoken_text_pair_count"], 0)
            self.assertEqual(result["unmatched_ids_excluded"], ["new"])
            self.assertIsNone(result["pooled_durations"]["duration_seconds"][
                "pooled_same_text_speed_ratio"])

    def test_selection_validates_ids_and_does_not_claim_real_neighbors(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_manifest(Path(tmp))
            self.assertEqual(len(pacing.measure_input(path, cue_ids=["cue"])["cues"]), 1)
            for ids in (["absent"], [], ["cue", "cue"]):
                with self.assertRaises(ValueError):
                    pacing.measure_input(path, cue_ids=ids)

    def test_adjacent_flag_is_review_only_and_discloses_manifest_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = pacing.measure_input(self.make_manifest(
                Path(tmp), "这是一个足够长的中文测试句子。"))
            first = base["cues"][0]
            second = json.loads(json.dumps(first))
            second["id"] = "next"
            second["rates"]["han_chars_per_articulation_proxy_second"] *= 1.5
            result = pacing.adjacent_review([first, second], "synthesize_manifest")
            self.assertEqual(len(result["candidates"]), 1)
            self.assertIn("not_necessarily", result["pairs"][0]["adjacency"])
            self.assertNotIn("passed", result)


if __name__ == "__main__":
    unittest.main()

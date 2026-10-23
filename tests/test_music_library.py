"""Independent signal assertions for the reusable theme/ducking pipeline."""

from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
import wave
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import numpy as np

from mathcoffee.music_library import (
    detect_activity,
    duck_music,
    generate_track,
    load_catalog,
    mix_narration,
    select_track,
)
from scripts import create_theme_music as cli

CATALOG = Path(__file__).resolve().parents[1] / "src/mathcoffee/data/audio/music_catalog.json"


class MusicLibraryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = load_catalog(CATALOG)

    def test_selection_matches_distinct_requests_and_is_repeatable(self) -> None:
        cases = (
            ("亲情", "温柔", "warm_windows"),
            ("数学", "好奇", "small_steps"),
            ("证据", "悬念", "unanswered_room"),
        )
        for theme, mood, expected in cases:
            chosen = select_track(self.catalog, theme, mood, 7)
            self.assertEqual(chosen["id"], expected)
            self.assertEqual(chosen, select_track(self.catalog, theme, mood, 7))
        with self.assertRaisesRegex(ValueError, "no catalog music"):
            select_track(self.catalog, "heavy metal", "ecstatic")
        self.assertEqual(select_track(self.catalog, "数学", "unknown")["id"], "small_steps")
        self.assertEqual(select_track(self.catalog, "unknown", "温柔")["id"], "warm_windows")

    def test_three_recipes_are_real_distinct_finite_and_sample_reproducible(self) -> None:
        hashes, onset_profiles = set(), []
        for track in self.catalog["tracks"]:
            audio = generate_track(track, 6, 16000, seed=23)
            np.testing.assert_array_equal(audio, generate_track(track, 6, 16000, seed=23))
            self.assertEqual(audio.shape, (96000, 2))
            self.assertEqual(audio.dtype, np.float32)
            self.assertTrue(np.isfinite(audio).all())
            self.assertGreater(np.sqrt(np.mean(audio**2)), 0.005)
            self.assertLess(np.max(np.abs(audio)), 0.5)
            np.testing.assert_array_equal(audio[[0, -1]], np.zeros((2, 2)))
            self.assertFalse(np.array_equal(audio[:, 0], audio[:, 1]))
            hashes.add(hashlib.sha256(audio.tobytes()).hexdigest())
            profile = np.sqrt(np.mean(audio.reshape(60, -1, 2) ** 2, axis=(1, 2)))
            onset_profiles.append(profile)
        self.assertEqual(len(hashes), 3)
        # Merely renaming/retuning one bed would retain its amplitude pattern.
        self.assertLess(np.corrcoef(onset_profiles[0], onset_profiles[1])[0, 1], 0.8)
        self.assertLess(np.corrcoef(onset_profiles[1], onset_profiles[2])[0, 1], 0.8)

    def test_detect_activity_bridges_phrase_but_not_large_silence(self) -> None:
        rate = 16000
        time = np.arange(rate * 4) / rate
        voice = 0.2 * np.sin(2 * np.pi * 230 * time)
        voice[~(((time >= 1) & (time < 1.5)) | ((time >= 1.6) & (time < 2.0)))] = 0
        self.assertEqual(detect_activity(voice, rate), [(1.0, 2.0)])
        self.assertEqual(detect_activity(np.zeros(rate), rate), [])

    def test_duck_lowers_music_during_voice_and_recovers_in_silence(self) -> None:
        rate = 16000
        time = np.arange(rate * 5) / rate
        music = np.full((len(time), 2), 0.1)
        voice = 0.2 * np.sin(2 * np.pi * 300 * time)
        voice[(time < 1) | (time >= 3)] = 0
        ducked, envelope, report = duck_music(music, voice, rate, duck_db=12)
        speech_level = float(np.mean(ducked[(time > 1.2) & (time < 2.8)]))
        quiet_level = float(np.mean(ducked[(time > 4) & (time < 4.8)]))
        self.assertAlmostEqual(20 * np.log10(speech_level / quiet_level), -12, places=4)
        self.assertAlmostEqual(quiet_level, 0.1, places=6)
        self.assertLess(envelope[round(0.99 * rate)], 0.5)  # pre-onset attack
        self.assertLess(envelope[round(3.2 * rate)], 0.6)  # still releasing
        self.assertLess(float(np.max(np.abs(np.diff(envelope)))), 0.002)
        self.assertEqual(report["activity_intervals_seconds"], [[1.0, 3.0]])

    def test_authored_activity_and_adjacent_intervals_do_not_pump(self) -> None:
        rate = 16000
        music, voice = np.ones((rate * 3, 2)) * 0.1, np.zeros(rate * 3)
        _, gain, report = duck_music(
            music, voice, rate, activity_intervals=[(0.5, 1.5), (1.4, 2.0)]
        )
        self.assertLess(float(np.max(gain[rate : round(1.9 * rate)])), 0.26)
        self.assertEqual(report["activity_source"], "authored_intervals")

    def test_mix_preserves_voice_timing_and_prevents_clipping(self) -> None:
        rate = 16000
        voice = np.zeros((rate, 2))
        voice[3210] = 1.1
        music = np.full((rate * 2, 2), 0.5)
        mixed, report = mix_narration(music, voice, rate, activity_intervals=[])
        self.assertEqual(mixed.shape, music.shape)
        self.assertEqual(int(np.argmax(mixed[:, 0])), 3210)
        self.assertLessEqual(float(np.max(np.abs(mixed))), 0.892)
        self.assertLess(report["master_gain"], 1)
        self.assertEqual(report["output"]["clipped_samples"], 0)
        self.assertEqual(report["voice_shift_samples"], 0)

    def test_unsafe_audio_or_timeline_rejected(self) -> None:
        track = self.catalog["tracks"][0]
        for duration in (0, float("nan"), 2000):
            with self.assertRaises(ValueError):
                generate_track(track, duration)
        with self.assertRaises(ValueError):
            duck_music(np.zeros(100), np.zeros(101), 16000)
        with self.assertRaises(ValueError):
            duck_music(np.zeros(16000), np.zeros(16000), 16000, activity_intervals=[(-1, 2)])
        with self.assertRaises(ValueError):
            mix_narration(np.array([np.nan]), np.zeros(1), 16000)

    def test_cli_rejects_nonempty_output_and_voice_name_collision_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            existing = output / "warm_windows.wav"
            existing.write_bytes(b"original input must remain untouched")
            before = existing.read_bytes()
            for voice_args in ([], ["--voice", str(existing)]):
                stderr = io.StringIO()
                with (
                    patch("sys.argv", ["create_theme_music", "--output-dir", folder, *voice_args]),
                    redirect_stderr(stderr),
                    self.assertRaises(SystemExit) as stopped,
                ):
                    cli.main()
                self.assertEqual(stopped.exception.code, 2)
                self.assertIn("must be new or empty", stderr.getvalue())
                self.assertEqual(existing.read_bytes(), before)
                self.assertEqual(list(output.iterdir()), [existing])

    def test_cli_captures_voice_hash_before_generation_and_accepts_empty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            voice = Path(folder) / "source.wav"
            with wave.open(str(voice), "wb") as stream:
                stream.setnchannels(1)
                stream.setsampwidth(2)
                stream.setframerate(16000)
                stream.writeframes(np.zeros(1600, dtype="<i2").tobytes())
            expected_hash = hashlib.sha256(voice.read_bytes()).hexdigest()
            output = Path(folder) / "output"
            output.mkdir()
            real_generate = cli.generate_track

            def change_external_file_after_read(*args, **kwargs):
                # Simulate an external writer after voice samples were loaded.
                # Provenance must describe samples used, not this later file.
                voice.write_bytes(b"external replacement after original input was read")
                return real_generate(*args, **kwargs)

            with (
                patch(
                    "sys.argv",
                    [
                        "create_theme_music",
                        "--output-dir",
                        str(output),
                        "--voice",
                        str(voice),
                        "--duration",
                        "0.1",
                        "--sample-rate",
                        "16000",
                    ],
                ),
                patch.object(cli, "generate_track", side_effect=change_external_file_after_read),
                redirect_stdout(io.StringIO()),
            ):
                cli.main()
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(manifest["mix"]["voice_sha256"], expected_hash)
            self.assertNotEqual(cli.sha256(voice), expected_hash)
            self.assertEqual(manifest["mix"]["decoded_metrics"]["samples"], 1600)


if __name__ == "__main__":
    unittest.main()

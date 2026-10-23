"""AAC container duration, decoder padding and protected QA-cache regressions."""

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
SPEC = importlib.util.spec_from_file_location(
    "native_audio_validation", ROOT / "src/mathcoffee/audio_validation.py",
)
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


def native_fixture():
    return {
        "codec": "aac", "sample_rate": 48000, "channels": 2, "first_pts_samples": 0,
        "all_frame_timestamps": "PASS", "frames_decoded": 2, "decoded_samples": 2048,
        "container_valid_samples": 1984, "container_duration_ticks": 1984,
        "container_time_base": "1/48000", "aac_padding_samples": 64,
        "pyav_version": VERIFY.av.__version__,
    }


class FakeContainer:
    def __init__(self, duration=1984, starts=(0, 1024), lengths=(1024, 1024)):
        layout = SimpleNamespace(channels=(0, 1))
        codec = SimpleNamespace(name="aac", sample_rate=48000, layout=layout)
        stream = SimpleNamespace(
            start_time=0, duration=duration, time_base=Fraction(1, 48000), codec_context=codec,
        )
        self.streams = SimpleNamespace(video=[object()], audio=[stream])
        self.frames = [SimpleNamespace(
            pts=pts, time_base=Fraction(1, 48000), samples=samples,
            sample_rate=48000, layout=layout,
        ) for pts, samples in zip(starts, lengths, strict=True)]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def decode(self, _stream):
        return iter(self.frames)


class NativeAudioTests(unittest.TestCase):
    def test_native_decoder_full_tail_frame_and_exact_container_duration(self):
        with patch.object(VERIFY.av, "open", return_value=FakeContainer()):
            result = VERIFY.validate_native_audio("fixture.mp4", 1984)
        self.assertEqual(result["container_valid_samples"], 1984)
        self.assertEqual(result["decoded_samples"], 2048)
        self.assertEqual(result["aac_padding_samples"], 64)

    def test_decoder_that_honors_padding_is_equally_valid(self):
        with patch.object(VERIFY.av, "open", return_value=FakeContainer(lengths=(1024, 960))):
            result = VERIFY.validate_native_audio("fixture.mp4", 1984)
        self.assertEqual(result["decoded_samples"], 1984)
        self.assertEqual(result["aac_padding_samples"], 0)

    def test_missing_or_wrong_container_duration_fails(self):
        for duration in (None, 1983, 1985, 2048):
            with self.subTest(duration=duration), patch.object(
                VERIFY.av, "open", return_value=FakeContainer(duration=duration),
            ), self.assertRaisesRegex(ValueError, "container audio duration"):
                VERIFY.validate_native_audio("fixture.mp4", 1984)

    def test_gap_offset_truncation_and_whole_extra_frame_fail(self):
        cases = [
            FakeContainer(starts=(1, 1025)),
            FakeContainer(starts=(0, 1025)),
            FakeContainer(lengths=(1024, 959)),
            FakeContainer(starts=(0, 1024, 2048), lengths=(1024, 1024, 1024)),
        ]
        for container in cases:
            with self.subTest(frames=container.frames), patch.object(
                VERIFY.av, "open", return_value=container,
            ), self.assertRaises(ValueError):
                VERIFY.validate_native_audio("fixture.mp4", 1984)

    def test_only_both_exact_export_lengths_are_accepted(self):
        native = native_fixture()
        valid = VERIFY.pcm_export_metadata(1984 * 8, native, 1984)
        padded = VERIFY.pcm_export_metadata(2048 * 8, native, 1984)
        self.assertEqual(valid["decoder_length_semantics"], "container_valid_samples")
        self.assertEqual(padded["tail_padding_samples"], 64)
        for size in (1983 * 8, 1985 * 8, 2000 * 8, 2049 * 8, 1984 * 8 + 1):
            with self.subTest(bytes=size), self.assertRaisesRegex(ValueError, "PCM export must"):
                VERIFY.pcm_export_metadata(size, native, 1984)

    def test_native_receipt_inconsistency_is_rejected(self):
        for key, value in (
            ("container_valid_samples", 2048), ("container_duration_ticks", 2048),
            ("container_time_base", "1/44100"), ("aac_padding_samples", 0),
            ("all_frame_timestamps", "FAIL"), ("first_pts_samples", 1),
        ):
            native = native_fixture()
            native[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(
                ValueError, "receipt is inconsistent",
            ):
                VERIFY.pcm_export_metadata(1984 * 8, native, 1984)


class AudioCacheTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.video = self.directory / "video.mp4"
        self.video.write_bytes(b"immutable-video-fixture")
        self.video_hash = VERIFY.sha256_file(self.video)
        self.export_samples = 1984
        self.ffmpeg_version = "ffmpeg fixture 9\nlibavcodec 63"

    def fake_run(self, command, **_kwargs):
        if command == ["ffmpeg", "-version"]:
            return SimpleNamespace(stdout=self.ffmpeg_version)
        self.assertNotIn("-ar", command)
        self.assertNotIn("-ac", command)
        self.assertNotIn("-t", command)
        self.assertNotIn("-af", command)
        Path(command[-1]).write_bytes(bytes(self.export_samples * 8))
        return SimpleNamespace(returncode=0)

    def checked(self):
        with patch.object(
            VERIFY, "validate_native_audio", return_value=native_fixture(),
        ), patch.object(
            VERIFY.subprocess, "run", side_effect=self.fake_run,
        ):
            return VERIFY.checked_audio_cache(self.directory, self.video, self.video_hash, 1984)

    def test_valid_length_receipt_and_cache_reuse(self):
        path, native, reused = self.checked()
        self.assertFalse(reused)
        self.assertEqual(path.stat().st_size, 1984 * 8)
        self.assertEqual(native["decoded_samples"], 2048)
        receipt = json.loads(path.with_suffix(".f32.json").read_text())
        self.assertEqual(receipt["identity"]["schema_version"], 2)
        self.assertEqual(receipt["identity"]["ffmpeg_version"], self.ffmpeg_version)
        self.assertEqual(receipt["pcm_export"]["samples"], 1984)
        self.assertEqual(receipt["pcm_export"]["tail_padding_samples"], 0)
        self.assertTrue(self.checked()[2])

    def test_full_native_frames_can_be_exported_and_reused(self):
        self.export_samples = 2048
        path, _, _ = self.checked()
        receipt = json.loads(path.with_suffix(".f32.json").read_text())
        self.assertEqual(receipt["pcm_export"]["tail_padding_samples"], 64)
        self.assertTrue(self.checked()[2])

    def test_in_between_length_retains_unreceipted_evidence(self):
        self.export_samples = 2000
        with self.assertRaisesRegex(ValueError, "PCM export must"):
            self.checked()
        path = self.directory / "decoded_audio.f32"
        original = path.read_bytes()
        self.assertFalse(path.with_suffix(".f32.json").exists())
        with self.assertRaisesRegex(ValueError, "unreceipted QA audio retained"):
            self.checked()
        self.assertEqual(path.read_bytes(), original)

    def test_cache_rejects_changed_decoder_version(self):
        self.checked()
        self.ffmpeg_version = "another decoder version"
        with self.assertRaisesRegex(ValueError, "different inputs/checks"):
            self.checked()

    def test_cache_rejects_false_export_semantics(self):
        path, _, _ = self.checked()
        receipt_path = path.with_suffix(".f32.json")
        receipt = json.loads(receipt_path.read_text())
        changed = deepcopy(receipt)
        changed["pcm_export"]["tail_padding_samples"] = 64
        receipt_path.write_text(json.dumps(changed))
        with self.assertRaisesRegex(ValueError, "PCM receipt is inconsistent"):
            self.checked()


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is required for actual AAC fixture")
class ActualAACPaddingTest(unittest.TestCase):
    def test_short_actual_aac_preserves_valid_length_and_native_pcm_export(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            audio, video = directory / "source.wav", directory / "fixture.mp4"
            # Deliberately 64 samples short of two AAC frames, covering a partial final AAC frame.
            samples = 1984
            wave = (np.sin(np.arange(samples) * 2 * np.pi * 440 / 48000) * 5000).astype(np.int16)
            wavfile.write(audio, 48000, np.column_stack([wave, wave]))
            subprocess.run([
                "ffmpeg", "-v", "error", "-nostdin", "-n", "-f", "lavfi", "-i",
                "color=c=black:s=32x32:r=30:d=0.1", "-i", str(audio), "-c:v", "libx264",
                "-c:a", "aac", "-movflags", "+faststart", str(video),
            ], check=True)
            native = VERIFY.validate_native_audio(video, samples)
            self.assertEqual(native["container_valid_samples"], samples)
            self.assertIn(native["decoded_samples"], (1984, 2048))
            exported, _, reused = VERIFY.checked_audio_cache(
                directory, video, VERIFY.sha256_file(video), samples,
            )
            self.assertFalse(reused)
            direct = subprocess.run([
                "ffmpeg", "-v", "error", "-nostdin", "-i", str(video), "-map", "0:a:0",
                "-f", "f32le", "-acodec", "pcm_f32le", "pipe:1",
            ], check=True, capture_output=True).stdout
            self.assertEqual(exported.read_bytes(), direct)
            self.assertTrue(VERIFY.checked_audio_cache(
                directory, video, VERIFY.sha256_file(video), samples,
            )[2])


if __name__ == "__main__":
    unittest.main()

"""Failure boundaries for renderer interchange, without installing a browser."""

import copy
import tempfile
import unittest
from pathlib import Path

from mathcoffee.renderer_contract import local_asset, sha256_file, validate_timeline


class RendererContractTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        (self.root / "clip.mp4").write_bytes(
            b"fixture; header inspection disabled in boundary tests"
        )
        (self.root / "mix.wav").write_bytes(b"fixture")
        self.plan = {
            "schema_version": 1,
            "width": 1920,
            "height": 1080,
            "fps": 60,
            "duration_frames": 120,
            "clips": [
                {
                    "id": "c",
                    "renderer": "manim",
                    "file": "clip.mp4",
                    "sha256": sha256_file(self.root / "clip.mp4"),
                    "start_frame": 0,
                    "source_in_frame": 0,
                    "duration_frames": 120,
                }
            ],
            "captions": [{"id": "s", "text": "同一时间轴", "start_frame": 1, "end_frame": 60}],
            "audio": {
                "file": "mix.wav",
                "sha256": sha256_file(self.root / "mix.wav"),
                "sample_rate": 48000,
                "samples": 96000,
            },
            "qa": {"anchor_frames": [0, 118]},
        }

    def check(self, plan=None):
        return validate_timeline(plan or self.plan, self.root, inspect_media=False)

    def test_half_open_end_and_exact_sample_clock(self):
        result = self.check()
        self.assertEqual((result["frames"], result["duration_seconds"]), (120, 2))
        self.plan["audio"]["samples"] -= 1
        with self.assertRaisesRegex(ValueError, "exactly"):
            self.check()

    def test_silent_contract_requires_explicit_opt_in_and_keeps_anchor_validation(self):
        plan = copy.deepcopy(self.plan)
        plan["audio"] = None
        with self.assertRaisesRegex(ValueError, "mixed audio"):
            self.check(plan)
        result = validate_timeline(plan, self.root, inspect_media=False, allow_no_audio=True)
        self.assertEqual(result["audio_samples"], 0)
        plan["qa"]["anchor_frames"] = [119]
        with self.assertRaisesRegex(ValueError, "extends"):
            validate_timeline(plan, self.root, inspect_media=False, allow_no_audio=True)

    def test_noninteger_and_boolean_frame_clocks_are_rejected(self):
        for value in (60.0, True, 0, -1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                plan = copy.deepcopy(self.plan)
                plan["fps"] = value
                self.check(plan)

    def test_caption_overlap_duplicate_ids_and_overflow_are_rejected(self):
        for second in (
            {"id": "x", "text": "overlap", "start_frame": 59, "end_frame": 80},
            {"id": "s", "text": "duplicate", "start_frame": 60, "end_frame": 80},
            {"id": "x", "text": "overflow", "start_frame": 90, "end_frame": 121},
        ):
            plan = copy.deepcopy(self.plan)
            plan["captions"].append(second)
            with self.subTest(second=second), self.assertRaises(ValueError):
                self.check(plan)

    def test_hash_drift_is_not_silently_reused(self):
        (self.root / "clip.mp4").write_bytes(b"modified after the receipt")
        with self.assertRaisesRegex(ValueError, "hash changed"):
            self.check()

    def test_network_absolute_and_parent_paths_are_rejected(self):
        for path in ("https://example.org/a.mp4", "/tmp/a", "../a", "a\\b"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                local_asset(self.root, path)

    def test_symlink_cannot_expose_assets_outside_staging(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "private.txt"
            target.write_text("fixture")
            (self.root / "escape").symlink_to(target)
            with self.assertRaises(ValueError):
                local_asset(self.root, "escape")

    def test_clip_ranges_and_marker_duration_are_bounded(self):
        self.plan["clips"][0]["duration_frames"] = 121
        with self.assertRaises(ValueError):
            self.check()
        self.plan["clips"][0]["duration_frames"] = 120
        self.plan["qa"]["anchor_frames"] = [119]
        with self.assertRaises(ValueError):
            self.check()


if __name__ == "__main__":
    unittest.main()

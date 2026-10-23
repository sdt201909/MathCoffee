"""Measured scheduling, cache invalidation and actual-input review gates."""

import copy
import json
import tempfile
import unittest
from pathlib import Path

from mathcoffee.authoring import plan_project
from mathcoffee.pipeline import (
    _caption_pages, _final_gate, file_hash, measured_schedule, read,
    implementation_sources, receipt_valid, scene_identity, source_freshness,
    source_identity, status, workspace_file, write,
)
from mathcoffee.style import resolve_style
from mathcoffee.workspace import init_workspace
from mathcoffee.verification import verify_artifacts


def fixture():
    return {
        "schema_version": 1, "episode": "test", "title": "两个点之间",
        "math_states": {"points": {"points": [[0, 0], [1, 1]]}, "unused": {"value": 9}},
        "actions": [],
        "scenes": [{"id": "opening", "title": "连线", "sentences": [
            {"id": "opening_one", "text": "两个点确定一条直线。",
             "duration_seconds": 2, "visual": {"kind": "line", "state_ref": "points"}},
            {"id": "opening_two", "text": "再看这条等式。", "formula": "1+1=2"},
        ]}],
    }


def plan():
    return {"authoring": fixture(), "style": resolve_style("mathcoffee-shorts@1"),
            "project": {"voice": {"mode": "imported"}, "music": {"enabled": False}},
            "source_sha256": {"authoring": "a" * 64}}


def voice():
    return {"mode": "imported", "cues": [
        {"id": identifier, "path": f"{identifier}.wav", "sha256": "a" * 64,
         "sample_rate": 24000, "samples": 30000, "active_start_sample": 1200,
         "active_end_sample": 28800}
        for identifier in ("opening_one", "opening_two")]}


class ScheduleTests(unittest.TestCase):
    def test_complete_pcm_and_formula_hold_are_preserved(self):
        result = measured_schedule(plan(), voice())
        cues = result["scenes"][0]["sentences"]
        self.assertEqual(cues[0]["slot"]["duration_frames"], 68)  # 1.25 s PCM + 1 s read hold.
        self.assertEqual(cues[1]["slot"]["duration_frames"], 180)
        self.assertEqual(result["duration_frames"], 248)
        self.assertAlmostEqual(cues[0]["active_start_seconds"], .05)
        self.assertAlmostEqual(cues[0]["active_end_seconds"], 1.2)
        self.assertEqual(cues[1]["start_frame"], 68)

    def test_missing_reordered_or_corrupt_voice_windows_are_rejected(self):
        for candidate in ({"cues": []}, {**voice(), "cues": list(reversed(voice()["cues"]))}):
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                measured_schedule(plan(), candidate)
        candidate = voice()
        candidate["cues"][0]["active_end_sample"] = 30001
        with self.assertRaisesRegex(ValueError, "activity"):
            measured_schedule(plan(), candidate)

    def test_silent_mode_is_explicit_and_not_estimated_speech(self):
        candidate = plan()
        candidate["project"]["voice"]["mode"] = "silent"
        result = measured_schedule(candidate, {"mode": "silent", "cues": []})
        self.assertEqual(result["voice_mode"], "silent")
        self.assertNotIn("active_start_seconds", result["scenes"][0]["sentences"][0])

    def test_formula_and_summary_in_shared_states_receive_minimum_reading_time(self):
        candidate = plan()
        candidate["project"]["voice"]["mode"] = "silent"
        source = candidate["authoring"]
        source["math_states"]["equation"] = {"kind": "formula", "text": "1+1=2"}
        source["scenes"][0]["sentences"][0]["visual"] = {"state_ref": "equation"}
        result = measured_schedule(candidate, {"mode": "silent", "cues": []})
        self.assertEqual(result["scenes"][0]["sentences"][0]["slot"]["duration_frames"], 180)

    def test_scene_cache_ignores_global_offset_and_unrelated_math_states(self):
        candidate = plan()
        schedule = measured_schedule(candidate, voice())
        scene = schedule["scenes"][0]
        first = scene_identity(scene, candidate, schedule)
        changed_scene = copy.deepcopy(scene)
        changed_scene["start_frame"] += 500
        for cue in changed_scene["sentences"]:
            cue["start_frame"] += 500
            cue["end_frame"] += 500
            cue["active_start_seconds"] += 500 / schedule["fps"]
            cue["active_end_seconds"] += 500 / schedule["fps"]
        self.assertEqual(first, scene_identity(changed_scene, candidate, schedule))
        candidate["authoring"]["math_states"]["unused"]["value"] = 42
        self.assertEqual(first, scene_identity(scene, candidate, schedule))
        candidate["authoring"]["math_states"]["points"]["points"][1][0] = 3
        self.assertNotEqual(first, scene_identity(scene, candidate, schedule))

    def test_source_identity_changes_for_text_style_audio_and_runtime(self):
        original = plan()
        original_voice = voice()
        before = source_identity(original, original_voice)
        changed = copy.deepcopy(original)
        changed["authoring"]["scenes"][0]["sentences"][0]["text"] += "再观察。"
        self.assertNotEqual(before, source_identity(changed, original_voice))
        changed = copy.deepcopy(original)
        changed["style"]["colors"]["result"] = "#FFFFFF"
        self.assertNotEqual(before, source_identity(changed, original_voice))
        changed_voice = copy.deepcopy(original_voice)
        changed_voice["cues"][0]["sha256"] = "b" * 64
        self.assertNotEqual(before, source_identity(original, changed_voice))
        changed = copy.deepcopy(original)
        changed["runtime_fingerprint"] = {"engine_sources": {"renderer": "changed"}}
        self.assertNotEqual(before, source_identity(changed, original_voice))

    def test_custom_scene_code_is_part_of_full_build_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "scene.py"
            source.write_text("# first custom implementation")
            candidate = plan()
            candidate["workspace"] = str(root)
            candidate["project"]["scene_module"] = "scene.py"
            before = source_identity(candidate, voice())
            source.write_text("# replacement implementation")
            self.assertNotEqual(before, source_identity(candidate, voice()))

    def test_captions_use_the_configured_rectangle_without_losing_words(self):
        style = resolve_style("mathcoffee-longform@1")
        cue = {"id": "words", "text": "甲" * 90, "active_start_seconds": 1,
               "active_end_seconds": 5}
        pages = _caption_pages(cue, 30, False, style)
        self.assertGreater(len(pages), 1)
        self.assertEqual("".join(page["text"].replace("\n", "") for page in pages), cue["text"])
        self.assertEqual(pages[0]["start_frame"], 30)
        self.assertEqual(pages[-1]["end_frame"], 150)
        self.assertTrue(all(a["end_frame"] == b["start_frame"] for a, b in zip(pages, pages[1:])))


class BuildBoundaryTests(unittest.TestCase):
    def test_status_marks_modified_authoring_and_implementation_stale_without_models(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "workspace"
            init_workspace(root, title="点与线")
            write(root / "authoring.json", fixture())
            current = plan_project(root)
            current["runtime_fingerprint"] = {"engine_sources": {}}
            manifest = {"status": "PASS", "technical_status": "PASS", "quality": "draft",
                        "identity": "a" * 64, "plan": current,
                        "implementation_sources": implementation_sources()}
            write(root / "build/manifest.json", manifest)
            write(root / "build/latest.json", {"manifest": str(root / "build/manifest.json")})
            self.assertEqual(status(root)["status"], "PASS")
            altered = fixture()
            altered["scenes"][0]["sentences"][0]["text"] += "再观察。"
            write(root / "authoring.json", altered)
            result = status(root)
            self.assertEqual(result["status"], "STALE")
            self.assertIn("authoring", result["source_freshness"]["changed"])
            write(root / "authoring.json", fixture())
            manifest["implementation_sources"]["components.py"] = "outdated"
            self.assertIn("package_implementation", source_freshness(root, manifest)["changed"])

    def test_verification_checks_timeline_schedule_and_display_bytes_before_media(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            names = {"timeline": "timeline.json", "schedule": "schedule.json",
                     "display_manifest": "display.json"}
            manifest = {**names, "output": {"path": "film.mp4"}, "outputs": []}
            for name in [*names.values(), "film.mp4"]:
                path = root / name
                path.write_text("fixture")
                manifest["outputs"].append({"path": str(path), "sha256": file_hash(path)})
            verify_artifacts(root, manifest)
            for name in names.values():
                path = root / name
                path.write_text("mutated")
                with self.subTest(name=name), self.assertRaisesRegex(ValueError, "artifact changed"):
                    verify_artifacts(root, manifest)
                path.write_text("fixture")
            manifest["outputs"].pop()
            with self.assertRaisesRegex(ValueError, "omits"):
                verify_artifacts(root, manifest)

    def test_cache_rejects_mutated_artifact_and_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "clip"
            output.write_bytes(b"original")
            receipt = {"status": "PASS", "identity": "identity",
                       "outputs": [{"path": str(output), "sha256": file_hash(output)}]}
            self.assertTrue(receipt_valid(receipt, "identity"))
            output.write_bytes(b"changed")
            self.assertFalse(receipt_valid(receipt, "identity"))
            link = root / "link"
            link.symlink_to(output)
            receipt["outputs"] = [{"path": str(link), "sha256": file_hash(link)}]
            self.assertFalse(receipt_valid(receipt, "identity"))

    def test_final_gate_requires_matching_draft_and_real_review_binding(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            identity = "a" * 64
            target = root / "build" / identity[:16]
            with self.assertRaisesRegex(ValueError, "complete draft"):
                _final_gate(root, identity)
            film = target / "draft/film.mp4"
            film.parent.mkdir(parents=True)
            film.write_bytes(b"reviewed film fixture")
            film_hash = file_hash(film)
            write(target / "draft/manifest.json", {"identity": identity, "technical_status": "PASS",
                                                    "output": {"sha256": film_hash, "path": str(film)}})
            with self.assertRaisesRegex(ValueError, "pending"):
                _final_gate(root, identity)
            reviews = {"identity": identity, "draft_visual": "approved", "reviewer": "editor",
                       "reviewed_output_sha256": "outdated"}
            write(target / "reviews.json", reviews)
            with self.assertRaisesRegex(ValueError, "exact reviewed film"):
                _final_gate(root, identity)
            reviews["reviewed_output_sha256"] = film_hash
            write(target / "reviews.json", reviews)
            _final_gate(root, identity)
            film.write_bytes(b"changed after review")
            with self.assertRaisesRegex(ValueError, "changed or is missing"):
                _final_gate(root, identity)

    def test_workspace_files_cannot_escape_and_status_never_reads_external_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(ValueError):
                workspace_file(root, "../external", exists=False)
            self.assertEqual(status(root)["status"], "not_built")
            write(root / "build/latest.json", {"manifest": "../external"})
            with self.assertRaises((ValueError, FileNotFoundError)):
                status(root)


if __name__ == "__main__":
    unittest.main()

"""Audience contract regressions: declared text surfaces and source/caption boundaries."""

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "audience_check", ROOT / "scripts/check_audience_text.py"
)
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


class AudienceTextTest(unittest.TestCase):
    def setUp(self):
        self.authoring = {
            "episode": "audience_test",
            "title": "从一张速度图，拆出不同的信息",
            "scope": "internal version, Manim renderer; files in /Users/owner/project",
            "review": {"status": "验收通过", "path": "media/final/movie.mp4"},
            "scenes": [
                {
                    "id": "opening",
                    "title": "改动应该有多大？",
                    "sentences": [
                        {"id": "opening_01", "text": "这个子空间由两个向量生成。", "formula": None},
                        {
                            "id": "opening_02",
                            "text": "我们先验证它们是否正交。",
                            "formula": "A^*B=0",
                        },
                    ],
                },
                {
                    "id": "closing",
                    "title": "回到同一张速度图",
                    "sentences": [
                        {
                            "id": "closing_01",
                            "text": "现在再看这张速度图，我们知道哪些信息藏在局部，"
                            "哪些绕过了障碍。",
                        },
                        {"id": "closing_02", "text": "这里是知数咖啡厅，我们下次见。"},
                    ],
                },
            ],
        }
        self.source = "scripts/check_audience_text.py"
        self.manifest = {
            "schema_version": 1,
            "episode": "audience_test",
            "authoring_sha256": "test_sha",
            "coverage": {"scene_ids": ["opening", "closing"], "declared_complete": True},
            "entries": [
                {
                    "id": "opening.label",
                    "scene_id": "opening",
                    "kind": "formula",
                    "text": "连续版本：三份分量唯一；生成它们的势不必唯一",
                    "cue_ids": ["opening_01"],
                },
                {
                    "id": "closing.source",
                    "scene_id": "closing",
                    "kind": "reference",
                    "text": "Arnold, Falk & Winther · Finite Element Exterior Calculus · 2010",
                },
                {
                    "id": "closing.brand",
                    "scene_id": "closing",
                    "kind": "brand",
                    "text": "知数咖啡厅 · 我们下次见",
                    "cue_ids": ["closing_02"],
                },
            ],
            "renderer_sources": [
                {"path": self.source, "sha256": checker.sha256(ROOT / self.source)}
            ],
            "metadata": {"notes": "项目说明、验收记录与生成路径仅内部保存。"},
        }
        self.timeline = {
            "episode": "audience_test",
            "scenes": [
                {
                    "id": scene["id"],
                    "sentences": [
                        {"id": cue["id"], "text": cue["text"], "caption": cue["text"]}
                        for cue in scene["sentences"]
                    ],
                }
                for scene in self.authoring["scenes"]
            ],
        }

    def check(self, **kwargs):
        return checker.check_audience(
            self.authoring,
            display_manifest=self.manifest,
            timeline=self.timeline,
            authoring_sha256="test_sha",
            **kwargs,
        )

    def test_natural_ending_and_math_language_pass_internal_metadata_is_not_a_surface(self):
        report = self.check()
        self.assertEqual(report["status"], "DECLARED_SURFACES_TEXT_PASS")
        self.assertEqual(report["findings"], [])
        self.assertIn("不证明论证连贯", "".join(report["limitations"]))
        self.assertTrue(report["scope"]["timeline_all_scenes"])



    def test_display_linebreak_does_not_hide_internal_phrase(self):
        findings = checker.check_text("完整出处见项目\n说明，验收\n记录在工程文档。")
        self.assertIn("项目说明", {finding["match"] for finding in findings})
        self.assertIn("验收", {finding["match"] for finding in findings})

    def test_prohibited_text_cannot_hide_in_title_or_display_reference(self):
        self.authoring["title"] = "视频 V5 修订记录"
        self.manifest["entries"][1]["text"] = "完整出处见项目说明 docs/episode_math.md"
        findings = self.check()["findings"]
        self.assertTrue(any(item["location"] == "authoring.title" for item in findings))
        self.assertTrue(any(item["location"] == "display.closing.source.text" for item in findings))

    def test_stale_subtitle_caught_even_when_new_narration_is_clean(self):
        self.timeline["scenes"][-1]["sentences"][-1]["caption"] = "验证记录保存在同一份工程里。"
        report = self.check()
        self.assertEqual(report["status"], "BLOCKED")
        self.assertTrue(any("caption differs" in error for error in report["errors"]))
        self.assertTrue(any(item["channel"] == "subtitle" for item in report["findings"]))

    def test_caption_linebreak_allowed_but_omission_and_reordering_rejected(self):
        self.timeline["scenes"][0]["sentences"][0]["caption"] = "这个子空间\n由两个向量生成。"
        self.assertEqual(self.check()["status"], "DECLARED_SURFACES_TEXT_PASS")
        self.timeline["scenes"][0]["sentences"].reverse()
        self.assertEqual(self.check()["status"], "BLOCKED")
        self.timeline["scenes"][0]["sentences"].pop()
        self.assertEqual(self.check()["status"], "BLOCKED")

    def test_mismatched_source_binding_and_uncovered_scenes_rejected(self):
        cases = [
            lambda m: m.update(authoring_sha256="old_revision"),
            lambda m: m["renderer_sources"][0].update(sha256="old_source"),
            lambda m: m["coverage"].update(scene_ids=["opening"]),
            lambda m: m.update(entries=m["entries"][:1]),
            lambda m: m["entries"][0].update(cue_ids=["closing_01"]),
            lambda m: m["entries"].append(copy.deepcopy(m["entries"][0])),
        ]
        original = copy.deepcopy(self.manifest)
        for mutate in cases:
            with self.subTest(mutation=mutate):
                self.manifest = copy.deepcopy(original)
                mutate(self.manifest)
                report = self.check()
                self.assertEqual(report["status"], "BLOCKED")
                self.assertTrue(report["errors"])

    def test_sample_subset_is_explicit_and_still_requires_entire_selected_scene(self):
        self.timeline["scenes"] = self.timeline["scenes"][-1:]
        self.assertEqual(self.check()["status"], "BLOCKED")
        subset = self.check(allow_scene_subset=True)
        self.assertEqual(subset["status"], "DECLARED_SURFACES_TEXT_PASS")
        self.assertFalse(subset["scope"]["timeline_all_scenes"])
        self.assertEqual(subset["scope"]["timeline_selected_scene_ids"], ["closing"])
        self.timeline["scenes"][0]["sentences"].pop()
        self.assertEqual(self.check(allow_scene_subset=True)["status"], "BLOCKED")

    def test_empty_unknown_or_duplicated_timeline_scene_cannot_be_called_complete(self):
        for scenes in ([], [{"id": "bogus", "sentences": []}], [self.timeline["scenes"][0]] * 2):
            with self.subTest(scenes=scenes):
                timeline = {"episode": "audience_test", "scenes": scenes}
                report = checker.check_audience(
                    self.authoring, timeline=timeline, allow_scene_subset=True
                )
                self.assertEqual(report["status"], "BLOCKED")

    def test_no_manifest_gives_only_scoped_pass_and_cli_enforces_complete_inputs(self):
        report = checker.check_audience(self.authoring)
        self.assertEqual(report["status"], "SCOPED_TEXT_PASS")
        with tempfile.TemporaryDirectory() as tmp:
            authoring, report_path = Path(tmp) / "authoring.json", Path(tmp) / "report.json"
            authoring.write_text(json.dumps(self.authoring, ensure_ascii=False))
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/check_audience_text.py"),
                    "--authoring",
                    str(authoring),
                    "--require-complete",
                    "--report",
                    str(report_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(report_path.read_text())["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()

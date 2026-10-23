"""Installation-independent authoring, configuration and workspace boundaries."""

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from mathcoffee.authoring import normalize_authoring, plan_project
from mathcoffee.resources import data_path
from mathcoffee.style import preset_ids, resolve_style
from mathcoffee.workspace import init_workspace, load_project, workspace_path


def source():
    return {
        "schema_version": 1,
        "episode": "geometry",
        "title": "长度怎样比较？",
        "brief": {"audience": "高中基础", "question": "长度怎样比较？"},
        "math_states": {"equal": {"values": [2, 2]}},
        "actions": [{"id": "show_lengths", "state_ref": "equal"}],
        "scenes": [
            {
                "id": "opening",
                "title": "比较两段长度",
                "sentences": [
                    {
                        "id": "opening_01",
                        "text": "两段长度都是二。",
                        "formula": "2=2",
                        "visual": {"kind": "compare", "state_ref": "equal"},
                        "action_refs": ["show_lengths"],
                        "duration_seconds": 6,
                    }
                ],
            }
        ],
    }


class StyleTests(unittest.TestCase):
    def test_presets_preserve_format_specific_defaults_and_pending_acceptance(self):
        shorts = resolve_style("mathcoffee-shorts@1")
        longform = resolve_style("mathcoffee-longform@1")
        self.assertFalse(shorts["layout"]["caption_enabled"])
        self.assertTrue(longform["layout"]["caption_enabled"])
        self.assertEqual(shorts["colors"]["object_a"], "#4EA1FF")
        self.assertEqual(longform["colors"]["object_a"], "#65B7EE")
        self.assertEqual(shorts["voice"]["speaker"], "Serena")
        self.assertEqual(shorts["brand"], "")
        self.assertEqual(shorts["provenance"]["review_status"], "pending_author_confirmation")
        self.assertEqual(len(preset_ids()), 2)

    def test_full_style_override_is_traced_and_leaves_default_immutable(self):
        before = resolve_style("mathcoffee-shorts@1")
        custom = resolve_style(
            "mathcoffee-shorts@1",
            {
                "colors": {"object_a": "#FF8800"},
                "voice": {"speaker": "AnotherPreset"},
                "layout": {"caption_enabled": True},
                "pacing": {"formula_min_seconds": 8},
            },
            brand="自己的频道",
        )
        self.assertEqual(custom["colors"]["object_a"], "#FF8800")
        self.assertEqual(custom["voice"]["speaker"], "AnotherPreset")
        self.assertEqual(custom["brand"], "自己的频道")
        self.assertIn("style.brand", {item["path"] for item in custom["provenance"]["diff"]})
        self.assertNotEqual(
            custom["provenance"]["style_sha256"], before["provenance"]["style_sha256"]
        )
        self.assertEqual(resolve_style("mathcoffee-shorts@1"), before)

    def test_typos_identity_review_and_wrong_types_cannot_be_style_overrides(self):
        for value in (
            {"colours": {}},
            {"schema_version": 2},
            {"preset_id": "other"},
            {"provenance": {"review_status": "passed"}},
            {"layout": {"caption_enabled": "false"}},
            {"render": {"fps": True}},
            {"font": {"family": ""}},
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                resolve_style("mathcoffee-shorts@1", value)

    def test_invalid_colors_geometry_durations_and_nonfinite_values_are_rejected(self):
        for value in (
            {"colors": {"text": "white"}},
            {"layout": {"safe_rect": [0, 0, 2000, 10]}},
            {"layout": {"safe_rect": [0, 1]}},
            {"pacing": {"formula_min_seconds": 0}},
            {"voice": {"seed": -1}},
            {"voice": {"temperature": float("nan")}},
            {"voice": {"top_p": 2.0}},
            {"voice": {"max_tokens": 0}},
            {"voice": {"stream": True}},
            {"render": {"width": 1081}},
            {"render": {"draft": {"width": 500}}},
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                resolve_style("mathcoffee-shorts@1", value)

    def test_resources_are_available_and_traversal_is_rejected(self):
        self.assertTrue(data_path("presets/mathcoffee-shorts-v1.json").is_file())
        self.assertTrue(data_path("presets").is_dir())
        for value in ("../presets/file", "/tmp/file", "presets/../file", "presets\\file"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                data_path(value)


class AuthoringTests(unittest.TestCase):
    def test_legacy_adapter_preserves_identity_text_metadata_and_input(self):
        original = source()
        legacy = deepcopy(original)
        legacy["chapters"] = legacy.pop("scenes")
        legacy["chapters"][0]["cues"] = legacy["chapters"][0].pop("sentences")
        saved = deepcopy(legacy)
        self.assertEqual(normalize_authoring(legacy), original)
        self.assertEqual(legacy, saved)

    def test_bad_ids_references_ambiguous_shapes_and_duplicate_cues_fail(self):
        candidates = []
        value = source()
        value["scenes"][0]["sentences"][0]["id"] = "../escape"
        candidates.append(value)
        value = source()
        value["scenes"][0]["sentences"] *= 2
        candidates.append(value)
        value = source()
        value["chapters"] = []
        candidates.append(value)
        value = source()
        value["scenes"][0]["sentences"][0]["visual"]["state_ref"] = "missing"
        candidates.append(value)
        value = source()
        value["scenes"][0]["sentences"][0]["action_refs"] = ["missing"]
        candidates.append(value)
        value = source()
        value["scenes"][0]["sentences"][0]["action_refs"] = [{}]
        candidates.append(value)
        value = source()
        value["actions"][0]["state_ref"] = []
        candidates.append(value)
        for value in candidates:
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_authoring(value)

    def test_narration_must_match_and_mathematical_json_must_be_finite(self):
        for path, replacement in (
            ("text", ""),
            ("tts_text", "另一段正文"),
            ("duration_seconds", -1),
        ):
            value = source()
            value["scenes"][0]["sentences"][0][path] = replacement
            with self.subTest(path=path), self.assertRaises(ValueError):
                normalize_authoring(value)
        value = source()
        value["math_states"]["equal"]["values"] = [float("inf")]
        with self.assertRaises(ValueError):
            normalize_authoring(value)


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "新工程 with spaces"
        init_workspace(self.root, title="长度怎样比较？", brand="自己的频道")

    def save_source(self):
        (self.root / "authoring.json").write_text(json.dumps(source(), ensure_ascii=False))

    def test_init_refuses_existing_directory_and_preserves_original_bytes(self):
        before = (self.root / "mathcoffee.json").read_bytes()
        with self.assertRaises(FileExistsError):
            init_workspace(self.root)
        self.assertEqual((self.root / "mathcoffee.json").read_bytes(), before)

    def test_blank_project_is_explicitly_incomplete_without_models(self):
        result = plan_project(self.root)
        self.assertEqual(result["status"], "incomplete")
        self.assertTrue(result["pending"])
        self.assertEqual(result["voice_request"]["cases"], [])
        self.assertTrue((self.root / "build/plan.json").is_file())
        self.assertFalse((self.root / "media").exists())

    def test_complete_plan_preserves_text_and_changes_source_identities(self):
        self.save_source()
        first = plan_project(self.root)
        self.assertEqual(first["status"], "plan_ready")
        self.assertEqual(first["voice_request"]["cases"][0]["text"], "两段长度都是二。")
        self.assertEqual(set(first["reviews"].values()), {"pending"})
        project = load_project(self.root)
        project["style"] = {"colors": {"object_b": "#0088FF"}}
        (self.root / "mathcoffee.json").write_text(json.dumps(project))
        second = plan_project(self.root)
        self.assertNotEqual(first["source_sha256"]["project"], second["source_sha256"]["project"])
        self.assertNotEqual(first["source_sha256"]["style"], second["source_sha256"]["style"])
        self.assertEqual(first["source_sha256"]["authoring"], second["source_sha256"]["authoring"])

    def test_relative_paths_and_symlinks_cannot_escape_user_workspace(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        (self.root / "linked").symlink_to(outside, target_is_directory=True)
        for path in ("../outside/file", str(outside), "linked/file", None):
            with self.subTest(path=path), self.assertRaises(ValueError):
                workspace_path(self.root, path)

    def test_planning_does_not_accept_ambiguous_or_unsupported_empty_templates(self):
        for value in (
            {"schema_version": 2, "title": "title", "scenes": []},
            {"title": "title", "scenes": [], "chapters": []},
            [],
        ):
            (self.root / "authoring.json").write_text(json.dumps(value))
            with self.subTest(value=value), self.assertRaises(ValueError):
                plan_project(self.root)


if __name__ == "__main__":
    unittest.main()

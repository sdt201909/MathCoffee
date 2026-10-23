"""Authoring adaptation regressions without model loading or synthesis."""

import importlib.util
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "episode_voice", ROOT / "scripts/create_episode_voiceover.py"
)
VOICE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VOICE)


class EpisodeVoiceTests(unittest.TestCase):
    def setUp(self):
        self.cues = [{"id": "h01_01", "text": "沿着第一条边。"},
                     {"id": "h01_02", "text": "再走完这个圈。"}]
        self.source = {"scenes": [{"id": "h01", "sentences": self.cues}]}

    def test_both_structures_preserve_ids_text_and_order(self):
        for source in (self.source, {"chapters": [{"id": "h01", "cues": self.cues}]}):
            result = VOICE.selected_chapters(source, "sha")
            self.assertEqual(result[0]["cues"], self.cues)
            self.assertEqual(result[0]["id"], "h01")

    def test_cut_requires_frozen_source_reason_and_known_unique_ids(self):
        cut = {"source_authoring_sha256": "sha", "excluded_cues": [
            {"id": "h01_02", "reason": "Explicit editorial cut"}
        ]}
        self.assertEqual(VOICE.selected_chapters(self.source, "sha", cut)[0]["cues"],
                         self.cues[:1])
        for changed in ({**cut, "source_authoring_sha256": "other"},
                        {**cut, "excluded_cues": [{"id": "missing", "reason": "cut"}]},
                        {**cut, "excluded_cues": [{"id": "h01_02", "reason": ""}]},
                        {**cut, "excluded_cues": cut["excluded_cues"] * 2},
                        {**cut, "excluded_cues": [{"id": c["id"], "reason": "cut"}
                                                   for c in self.cues]}):
            with self.subTest(cut=changed), self.assertRaises(ValueError):
                VOICE.selected_chapters(self.source, "sha", changed)

    def test_empty_duplicate_unsafe_and_ambiguous_authoring_rejected(self):
        cases = [{"scenes": []}, {"chapters": [], "scenes": []},
                 {"scenes": self.source["scenes"] * 2}]
        for field, value in (("id", "../escape"), ("id", "H01_01"), ("text", "")):
            source = deepcopy(self.source)
            source["scenes"][0]["sentences"][0][field] = value
            cases.append(source)
        duplicate = deepcopy(self.source)
        duplicate["scenes"][0]["sentences"] *= 2
        cases.append(duplicate)
        for source in cases:
            with self.subTest(source=source), self.assertRaises(ValueError):
                VOICE.selected_chapters(source, "sha")


if __name__ == "__main__":
    unittest.main()

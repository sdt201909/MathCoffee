"""Speech planning gates; these deliberately do not claim listening acceptance."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from mathcoffee.speech.planning import (
    PronunciationError,
    apply_aliases,
    make_plan,
    patch_kokoro_phonemes,
    pronunciation_targets,
    validate_lexicon,
)
from mathcoffee.speech.providers import QwenMLXProvider, local_model_manifest, pinned_model_source

ROOT = Path(__file__).resolve().parents[1]
LEXICON = json.loads((ROOT / "src/mathcoffee/data/speech/lexicon.json").read_text())
CASES = json.loads((ROOT / "src/mathcoffee/data/speech/smoke_cases.json").read_text())["cases"]


class SpeechPlanTests(unittest.TestCase):
    def test_all_authored_cases_preserve_original_subtitles_and_pending_review(self):
        for provider in ("kokoro", "qwen_mlx"):
            for case in CASES:
                with self.subTest(provider=provider, case=case["id"]):
                    plan = make_plan(case, provider, LEXICON)
                    self.assertEqual(plan["subtitle_text"], case["text"])
                    self.assertEqual(plan["review_status"], "pending_human_listening")

    def test_context_disambiguates_same_character_and_keeps_non_target_syllables(self):
        text = "重根重新权重"
        actual, changes = patch_kokoro_phonemes(
            text, "ㄓ中4ㄍㄣ1ㄓ中4ㄒ阴1ㄑ元2ㄔ中2", LEXICON["pronunciations"]
        )
        self.assertEqual(actual, "ㄔ中2ㄍㄣ1ㄔ中2ㄒ阴1ㄑ元2ㄓ中4")
        self.assertEqual([c["character_offset"] for c in changes], [0, 2, 5])
        self.assertTrue(all(c["changed"] for c in changes))

    def test_all_required_polyphones_have_explicit_kokoro_targets(self):
        text = "每一行可行重根重新权重单调调节奇数奇怪模长"
        targets = pronunciation_targets(text, LEXICON["pronunciations"])
        self.assertEqual(
            [v["pinyin"] for _, v in sorted(targets.items())],
            ["hang2", "xing2", "chong2", "chong2", "zhong4", "diao4", "tiao2",
             "ji1", "qi2", "mo2", "chang2"],
        )

    def test_longest_context_wins_even_if_general_rule_comes_first(self):
        rules = [
            {"phrase": "重", "kokoro_targets": [{"offset": 0, "phoneme": "ㄓ中4"}]},
            {"phrase": "重根", "kokoro_targets": [{"offset": 0, "phoneme": "ㄔ中2"}]},
        ]
        self.assertEqual(pronunciation_targets("重根", rules)[0]["phoneme"], "ㄔ中2")

    def test_alignment_refuses_missing_syllables_erhua_digits_and_unknowns(self):
        for text, phonemes in (
            ("女儿", "ㄋㄩ3R"), ("重根", "ㄔ中2"), ("重根3", "ㄔ中2ㄍㄣ1"),
            ("重根 AI", "ㄔ中2ㄍㄣ1"), ("重根", "❓"), ("重根", "❓ㄔ中2ㄍㄣ1"),
        ):
            with self.subTest(text=text), self.assertRaises(PronunciationError):
                patch_kokoro_phonemes(text, phonemes, LEXICON["pronunciations"])

    def test_overrides_report_already_correct_reading_without_false_change(self):
        actual, corrections = patch_kokoro_phonemes(
            "重根", "ㄔ中2ㄍㄣ1", LEXICON["pronunciations"]
        )
        self.assertEqual(actual, "ㄔ中2ㄍㄣ1")
        self.assertFalse(corrections[0]["changed"])

    def test_qwen_gets_words_not_kokoro_phonemes(self):
        case = {"id": "example", "text": "重根重新权重"}
        plan = make_plan(case, "qwen_mlx", LEXICON)
        self.assertEqual(plan["spoken_text"], case["text"])
        self.assertIn("no_hard_phoneme_override_pronunciations_require_listening", plan["risks"])

    def test_mixed_language_is_explicit_for_kokoro_continuous_for_qwen(self):
        case = next(c for c in CASES if c["id"] == "mixed_intro")
        plan = make_plan(case, "qwen_mlx", LEXICON)
        self.assertEqual(plan["spoken_text"], case["text"])
        self.assertIn("derivative", plan["spoken_text"])
        with self.assertRaises(PronunciationError):
            make_plan({"id": "implicit", "text": case["text"]}, "kokoro", LEXICON)

    def test_inexact_language_spans_fail_before_synthesis(self):
        case = {"id": "missing", "text": "你好 hello",
                "spans": [{"language": "zh", "text": "你好"}]}
        with self.assertRaises(ValueError):
            make_plan(case, "qwen_mlx", LEXICON)

    def test_aliases_are_longest_literal_provider_specific_and_nonrecursive(self):
        rules = [
            {"source": "AA", "spoken": "B", "providers": ["qwen_mlx"]},
            {"source": "A", "spoken": "wrong", "providers": ["qwen_mlx"]},
            {"source": "B", "spoken": "recursive", "providers": ["qwen_mlx"]},
        ]
        self.assertEqual(apply_aliases("AA", rules, "qwen_mlx")[0], "B")
        self.assertEqual(apply_aliases("AA", rules, "kokoro")[0], "AA")
        self.assertEqual(apply_aliases("BAA", rules, "qwen_mlx")[0], "BAA")
        self.assertEqual(apply_aliases("13.14", LEXICON["aliases"], "kokoro")[0], "13.14")

    def test_math_spoken_forms_do_not_modify_subtitle_copy(self):
        case = next(c for c in CASES if c["id"] == "formula_acronym")
        plan = make_plan(case, "qwen_mlx", LEXICON)
        self.assertIn("三点一四", plan["spoken_text"])
        self.assertIn("艾克斯的平方加一等于零", plan["spoken_text"])
        self.assertIn("3.14", plan["subtitle_text"])
        self.assertIn("x²+1=0", plan["subtitle_text"])

    def test_alias_boundaries_do_not_rewrite_partial_literals_or_equations(self):
        for text in ("x²+1=0.5", "AI_model", "3.14.15", "1.3.14", "x²+1=0+2"):
            with self.subTest(text=text):
                self.assertEqual(apply_aliases(text, LEXICON["aliases"], "qwen_mlx")[0], text)
                plan = make_plan({"id": "partial", "text": text}, "qwen_mlx", LEXICON)
                self.assertIn("unreviewed_numeric_formula_or_identifier_text", plan["risks"])
        self.assertEqual(
            apply_aliases("x²+1=0.", LEXICON["aliases"], "qwen_mlx")[0],
            "艾克斯的平方加一等于零.",
        )

    def test_bad_lexicon_target_fails(self):
        invalid = {"schema_version": 1, "pronunciations": [{
            "phrase": "重", "kokoro_targets": [{"offset": 1, "phoneme": "ㄔ中2"}],
        }]}
        with self.assertRaises(ValueError):
            validate_lexicon(invalid)

    def test_model_identity_changes_with_content(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text('{}')
            first = local_model_manifest(directory)
            path.write_text('{"x":1}')
            second = local_model_manifest(directory)
        self.assertNotEqual(first["content_sha256"], second["content_sha256"])

    def test_model_identity_ignores_hidden_files_and_all_hidden_subtrees(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text('{}')
            first = local_model_manifest(root)
            (root / ".agent_harnesses.json").write_text('{"ephemeral":1}')
            (root / ".download_cache").mkdir()
            (root / ".download_cache/state.json").write_text('{"download":2}')
            (root / "nested").mkdir()
            (root / "nested/.other_cache").mkdir()
            (root / "nested/.other_cache/model.safetensors").write_bytes(b"not a model")
            self.assertEqual(local_model_manifest(root), first)

    def test_pinned_source_matches_content_and_never_attributes_changed_local_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = root / "model"
            model.mkdir()
            (model / "config.json").write_bytes(b'{}')
            (model / "model.safetensors").write_bytes(b"fake test weight")
            pin = root / "pin.json"
            pin.write_text(json.dumps({
                "repo": "example/fixture", "revision": "a" * 40,
                "files": [
                    {"path": "config.json", "size": 2,
                     "oid": hashlib.sha1(b"blob 2\0{}", usedforsecurity=False).hexdigest()},
                    {"path": "model.safetensors", "size": 16,
                     "lfs": {"oid": hashlib.sha256(b"fake test weight").hexdigest()}},
                ],
            }))
            identity = local_model_manifest(model)
            matched = pinned_model_source(identity, pin)
            self.assertEqual(matched["status"], "matched_pinned_source")
            self.assertEqual(matched["revision"], "a" * 40)
            (model / "model.safetensors").write_bytes(b"fake test WEIGHT")
            unverified = pinned_model_source(local_model_manifest(model), pin)
            self.assertEqual(unverified["status"], "unverified_local")
            self.assertNotIn("repo", unverified)
            self.assertNotIn("revision", unverified)

    def test_qwen_disallows_wrong_variant_and_unsupported_speed_before_imports(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text('{"tts_model_type":"base"}')
            with self.assertRaisesRegex(ValueError, "CustomVoice"):
                QwenMLXProvider({}, [], {}, directory)
            path.write_text('{"tts_model_type":"custom_voice","tts_model_size":"0b6"}')
            with self.assertRaisesRegex(ValueError, "1.7B"):
                QwenMLXProvider({"instruct": "gentle"}, [], {}, directory)
            path.write_text('{"tts_model_type":"custom_voice","tts_model_size":"1b7"}')
            with self.assertRaisesRegex(ValueError, "speed"):
                QwenMLXProvider({"speed": .9}, [], {}, directory)


if __name__ == "__main__":
    unittest.main()

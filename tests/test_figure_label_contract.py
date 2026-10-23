"""Reference identity gates: text correctness does not establish pronunciation."""

import importlib.util
import json
import unittest
from copy import deepcopy
from pathlib import Path

from mathcoffee.figure_label_contract import (
    FigureLabelError,
    make_figure_plan,
    normalize_figure_labels,
    registry_from_display_names,
    validate_figure_plan,
    validate_registry,
    visual_references,
)
from mathcoffee.speech.planning import make_plan

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "figure_label_cli", ROOT / "scripts/validate_figure_labels.py"
)
CLI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLI)
EMPTY = {"schema_version": 1, "pronunciations": [], "aliases": []}
REGISTRY = registry_from_display_names(["A", "B", "C", "A₁", "B₁", "C₁", "A′", "A₁′"])


def plan_for(text, lexicon=EMPTY):
    return make_figure_plan({"id": "test", "text": text}, "qwen_mlx", lexicon, REGISTRY)


def altered_plan(original, spoken):
    plan = plan_for(original)
    plan["spoken_text"] = spoken
    plan["spans"][0]["spoken"] = spoken
    return plan


class FigureLabelContractTests(unittest.TestCase):
    def test_registry_preserves_all_eight_distinct_referents(self):
        text = "、".join(row["glyph"] for row in REGISTRY["labels"])
        plan = plan_for(text)
        self.assertEqual(
            plan["spoken_text"], "、".join(row["spoken"] for row in REGISTRY["labels"])
        )
        self.assertEqual(plan["subtitle_text"], text)
        self.assertEqual(plan["spans"][0]["original"], text)
        self.assertEqual(len(plan["figure_label_audit"]["expansions"]), 8)
        self.assertEqual(plan["review_status"], "pending_human_listening")

    def test_normalization_offsets_refer_to_original_glyphs(self):
        text = "看A₁′，再看C。"
        result = normalize_figure_labels(text, REGISTRY)
        self.assertEqual(result["text"], "看A 下标一 撇，再看C。")
        for item in result["expansions"]:
            self.assertEqual(text[item["start"] : item["end"]], item["glyph"])

    def test_identifier_boundaries_do_not_split_words_or_abc(self):
        text = "ABC CAD AbC eigenvalue my_A A2 A_1 AB A_B Cauchy。"
        self.assertEqual(visual_references(text, REGISTRY), [])
        self.assertEqual(plan_for(text), make_plan({"id": "test", "text": text}, "qwen_mlx", EMPTY))

    def test_real_nonlabel_paragraph_and_plan_are_byte_equivalent(self):
        lexicon = json.loads((ROOT / "src/mathcoffee/data/speech/lexicon.json").read_text())
        case = {
            "id": "unchanged",
            "text": "我们先看每一行，再把局部条件与整体结构联系起来。",
            "review_questions": ["是否漏词？"],
        }
        expected = make_plan(case, "qwen_mlx", lexicon)
        actual = make_figure_plan(case, "qwen_mlx", lexicon, REGISTRY)
        self.assertEqual(
            json.dumps(actual, ensure_ascii=False), json.dumps(expected, ensure_ascii=False)
        )
        self.assertNotIn("figure_label_audit", actual)

    def test_malicious_lexicon_cannot_rename_even_expanded_labels(self):
        for source, spoken, text in [("A", "甲", "看A₁。"), ("C", "B", "从A去C。")]:
            lexicon = deepcopy(EMPTY)
            lexicon["aliases"].append(
                {
                    "source": source,
                    "spoken": spoken,
                    "kind": "spoken_form",
                    "providers": ["qwen_mlx"],
                }
            )
            with self.subTest(source=source), self.assertRaises(FigureLabelError):
                plan_for(text, lexicon)

    def test_missing_repeated_reordered_and_wrong_letter_rejected(self):
        original = "从A经过B到C，再回A。"
        for spoken in (
            "从A经过B，再回A。",
            "从A经过B到C再到C，再回A。",
            "从B经过A到C，再回A。",
            "从A经过B到B，再回A。",
        ):
            with self.subTest(spoken=spoken), self.assertRaises(FigureLabelError):
                validate_figure_plan(original, altered_plan(original, spoken), REGISTRY)

    def test_case_subscript_prime_and_raw_glyph_loss_rejected(self):
        for original, spoken in [
            ("看A。", "看a。"),
            ("看A₁。", "看A。"),
            ("看A′。", "看A。"),
            ("看A₁′。", "看A 下标一。"),
            ("看A₁。", "看A₁。"),
            ("看A₁。", "看A 下标二。"),
            ("看A₁。", "看A下标一。"),
        ]:
            with self.subTest(spoken=spoken), self.assertRaises(FigureLabelError):
                validate_figure_plan(original, altered_plan(original, spoken), REGISTRY)

    def test_forbidden_aliases_rejected_in_original_and_actual_plan(self):
        for alias in ("甲", "乙", "丙"):
            with self.subTest(alias=alias), self.assertRaises(FigureLabelError):
                plan_for(f"从{alias}出发。")
            with self.assertRaises(FigureLabelError):
                validate_figure_plan(
                    "从A出发。", altered_plan("从A出发。", f"从{alias}出发。"), REGISTRY
                )

    def test_invalid_visual_case_prime_and_unknown_subscript_rejected(self):
        for text in ("看a。", "看A'。", "看A₂。"):
            with self.subTest(text=text), self.assertRaises(FigureLabelError):
                plan_for(text)

    def test_subtitle_or_actual_span_tampering_rejected(self):
        plan = plan_for("看A₁。")
        for key, value in (("subtitle_text", "看A 下标一。"), ("spoken_text", "看B。")):
            changed = {**deepcopy(plan), key: value}
            with self.assertRaises(FigureLabelError):
                validate_figure_plan("看A₁。", changed, REGISTRY)

    def test_explicit_language_spans_restore_originals(self):
        case = {
            "id": "spans",
            "text": "看A₁，then C。",
            "spans": [{"language": "zh", "text": "看A₁，"}, {"language": "en", "text": "then C。"}],
        }
        plan = make_figure_plan(case, "qwen_mlx", EMPTY, REGISTRY)
        self.assertEqual([s["original"] for s in plan["spans"]], [s["text"] for s in case["spans"]])
        self.assertEqual(plan["spoken_text"], "看A 下标一，then C。")

    def test_registry_cannot_declare_alias_as_approved_spoken_form(self):
        registry = deepcopy(REGISTRY)
        registry["labels"][0]["spoken"] = "甲"
        with self.assertRaises(FigureLabelError):
            validate_registry(registry)

    def test_general_factory_supports_additional_letters(self):
        registry = registry_from_display_names(["X", "Y₂", "Z′"], forbidden_aliases=[])
        case = {"id": "other", "text": "X与Y₂到Z′。"}
        self.assertEqual(
            make_figure_plan(case, "qwen_mlx", EMPTY, registry)["spoken_text"],
            "X与Y 下标二到Z 撇。",
        )

    def test_cli_checks_real_request_sequence_and_coverage(self):
        authoring = {
            "scenes": [
                {
                    "id": "v01",
                    "sentences": [
                        {"id": "v01_01", "text": "从A出发。", "voice_block": "v01_b01"},
                        {"id": "v01_02", "text": "最后到C。", "voice_block": "v01_b01"},
                    ],
                }
            ]
        }
        block = {"id": "v01_b01", "text": "从A出发。最后到C。"}
        plan = make_figure_plan(block, "qwen_mlx", EMPTY, REGISTRY)
        request = {"plans": [{"id": "v01", "plans": [plan]}]}
        self.assertEqual(
            CLI.check(authoring, REGISTRY, EMPTY, request=request)["request_plans_checked"], 1
        )
        request["plans"][0]["plans"][0] = {
            **altered_plan(block["text"], "从A出发。最后到B。"),
            "id": block["id"],
        }
        with self.assertRaises(FigureLabelError):
            CLI.check(authoring, REGISTRY, EMPTY, request=request)
        with self.assertRaises(FigureLabelError):
            CLI.check(authoring, REGISTRY, EMPTY, request={"plans": []})

    def test_cli_rejects_complete_but_reordered_plans(self):
        cues = [{"id": "first", "text": "先看A。"}, {"id": "second", "text": "再看C。"}]
        authoring = {"scenes": [{"id": "chapter", "sentences": cues}]}
        plans = [make_figure_plan(cue, "qwen_mlx", EMPTY, REGISTRY) for cue in cues]
        self.assertEqual(
            CLI.check(authoring, REGISTRY, EMPTY, request={"plans": plans})[
                "request_plans_checked"
            ],
            2,
        )
        with self.assertRaisesRegex(FigureLabelError, "order"):
            CLI.check(authoring, REGISTRY, EMPTY, request={"plans": plans[::-1]})

    def test_cli_model_registry_uses_display_names_not_internal_names(self):
        world = {"vertex_names": ["internal_a", "internal_b"],
                 "vertex_display_names": ["X", "Y"],
                 "cut_strip": {"vertex_names": ["internal_a′"]}}
        self.assertEqual(CLI.model_display_names(world), {"X", "Y", "X′"})


if __name__ == "__main__":
    unittest.main()

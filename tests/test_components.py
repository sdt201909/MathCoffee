"""Component input semantics; object/encoded-frame review remains separate."""

import unittest

from manim import Line
from mathcoffee.components import build_visual, finite_point, math_template, referenced_visual, semantic_anchor


class ComponentInputTests(unittest.TestCase):
    def test_polyline_preserves_intermediate_vertices_and_vector_has_two_endpoints(self):
        class Layout:
            style = {"colors": {"object_a": "#4EA1FF", "object_b": "#70E1E8"}}

            def rect(self, _name):
                return [0, 0, 100, 100]

            def place(self, item, *_args):
                return item

        cue = {"id": "bent", "visual": {"kind": "polyline", "points": [[0, 0], [1, 1], [2, 0]]}}
        visual = build_visual(Layout(), cue, {})
        segments = [part for part in visual if isinstance(part, Line)]
        self.assertEqual(len(segments), 2)
        self.assertTrue((segments[0].get_end() == segments[1].get_start()).all())
        cue["visual"]["kind"] = "vector"
        with self.assertRaisesRegex(ValueError, "exactly two"):
            build_visual(Layout(), cue, {})

    def test_geometry_references_use_shared_state_without_eval(self):
        state = {"positions": {"points": [[0, 0], [2, 1]], "labels": ["A", "B"]}}
        cue = {"id": "cue", "text": "两个点。", "visual": {"kind": "vector", "state_ref": "positions"}}
        result = referenced_visual(cue, state)
        self.assertEqual(result["points"], state["positions"]["points"])
        self.assertEqual(result["kind"], "vector")
        self.assertEqual(result["labels"], ["A", "B"])

    def test_missing_state_and_nonfinite_geometry_are_rejected(self):
        with self.assertRaises(ValueError):
            referenced_visual({"visual": {"state_ref": "missing"}}, {})
        for point in ([1], [1, 2, 3], [0, float("nan")], [float("inf"), 1]):
            with self.subTest(point=point), self.assertRaises(ValueError):
                finite_point(point)
        self.assertEqual(finite_point([1, 2]), (1.0, 2.0))

    def test_narration_is_not_used_as_default_screen_text(self):
        cue = {"id": "cue", "text": "这段是完整旁白，不应自动铺满画面。"}
        self.assertEqual(referenced_visual(cue, {})["text"], "")
        cue["formula"] = "x^2+1=0"
        self.assertEqual(referenced_visual(cue, {})["kind"], "formula")

    def test_math_font_is_used_by_xelatex_and_injection_is_rejected(self):
        template, receipt = math_template("Latin Modern Math")
        self.assertEqual(template.tex_compiler, "xelatex")
        self.assertEqual(template.output_format, ".xdv")
        self.assertIn("\\setmathfont{latinmodern-math.otf}", template.preamble)
        self.assertEqual(receipt["requested"], "Latin Modern Math")
        self.assertEqual(receipt["resolved"], "latinmodern-math.otf")
        for invalid in ("", "font}\\input{secret}", "name\ncommand", "/path/font.otf"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                math_template(invalid)

    def test_unimplemented_actions_are_not_reported_as_executed(self):
        self.assertEqual(semantic_anchor({"id": "anchor", "fraction": .25}), .25)
        for event in ({"type": "translate"}, {"type": "highlight"}, {"fraction": True},
                      {"fraction": float("nan")}, {"fraction": 2}):
            with self.subTest(event=event), self.assertRaises(ValueError):
                semantic_anchor(event)


if __name__ == "__main__":
    unittest.main()

"""Data-driven Manim components and measured display receipts.

Import this module only in the rendering interpreter. Planning has no Manim dependency.
The components draw supplied states; they never evaluate mathematical source strings.
"""

from __future__ import annotations

import json
import math
import os
import hashlib
from pathlib import Path
from typing import Any

import numpy as np
from manim import (
    Arrow, Dot, FadeIn, FadeOut, Line, MathTex,
    Scene, SurroundingRectangle, TexTemplate, Text, VGroup, config,
)
import manimpango

from .pipeline import resolve_visual


def finite_point(value: Any) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("a plotted point needs exactly two coordinates")
    result = tuple(float(v) for v in value)
    if not all(math.isfinite(v) for v in result):
        raise ValueError("plotted coordinates must be finite")
    return result


def select_font(style: dict) -> dict:
    available = set(manimpango.list_fonts())
    requested = style["font"]["family"]
    candidates = [requested, *style["font"].get("fallbacks", [])]
    selected = next((name for name in candidates if name in available), None)
    if selected is None:
        raise ValueError(f"requested fonts are unavailable: {', '.join(candidates)}")
    return {"requested": requested, "resolved": selected,
            "fallback_used": selected != requested}


def referenced_visual(cue: dict, states: dict) -> dict:
    return resolve_visual(cue, states)


def math_template(font: str) -> tuple[TexTemplate, dict]:
    """Use a real OpenType math font, without accepting TeX through a font name."""
    if (not isinstance(font, str) or not font.strip() or len(font) > 120
            or any(not (character.isalnum() or character in " ._-") for character in font)):
        raise ValueError("formula font must be a plain installed font name")
    # TeX Live ships this face in its own font tree, outside macOS Font Book.
    # Using its OpenType filename lets kpathsea locate the same requested face.
    resolved = "latinmodern-math.otf" if font == "Latin Modern Math" else font
    preamble = ("\\usepackage{amsmath}\n\\usepackage{fontspec}\n"
                "\\usepackage{unicode-math}\n\\setmathfont{" + resolved + "}")
    template = TexTemplate(tex_compiler="xelatex", output_format=".xdv", preamble=preamble)
    receipt = {"requested": font, "resolved": resolved, "compiler": "xelatex", "output_format": ".xdv",
               "preamble": preamble, "preamble_sha256": hashlib.sha256(preamble.encode()).hexdigest(),
               "fallback_policy": "none; missing requested math font fails compilation"}
    return template, receipt


def semantic_anchor(event: dict) -> float:
    if event.get("type", "semantic_anchor") != "semantic_anchor":
        raise ValueError("standard components only support semantic_anchor; implement other actions in a custom scene")
    value = event.get("fraction", 0.5)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("semantic action fraction must lie in [0,1]")
    return float(value)


class SceneBase(Scene):
    """Pixel-addressed layout and records shared by standard and custom scenes."""

    def setup(self):
        super().setup()
        self.payload = json.loads(Path(os.environ["MATHCOFFEE_SCENE_INPUT"]).read_text())
        self.style = self.payload["style"]
        self.font_receipt = select_font(self.style)
        self.math_tex_template, self.math_font_receipt = math_template(self.style["font"]["formula"])
        self.display_entries: list[dict] = []
        self.layout_entries: list[dict] = []
        self.action_entries: list[dict] = []
        self.scene_id = self.payload["scene"]["id"]
        self.camera.background_color = self.style["colors"]["background"]
        width, height = self.style["render"]["width"], self.style["render"]["height"]
        self.reference_width, self.reference_height = width, height
        self.units_per_pixel = float(config.frame_width) / width

    def coordinate(self, x: float, y: float) -> np.ndarray:
        return np.array([(x - self.reference_width / 2) * self.units_per_pixel,
                         (self.reference_height / 2 - y) * self.units_per_pixel, 0.0])

    def rect(self, name: str) -> list[float]:
        return list(self.style["layout"][name])

    def register_text(self, identifier: str, text: str, kind: str, cue_id: str) -> None:
        if not isinstance(text, str) or not text.strip():
            return
        if any(entry["id"] == identifier for entry in self.display_entries):
            raise ValueError(f"display ID is duplicated: {identifier}")
        self.display_entries.append({"id": identifier, "scene_id": self.scene_id,
                                     "kind": kind, "text": text, "cue_ids": [cue_id]})

    def place(self, group, rectangle: list[float], identifier: str, cue_id: str):
        x, y, width, height = rectangle
        max_width, max_height = width * self.units_per_pixel, height * self.units_per_pixel
        factor = min(1.0, max_width / max(float(group.width), 1e-12),
                     max_height / max(float(group.height), 1e-12))
        if factor < 1:
            group.scale(factor)
        group.move_to(self.coordinate(x + width / 2, y + height / 2))
        center = group.get_center()
        left = center[0] / self.units_per_pixel + self.reference_width / 2 - group.width / self.units_per_pixel / 2
        top = self.reference_height / 2 - center[1] / self.units_per_pixel - group.height / self.units_per_pixel / 2
        actual = [float(left), float(top), float(group.width / self.units_per_pixel),
                  float(group.height / self.units_per_pixel)]
        within = (actual[0] >= x - 0.01 and actual[1] >= y - 0.01
                  and actual[0] + actual[2] <= x + width + 0.01
                  and actual[1] + actual[3] <= y + height + 0.01)
        self.layout_entries.append({"id": identifier, "cue_id": cue_id,
                                    "allocated_rect": rectangle, "actual_rect": actual,
                                    "fit_scale": factor, "inside_allocated_rect": within})
        if not within:
            raise ValueError(f"component exceeds its allocated rectangle: {identifier}")
        if factor < 0.5:
            raise ValueError(f"component needs excessive shrinking; shorten/reflow it: {identifier}")
        return group

    def label(self, text: str, cue_id: str, suffix: str, *, color=None, kind="label", size=None):
        self.register_text(f"{cue_id}.{suffix}", text, kind, cue_id)
        return Text(text, font=self.font_receipt["resolved"],
                    font_size=size or self.style["layout"]["font_sizes"]["body"],
                    color=color or self.style["colors"]["text"])

    def formula(self, text: str, cue_id: str, suffix="formula"):
        if any("\u4e00" <= char <= "\u9fff" for char in text):
            raise ValueError("Chinese prose belongs in Text, not a MathTex expression")
        self.register_text(f"{cue_id}.{suffix}", text, "formula", cue_id)
        try:
            return MathTex(text, font_size=self.style["layout"]["font_sizes"]["formula"],
                           tex_template=self.math_tex_template,
                           color=self.style["colors"]["result"])
        except ValueError as error:
            raise ValueError(f"formula rendering with requested math font {self.math_font_receipt['requested']!r} failed; install that font and the XeLaTeX unicode-math toolchain") from error

    def title(self, text: str, cue_id: str):
        return self.place(self.label(text, cue_id, "title", kind="heading",
                                     size=self.style["layout"]["font_sizes"]["title"]),
                          self.rect("title_rect"), f"{cue_id}.title", cue_id)

    def register_action(self, cue_id: str, identifier: str, frame: int, **metadata):
        self.action_entries.append({"id": identifier, "cue_id": cue_id,
                                    "scene_id": self.scene_id, "local_frame": int(frame),
                                    **metadata})

    def write_receipt(self):
        receipt = {"schema_version": 1, "scene_id": self.scene_id,
                   "font": self.font_receipt, "entries": self.display_entries,
                   "formula_font": self.math_font_receipt,
                   "layout": self.layout_entries, "actions": self.action_entries,
                   "executed_scene_seconds": float(self.time),
                   "measurement_scope": "Manim object bounds; executed scene duration is checked against encoded frames. Semantic anchors are schedule declarations, not observed actions."}
        Path(self.payload["receipt"]).write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")


class FormulaStage(VGroup):
    def __init__(self, scene: SceneBase, text: str, cue_id: str):
        super().__init__(scene.formula(text, cue_id))


class Compare(VGroup):
    def __init__(self, scene: SceneBase, left: str, right: str, cue_id: str):
        colors = scene.style["colors"]
        a = scene.label(left, cue_id, "left", color=colors["object_a"])
        b = scene.label(right, cue_id, "right", color=colors["object_b"])
        super().__init__(a, b)
        self.arrange_in_grid(rows=2 if scene.reference_height > scene.reference_width else 1,
                             buff=0.7)


class StateReadout(VGroup):
    def __init__(self, scene: SceneBase, values: dict, cue_id: str):
        if not isinstance(values, dict) or not values:
            raise ValueError("state_readout needs a nonempty values object")
        labels = [scene.label(f"{key} = {value}", cue_id, f"value_{index}")
                  for index, (key, value) in enumerate(values.items())]
        super().__init__(*labels)
        self.arrange_in_grid(cols=1, buff=0.35)


class Emphasis(VGroup):
    def __init__(self, scene: SceneBase, text: str, cue_id: str):
        label = scene.label(text, cue_id, "emphasis", color=scene.style["colors"]["result"])
        border = SurroundingRectangle(label, color=scene.style["colors"]["result"], buff=0.3)
        super().__init__(border, label)


class Summary(VGroup):
    def __init__(self, scene: SceneBase, lines: list[str], cue_id: str, *, reference=False):
        if not isinstance(lines, list) or not lines or not all(isinstance(v, str) and v.strip() for v in lines):
            raise ValueError("summary/reference needs nonempty display lines")
        labels = [scene.label(text, cue_id, f"line_{index}",
                              kind="reference" if reference else "label")
                  for index, text in enumerate(lines)]
        super().__init__(*labels)
        self.arrange_in_grid(cols=1, buff=0.4)


class References(Summary):
    def __init__(self, scene: SceneBase, lines: list[str], cue_id: str):
        super().__init__(scene, lines, cue_id, reference=True)


def build_visual(scene: SceneBase, cue: dict, states: dict):
    visual = referenced_visual(cue, states)
    cue_id, kind = cue["id"], visual["kind"]
    colors = scene.style["colors"]
    if kind == "formula":
        item = FormulaStage(scene, visual["text"], cue_id)
    elif kind in {"text", "title"}:
        if not visual.get("text"):
            raise ValueError(f"cue {cue_id} needs visual text, a formula, or a supported visual")
        item = scene.label(visual["text"], cue_id, "body")
    elif kind == "compare":
        item = Compare(scene, str(visual["left"]), str(visual["right"]), cue_id)
    elif kind in {"state", "state_readout"}:
        item = StateReadout(scene, visual["values"], cue_id)
    elif kind == "emphasis":
        if not visual.get("text"):
            raise ValueError("emphasis needs nonempty display text")
        item = Emphasis(scene, visual["text"], cue_id)
    elif kind in {"summary", "references"}:
        item = (References if kind == "references" else Summary)(scene, visual["lines"], cue_id)
    elif kind in {"points", "line", "polyline", "vector"}:
        points = [finite_point(point) for point in visual.get("points", [])]
        if not points or kind in {"line", "polyline", "vector"} and len(points) < 2:
            raise ValueError("point/line/vector visual has too few points")
        if kind == "vector" and len(points) != 2:
            raise ValueError("a vector requires exactly two endpoints")
        minimum = np.min(np.array(points), axis=0)
        maximum = np.max(np.array(points), axis=0)
        extent = np.maximum(maximum - minimum, 1)
        center = (minimum + maximum) / 2
        normalized = [(np.array([*(np.array(point) - center), 0.0]) * (3 / max(extent))) for point in points]
        dots = VGroup(*[Dot(point, color=colors["object_a"], radius=0.075) for point in normalized])
        item = VGroup(dots)
        if kind == "vector":
            item.add(Arrow(normalized[0], normalized[1], color=colors["object_b"], buff=0))
        elif kind in {"line", "polyline"}:
            item.add(*[Line(start, end, color=colors["object_b"], buff=0)
                       for start, end in zip(normalized, normalized[1:])])
        labels = visual.get("labels", [])
        if labels and len(labels) != len(points):
            raise ValueError("point labels must match supplied points")
        for index, (label, point) in enumerate(zip(labels, normalized)):
            item.add(scene.label(label, cue_id, f"point_{index}", size=30).next_to(point, direction=np.array([0, 1, 0]), buff=0.15))
    else:
        raise ValueError(f"unsupported visual kind {kind!r}; use an explicit custom scene module")
    rectangle = scene.rect("formula_rect" if kind == "formula" else "visual_rect")
    item = scene.place(item, rectangle, f"{cue_id}.visual", cue_id)
    formula = cue.get("formula")
    if formula and kind != "formula":
        item.add(scene.place(FormulaStage(scene, formula, cue_id), scene.rect("formula_rect"),
                             f"{cue_id}.formula_stage", cue_id))
    return item


class ProjectScene(SceneBase):
    """Execute measured sentence slots without inventing actions or narration."""

    def construct(self):
        scene = self.payload["scene"]
        fps = self.payload["fps"]
        events = {event["id"]: event for event in self.payload.get("actions", [])}
        cursor = 0
        for cue in scene["sentences"]:
            slot = cue["slot"]
            if slot["start_frame"] > cursor:
                self.wait((slot["start_frame"] - cursor) / fps)
            item = build_visual(self, cue, self.payload.get("math_states", {}))
            frames = slot["duration_frames"]
            transition = min(round(self.style["pacing"]["transition_seconds"] * fps), frames // 4)
            if transition:
                self.play(FadeIn(item), run_time=transition / fps)
            else:
                self.add(item)
            for identifier in cue.get("action_refs", []):
                event = events[identifier]
                fraction = semantic_anchor(event)
                self.register_action(cue["id"], identifier,
                                     slot["start_frame"] + round(fraction * frames),
                                     state_ref=event.get("state_ref"),
                                     action_type=event.get("type", "semantic_anchor"),
                                     registration_scope="declared semantic anchor derived from the measured PCM schedule; not an observed action")
            self.wait(max(0, frames - 2 * transition) / fps)
            if transition:
                self.play(FadeOut(item), run_time=transition / fps)
            else:
                self.remove(item)
            cursor = slot["start_frame"] + frames
        if cursor < self.payload["duration_frames"]:
            self.wait((self.payload["duration_frames"] - cursor) / fps)
        self.write_receipt()

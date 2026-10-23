"""Versioned style candidates shared by mathematical scenes and compositors.

Style settings control presentation. Mathematical correctness, audience checks,
source identity and human acceptance are independent production requirements.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from copy import deepcopy
from typing import Any

from .resources import data_path

_PRESETS = {
    "mathcoffee-shorts@1": "presets/mathcoffee-shorts-v1.json",
    "mathcoffee-longform@1": "presets/mathcoffee-longform-v1.json",
}
_CONFIGURABLE = {
    "colors",
    "font",
    "layout",
    "pacing",
    "voice",
    "music",
    "narrative",
    "render",
}


def preset_ids() -> tuple[str, ...]:
    return tuple(_PRESETS)


def json_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


def _merge(default: Any, override: Any, location: str, diff: list[dict]) -> Any:
    if isinstance(default, dict):
        if not isinstance(override, dict):
            raise ValueError(f"{location}: expected an object")
        unknown = set(override) - set(default)
        if unknown:
            raise ValueError(f"{location}: unknown fields {sorted(unknown)}")
        result = deepcopy(default)
        for key, value in override.items():
            result[key] = _merge(default[key], value, f"{location}.{key}", diff)
        return result
    expected = type(default)
    if expected in (int, float) and expected is not bool:
        valid = type(override) in (int, float) and math.isfinite(override)
        if expected is int:
            valid = valid and type(override) is int
    else:
        valid = type(override) is expected
    if not valid:
        raise ValueError(f"{location}: expected {expected.__name__}")
    if isinstance(default, list):
        if len(default) == 4 and all(type(v) in (int, float) for v in default):
            if len(override) != 4 or any(
                type(v) not in (int, float) or not math.isfinite(v) for v in override
            ):
                raise ValueError(f"{location}: expected four finite coordinates")
        elif any(not isinstance(v, str) or not v.strip() for v in override):
            raise ValueError(f"{location}: expected nonempty text items")
    if default != override:
        diff.append({"path": location, "default": deepcopy(default), "value": deepcopy(override)})
    return deepcopy(override)


def _positive(value: Any, location: str, *, zero: bool = False) -> None:
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or (value < 0 if zero else value <= 0)
    ):
        raise ValueError(
            f"{location}: expected {'nonnegative' if zero else 'positive'} finite number"
        )


def validate_style(style: dict) -> None:
    """Validate configuration geometry and semantics, never grant visual acceptance."""
    for key, value in style["colors"].items():
        if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise ValueError(f"colors.{key}: expected #RRGGBB")
    render = style["render"]
    portrait = style["preset_id"].startswith("mathcoffee-shorts")
    for quality in (render, render["draft"]):
        for key in ("width", "height", "fps"):
            if type(quality[key]) is not int or quality[key] <= 0:
                raise ValueError(f"render.{key}: expected positive integer")
        minimum = (180, 320) if portrait else (320, 180)
        if quality["width"] < minimum[0] or quality["height"] < minimum[1]:
            raise ValueError("render dimensions are below the composition minimum")
        if quality["width"] % 2 or quality["height"] % 2 or quality["fps"] > 120:
            raise ValueError("render requires even dimensions and FPS <= 120")
        if quality["width"] * render["height"] != quality["height"] * render["width"]:
            raise ValueError("draft and final aspect ratios must match")
    if (
        render["width"] * 16 != render["height"] * 9
        if portrait
        else render["width"] * 9 != render["height"] * 16
    ):
        raise ValueError("preset aspect ratio must remain 9:16 or 16:9")
    for name, rect in style["layout"].items():
        if not name.endswith("_rect"):
            continue
        x, y, width, height = rect
        if x < 0 or y < 0 or width <= 0 or height <= 0:
            raise ValueError(f"layout.{name}: invalid rectangle")
        if x + width > render["width"] or y + height > render["height"]:
            raise ValueError(f"layout.{name}: rectangle exceeds canvas")
    for name, size in style["layout"]["font_sizes"].items():
        _positive(size, f"layout.font_sizes.{name}")
    for name, duration in style["pacing"].items():
        _positive(duration, f"pacing.{name}", zero=name == "transition_seconds")
    if any(
        not isinstance(style["font"][name], str) or not style["font"][name].strip()
        for name in ("family", "formula")
    ):
        raise ValueError("font families must be nonempty")
    voice = style["voice"]
    if type(voice["seed"]) is not int or not 0 <= voice["seed"] < 2**32:
        raise ValueError("voice.seed must be uint32")
    for name in ("provider", "profile", "speaker", "language", "text_conditioning"):
        if not voice[name].strip():
            raise ValueError(f"voice.{name}: expected nonempty text")
    _positive(voice["temperature"], "voice.temperature", zero=True)
    for name in ("top_k", "max_tokens"):
        if type(voice[name]) is not int or voice[name] <= 0:
            raise ValueError(f"voice.{name} must be a positive integer")
    _positive(voice["repetition_penalty"], "voice.repetition_penalty")
    if not 0 < voice["top_p"] <= 1:
        raise ValueError("voice.top_p must be in (0, 1]")
    if voice["stream"] is not False:
        raise ValueError("production voice requests require a complete waveform, stream=false")
    _positive(style["music"]["duck_db"], "music.duck_db", zero=True)
    if type(style["music"]["seed"]) is not int or not 0 <= style["music"]["seed"] < 2**32:
        raise ValueError("music.seed must be uint32")
    if type(style["layout"]["caption_enabled"]) is not bool:
        raise ValueError("layout.caption_enabled must be a boolean")


def resolve_style(preset: str, overrides: dict | None = None, brand: str | None = None) -> dict:
    """Resolve a built-in candidate plus strict overrides and record every difference."""
    if preset not in _PRESETS:
        raise ValueError(f"unknown style preset: {preset}; choose from {', '.join(_PRESETS)}")
    if overrides is None:
        overrides = {}
    if not isinstance(overrides, dict):
        raise ValueError("style overrides must be an object")
    prohibited = set(overrides) - _CONFIGURABLE
    if prohibited:
        raise ValueError(f"style overrides cannot set {sorted(prohibited)}")
    base = json.loads(data_path(_PRESETS[preset]).read_text())
    diff: list[dict] = []
    result = _merge(base, overrides, "style", diff)
    if brand is not None:
        if not isinstance(brand, str):
            raise ValueError("brand must be text")
        if result["brand"] != brand:
            diff.append({"path": "style.brand", "default": result["brand"], "value": brand})
        result["brand"] = brand
    validate_style(result)
    digest = json_sha256(result)
    result["provenance"] = {
        "preset_id": preset,
        "preset_version": result["preset_version"],
        "overrides": deepcopy(overrides),
        "diff": diff,
        "style_sha256": digest,
        "review_status": "pending_author_confirmation",
        "review_scope": "configuration only; no visual or listening acceptance implied",
    }
    return result

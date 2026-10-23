#!/usr/bin/env python3
"""Validate opted-in authoring and actual normalized request plans, offline."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mathcoffee.figure_label_contract import (  # noqa: E402
    FigureLabelError,
    make_figure_plan,
    registry_sha256,
    validate_figure_plan,
    validate_registry,
    visual_references,
)


def read(path):
    return json.loads(Path(path).read_text())


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def model_display_names(world):
    """Resolve cut-copy names through the model's declared base display map."""
    display = world.get("vertex_display_names")
    internal = world.get("vertex_names")
    if not display or not internal or len(display) != len(internal):
        raise FigureLabelError("world requires aligned vertex_names/vertex_display_names")
    mapping = dict(zip(internal, display, strict=True))
    names = list(display)
    for name in world.get("cut_strip", {}).get("vertex_names", []):
        bare = name.rstrip("′")
        if bare not in mapping:
            raise FigureLabelError(f"cut vertex lacks a model display mapping: {name}")
        names.append(mapping[bare] + name[len(bare) :])
    return set(names)


def flatten_plans(request):
    rows = request.get("plans")
    if not isinstance(rows, list):
        raise FigureLabelError("request requires actual plans")
    return [p for row in rows for p in (row["plans"] if "plans" in row else [row])]


def check(authoring, registry, lexicon, *, request=None, world=None):
    registered = set(validate_registry(registry))
    if world is not None and registered != model_display_names(world):
        raise FigureLabelError("registry glyphs differ from actual model vertex display names")
    cues = [cue for chapter in authoring["scenes"] for cue in chapter["sentences"]]
    by_id = {cue["id"]: cue for cue in cues}
    if len(by_id) != len(cues):
        raise FigureLabelError("duplicate authoring cue IDs")
    blocks = {}
    for cue in cues:
        if cue.get("voice_block"):
            blocks.setdefault(cue["voice_block"], []).append(cue["text"])
    blocks = {key: "".join(texts) for key, texts in blocks.items()}
    mentions = []
    for cue in cues:
        refs = visual_references(cue["text"], registry)
        # Also exercise the actual frozen lexicon, including malicious aliases.
        make_figure_plan(cue, "qwen_mlx", lexicon, registry)
        if refs:
            mentions.append({"id": cue["id"], "references": [r["glyph"] for r in refs]})
    result = {
        "cue_count": len(cues),
        "labelled_cues": mentions,
        "registry_sha256": registry_sha256(registry),
        "request_plans_checked": 0,
    }
    if request is not None:
        if request.get("figure_label_registry", registry) != registry:
            raise FigureLabelError("request registry differs from authoring")
        plans = flatten_plans(request)
        plan_ids = [plan["id"] for plan in plans]
        if len(set(plan_ids)) != len(plan_ids):
            raise FigureLabelError("duplicate actual request plan IDs")
        if set(plan_ids) == set(by_id):
            expected = {key: cue["text"] for key, cue in by_id.items()}
        elif blocks and set(plan_ids) == set(blocks):
            expected = blocks
        else:
            raise FigureLabelError("request plans must completely cover authoring cues or blocks")
        if plan_ids != list(expected):
            raise FigureLabelError("request plan order differs from authoring reference order")
        for plan in plans:
            validate_figure_plan(expected[plan["id"]], plan, registry)
        result["request_plans_checked"] = len(plans)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authoring", type=Path, required=True)
    parser.add_argument("--request", type=Path)
    parser.add_argument(
        "--registry", type=Path, help="Otherwise use authoring.figure_label_registry"
    )
    parser.add_argument("--world", "--model", type=Path, help="Frozen world JSON, never a video")
    parser.add_argument("--lexicon", type=Path, default=ROOT / "assets/speech/lexicon.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = {"scope": "Text/normalization contract only; no audio listening or model loading"}
    try:
        authoring = read(args.authoring)
        registry = read(args.registry) if args.registry else authoring.get("figure_label_registry")
        report.update(
            check(
                authoring,
                registry,
                read(args.lexicon),
                request=read(args.request) if args.request else None,
                world=read(args.world) if args.world else None,
            )
        )
        report["passed"] = True
        report["input_sha256"] = {
            str(path): sha256(path)
            for path in (args.authoring, args.request, args.registry, args.world, args.lexicon)
            if path is not None
        }
    except (FigureLabelError, ValueError, KeyError, TypeError, OSError) as error:
        report.update({"passed": False, "error": str(error)})
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

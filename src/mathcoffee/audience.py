#!/usr/bin/env python3
"""Check declared audience text, never recursively scan engineering metadata.

This is a text leakage / provenance guard, not a narrative comprehension test.
Renderers must consume the same display registry that exports the manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path.cwd()
DISPLAY_KINDS = {"heading", "label", "formula", "reference", "brand"}
LIMITATIONS = [
    "仅检查明确登记的旁白、字幕和显示文字；不证明未登记的画面文字已完整覆盖。",
    "规则命中用于发现制作话语泄漏；无命中不证明论证连贯或观众理解。",
    "不读取音视频，不替代实际编码画面检查、听审或字幕与实际音轨对照。",
]
# Deliberately contextual: 生成、验证、版本、工程 alone have valid mathematical uses.
# Cryptographic hashes and mathematical checks are audience content in their
# own right; only their engineering receipt/workflow contexts are prohibited.
# No automatic allowlist: a reported occurrence must be rewritten or explicitly
# discussed in the separate editorial review, never silently waived by a flag.
RULES = (
    (
        "production_reference",
        r"项目(?:说明|文档|记录|文件|源码|路径)|本项目|本期制作|制作(?:记录|流程|管线|清单)"
        r"|参考与制作|工程(?:文件|记录|目录|说明)|同一份工程|配乐与可视化[：:]",
    ),
    (
        "internal_receipt",
        r"验证记录|验收|调试|复现|源(?:码|文件)|文件路径|渲染|编解码"
        r"|(?:文件|音轨|音频|视频|成片|产物|源码|输入源)(?:的)?(?:哈希|[Ss][Hh][Aa]-?256)"
        r"|(?:哈希|[Ss][Hh][Aa]-?256)(?:清单|回执|记录)",
    ),
    (
        "production_tools",
        r"(?<![A-Za-z])(?:Manim|Remotion|Qwen(?:3)?(?:-TTS)?|Serena|FFmpeg|FFprobe"
        r"|Kokoro|MLX-Audio|TTS)(?![A-Za-z])",
    ),
    (
        "voice_workflow",
        r"本地(?:配音|模型|语音)|配音[：:]|(?:字幕|配音|音频|视频)(?:管线|生成|对齐)"
        r"|(?:生成|导出)(?:样片|成片|视频|音频)|(?:测试|检查)报告"
        r"|(?:技术|音频|视频|配音|字幕|样片|成片|自动)(?:测试|检查)通过|技术样片",
    ),
    (
        "revision_credit",
        r"(?:本片|本期|修订|视频|工程|制作|项目)\s*(?:版本|版|V\s*\d)"
        r"|(?:Hodge|霍奇)\s*V\s*\d|V\s*\d+\s*(?:修订|版本|制作)",
    ),
    (
        "local_path",
        r"(?:/Users/|/home/|file://|[A-Z]:\\Users\\)|(?:media|assets|scripts|scenes|docs|src)/[^\s，。；]*\.(?:mp4|wav|json|py|md|png|srt)|\b(?:AGENTS|README)\.md\b",
    ),
)
COMPILED_RULES = [(name, re.compile(pattern, re.IGNORECASE)) for name, pattern in RULES]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized_text(text: str) -> str:
    """Line wrapping may differ; spelling, punctuation and content may not."""
    return re.sub(r"\s+", "", text)


def check_text(
    text: str, *, location: str = "display", channel: str = "display"
) -> list[dict[str, str]]:
    """Renderer hook for an actual string; no metadata should be passed here."""
    # Chinese line wrapping must not hide a forbidden phrase. Keep Latin word
    # boundaries intact so academic names and mathematical identifiers stay safe.
    scan_text = re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", text)
    return [
        {
            "rule_id": rule_id,
            "location": location,
            "channel": channel,
            "text": text,
            "match": match.group(0),
        }
        for rule_id, pattern in COMPILED_RULES
        for match in pattern.finditer(scan_text)
    ]


def check_audience(
    authoring: dict[str, Any],
    *,
    display_manifest: dict[str, Any] | None = None,
    timeline: dict[str, Any] | None = None,
    authoring_sha256: str | None = None,
    root: Path = ROOT,
    allow_scene_subset: bool = False,
    source_roots: list[Path] | None = None,
) -> dict[str, Any]:
    """Validate explicit surfaces; internal authoring/manifest metadata is ignored."""
    errors: list[str] = []
    surfaces: list[dict[str, str]] = []
    scene_ids: set[str] = set()
    cues: dict[str, tuple[str, str]] = {}
    scene_order: list[str] = []
    timeline_scene_ids: list[str] = []
    if not isinstance(authoring.get("episode"), str) or not authoring["episode"]:
        errors.append("authoring.episode: expected nonempty string")

    def surface(location: str, text: Any, channel: str) -> None:
        if not isinstance(text, str) or not text.strip():
            errors.append(f"{location}: expected nonempty text")
        else:
            surfaces.append({"location": location, "channel": channel, "text": text})

    surface("authoring.title", authoring.get("title"), "title")
    scenes = authoring.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        errors.append("authoring.scenes: expected nonempty list")
        scenes = []
    for scene in scenes:
        if not isinstance(scene, dict) or not isinstance(scene.get("id"), str):
            errors.append("authoring scene: expected object with string id")
            continue
        sid = scene["id"]
        if sid in scene_ids:
            errors.append(f"duplicate authoring scene: {sid}")
        scene_ids.add(sid)
        scene_order.append(sid)
        surface(f"authoring.{sid}.title", scene.get("title"), "heading")
        sentences = scene.get("sentences")
        if not isinstance(sentences, list) or not sentences:
            errors.append(f"authoring.{sid}.sentences: expected nonempty list")
            continue
        for cue in sentences:
            if not isinstance(cue, dict) or not isinstance(cue.get("id"), str):
                errors.append(f"authoring.{sid}: expected cue with string id")
                continue
            cid = cue["id"]
            if cid in cues:
                errors.append(f"duplicate authoring cue: {cid}")
            text = cue.get("text")
            surface(f"authoring.{sid}.{cid}.text", text, "narration")
            if isinstance(text, str):
                cues[cid] = (sid, text)
            if cue.get("formula") is not None:
                surface(f"authoring.{sid}.{cid}.formula", cue["formula"], "formula")

    if display_manifest is not None:
        manifest = display_manifest
        if manifest.get("schema_version") != 1:
            errors.append("display.schema_version: expected 1")
        if manifest.get("episode") != authoring.get("episode"):
            errors.append("display.episode does not match authoring")
        if not authoring_sha256 or manifest.get("authoring_sha256") != authoring_sha256:
            errors.append("display.authoring_sha256 missing or stale")
        coverage = manifest.get("coverage", {})
        if not isinstance(coverage, dict):
            coverage = {}
        declared_ids = coverage.get("scene_ids", [])
        if (
            not isinstance(declared_ids, list)
            or any(not isinstance(item, str) for item in declared_ids)
            or len(declared_ids) != len(set(declared_ids))
            or set(declared_ids) != scene_ids
            or coverage.get("declared_complete") is not True
        ):
            errors.append("display.coverage must explicitly declare every scene exactly once")
        entries = manifest.get("entries")
        if not isinstance(entries, list) or not entries:
            errors.append("display.entries: expected nonempty list")
            entries = []
        ids: set[str] = set()
        present_scenes: set[str] = set()
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
                errors.append("display entry: expected object with string id")
                continue
            eid, sid = entry["id"], entry.get("scene_id")
            if eid in ids:
                errors.append(f"duplicate display id: {eid}")
            ids.add(eid)
            if not isinstance(sid, str) or sid not in scene_ids:
                errors.append(f"display.{eid}: unknown scene_id")
            else:
                present_scenes.add(sid)
            kind = entry.get("kind")
            if not isinstance(kind, str) or kind not in DISPLAY_KINDS:
                errors.append(f"display.{eid}: unknown kind")
            surface(f"display.{eid}.text", entry.get("text"), "display")
            cue_ids = entry.get("cue_ids", [])
            if not isinstance(cue_ids, list):
                errors.append(f"display.{eid}.cue_ids: expected list")
                continue
            for cid in cue_ids:
                if not isinstance(cid, str) or cid not in cues or cues[cid][0] != sid:
                    errors.append(f"display.{eid}: unknown or wrong-scene cue_id {cid!r}")
        if present_scenes != scene_ids:
            errors.append(
                "display.entries missing scenes: " + ", ".join(sorted(scene_ids - present_scenes))
            )
        sources = manifest.get("renderer_sources")
        if not isinstance(sources, list) or not sources:
            errors.append("display.renderer_sources: expected nonempty source/hash list")
            sources = []
        for source in sources:
            if not isinstance(source, dict) or not isinstance(source.get("path"), str):
                errors.append("display.renderer_sources: malformed source")
                continue
            path = (root / source["path"]).resolve()
            allowed_roots = [root.resolve(), *[p.resolve() for p in (source_roots or [])]]
            if not any(path.is_relative_to(allowed) for allowed in allowed_roots) or not path.is_file():
                errors.append(f"display source missing or outside project: {source['path']}")
            elif sha256(path) != source.get("sha256"):
                errors.append(f"display source hash stale: {source['path']}")

    if timeline is not None:
        if timeline.get("episode") != authoring.get("episode"):
            errors.append("timeline.episode does not match authoring")
        timeline_scenes = timeline.get("scenes")
        if not isinstance(timeline_scenes, list):
            errors.append("timeline.scenes: expected list")
            timeline_scenes = []
        seen_cues: list[str] = []
        for scene in timeline_scenes:
            if not isinstance(scene, dict) or not isinstance(scene.get("sentences"), list):
                errors.append("timeline scene: expected sentences list")
                continue
            sid = scene.get("id")
            if isinstance(sid, str):
                timeline_scene_ids.append(sid)
            else:
                errors.append("timeline scene: expected string id")
            for cue in scene["sentences"]:
                if not isinstance(cue, dict) or not isinstance(cue.get("id"), str):
                    errors.append("timeline cue: expected object with string id")
                    continue
                cid = cue["id"]
                seen_cues.append(cid)
                caption = cue.get("caption")
                surface(f"timeline.{sid}.{cid}.caption", caption, "subtitle")
                if cid not in cues or cues[cid][0] != sid:
                    errors.append(f"timeline.{sid}.{cid}: unknown or wrong-scene cue")
                elif isinstance(caption, str) and normalized_text(caption) != normalized_text(
                    cues[cid][1]
                ):
                    errors.append(f"timeline.{sid}.{cid}: caption differs from authoring")
                # A stale speech-text field is also an input-chain discrepancy.
                if "text" in cue and cid in cues and cue["text"] != cues[cid][1]:
                    errors.append(f"timeline.{sid}.{cid}: text differs from authoring")
        selected_scenes = set(timeline_scene_ids) if allow_scene_subset else scene_ids
        expected_scenes = [sid for sid in scene_order if sid in selected_scenes]
        if not timeline_scene_ids or timeline_scene_ids != expected_scenes:
            errors.append("timeline scene sequence is missing, duplicated, unknown or reordered")
        expected_cues = [cid for cid, (sid, _) in cues.items() if sid in selected_scenes]
        if seen_cues != expected_cues:
            errors.append("timeline cue sequence differs from complete authoring sequence")

    findings = []
    for item in surfaces:
        findings.extend(check_text(**item))
    complete = display_manifest is not None and timeline is not None
    status = (
        "BLOCKED"
        if errors or findings
        else ("DECLARED_SURFACES_TEXT_PASS" if complete else "SCOPED_TEXT_PASS")
    )
    return {
        "schema_version": 1,
        "status": status,
        "episode": authoring.get("episode"),
        "scope": {
            "authoring": True,
            "display_manifest": display_manifest is not None,
            "timeline_captions": timeline is not None,
            "surface_count": len(surfaces),
            "scene_count": len(scene_ids),
            "cue_count": len(cues),
            "timeline_selected_scene_ids": timeline_scene_ids,
            "timeline_all_scenes": timeline is not None and timeline_scene_ids == scene_order,
            "allow_scene_subset": allow_scene_subset,
        },
        "authoring_sha256": authoring_sha256,
        "errors": errors,
        "findings": findings,
        "limitations": LIMITATIONS,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authoring", required=True, type=Path)
    parser.add_argument("--display-manifest", type=Path)
    parser.add_argument("--timeline", type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--allow-scene-subset", action="store_true")
    args = parser.parse_args()
    try:
        inputs = {"authoring": args.authoring}
        if args.display_manifest:
            inputs["display_manifest"] = args.display_manifest
        if args.timeline:
            inputs["timeline"] = args.timeline
        values = {name: json.loads(path.read_text()) for name, path in inputs.items()}
        if any(not isinstance(value, dict) for value in values.values()):
            raise ValueError("all inputs must be JSON objects")
        report = check_audience(
            **values,
            authoring_sha256=sha256(args.authoring),
            allow_scene_subset=args.allow_scene_subset,
        )
        report["inputs"] = {
            name: {"path": str(path.resolve()), "sha256": sha256(path)}
            for name, path in inputs.items()
        }
        report["checker_sha256"] = sha256(Path(__file__))
        if args.require_complete and report["status"] == "SCOPED_TEXT_PASS":
            report["errors"].append("--require-complete needs display manifest and timeline")
            report["status"] = "BLOCKED"
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    except (OSError, ValueError, TypeError) as error:
        parser.exit(2, f"input error: {error}\n")
    print(f"{report['status']}: {len(report['findings'])} findings, {len(report['errors'])} errors")
    return 1 if report["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())

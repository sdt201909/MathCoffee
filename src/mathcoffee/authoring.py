"""One canonical authoring source and model-free planning for user workspaces."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from .style import json_sha256, resolve_style
from .workspace import PROJECT_FILE, load_project, workspace_path

_ID = re.compile(r"[a-z][a-z0-9_]{0,79}\Z")


def _id(value: Any, location: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"{location}: expected a safe lowercase stable ID")
    return value


def _nonempty(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{location}: expected nonempty text")
    return value


def _json(value: Any, location: str) -> None:
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{location}: expected finite JSON data") from exc


def normalize_authoring(raw: dict) -> dict:
    """Adapt legacy chapter/cue names once; preserve raw text and stable identities."""
    if not isinstance(raw, dict):
        raise ValueError("authoring must be an object")
    if type(raw.get("schema_version", 1)) is not int or raw.get("schema_version", 1) != 1:
        raise ValueError("unsupported authoring schema_version")
    if ("chapters" in raw) == ("scenes" in raw):
        raise ValueError("authoring must contain exactly one of scenes or chapters")
    _json(raw, "authoring")
    result = deepcopy(raw)
    result["schema_version"] = 1
    result["episode"] = _id(raw.get("episode", "project"), "authoring.episode")
    result["title"] = _nonempty(raw.get("title"), "authoring.title")
    source_scenes = result.pop("chapters") if "chapters" in result else result.pop("scenes")
    if not isinstance(source_scenes, list) or not source_scenes:
        raise ValueError("authoring.scenes: expected nonempty list; complete the blank template")
    states = result.setdefault("math_states", {})
    if not isinstance(states, dict):
        raise ValueError("authoring.math_states: expected object keyed by stable state IDs")
    for key in states:
        _id(key, "math_state ID")
    global_actions = result.setdefault("actions", [])
    if not isinstance(global_actions, list):
        raise ValueError("authoring.actions: expected list")
    action_ids: set[str] = set()
    for action in global_actions:
        if not isinstance(action, dict):
            raise ValueError("action must be an object")
        aid = _id(action.get("id"), "action.id")
        if aid in action_ids:
            raise ValueError("duplicate action ID")
        action_ids.add(aid)
        if "state_ref" in action and (
            not isinstance(action["state_ref"], str) or action["state_ref"] not in states
        ):
            raise ValueError(f"action {aid}: unknown math state")
    scene_ids: set[str] = set()
    cue_ids: set[str] = set()
    scenes = []
    for source_scene in source_scenes:
        if not isinstance(source_scene, dict):
            raise ValueError("scene must be an object")
        scene = deepcopy(source_scene)
        sid = _id(scene.get("id"), "scene.id")
        if sid in scene_ids:
            raise ValueError("duplicate scene ID")
        scene_ids.add(sid)
        _nonempty(scene.get("title"), f"scene {sid}.title")
        if ("sentences" in scene) == ("cues" in scene):
            raise ValueError(f"scene {sid}: provide exactly one of sentences or cues")
        sentences = scene.pop("cues") if "cues" in scene else scene.pop("sentences")
        if not isinstance(sentences, list) or not sentences:
            raise ValueError(f"scene {sid}: expected nonempty sentences")
        for cue in sentences:
            if not isinstance(cue, dict):
                raise ValueError("sentence must be an object")
            cid = _id(cue.get("id"), "sentence.id")
            if cid in cue_ids:
                raise ValueError("duplicate sentence ID")
            cue_ids.add(cid)
            _nonempty(cue.get("text"), f"sentence {cid}.text")
            for key in ("narration", "tts_text"):
                if key in cue and cue[key] != cue["text"]:
                    raise ValueError(f"sentence {cid}: {key} differs from canonical text")
            if "formula" in cue and not isinstance(cue["formula"], str):
                raise ValueError(f"sentence {cid}: formula must be text")
            if "duration_seconds" in cue:
                duration = cue["duration_seconds"]
                if (
                    type(duration) not in (int, float)
                    or not math.isfinite(duration)
                    or duration <= 0
                ):
                    raise ValueError(f"sentence {cid}: duration_seconds must be positive")
            visual = cue.get("visual")
            if visual is not None and not isinstance(visual, (str, dict)):
                raise ValueError(f"sentence {cid}: visual must be a name or object")
            references = [cue.get("state_ref")]
            if isinstance(visual, dict):
                references.append(visual.get("state_ref"))
            for reference in references:
                if reference is not None and (
                    not isinstance(reference, str) or reference not in states
                ):
                    raise ValueError(f"sentence {cid}: unknown math state {reference}")
            refs = cue.get("action_refs", [])
            if (
                not isinstance(refs, list)
                or any(not isinstance(ref, str) for ref in refs)
                or len(refs) != len(set(refs))
            ):
                raise ValueError(f"sentence {cid}: action_refs must be unique IDs")
            if any(ref not in action_ids for ref in refs):
                raise ValueError(f"sentence {cid}: unknown action reference")
        scene["sentences"] = sentences
        scenes.append(scene)
    result["scenes"] = scenes
    return result


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_plan(root: Path, result: dict) -> None:
    target = workspace_path(root, "build/plan.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=target.parent, prefix=".plan-", suffix=".json", delete=False
    ) as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        name = stream.name
    os.replace(name, target)


def plan_project(workspace: str | Path) -> dict:
    """Plan without importing rendering, synthesis runtimes, or model identities."""
    root = Path(workspace).expanduser().resolve(strict=True)
    project = load_project(root)
    authoring_path = workspace_path(root, project["authoring"])
    style = resolve_style(project["preset"], project["style"], project["brand"])
    if not authoring_path.is_file():
        raise ValueError("authoring file is missing")
    raw = json.loads(authoring_path.read_text())
    if not isinstance(raw, dict):
        raise ValueError("authoring must be an object")
    if type(raw.get("schema_version", 1)) is not int or raw.get("schema_version", 1) != 1:
        raise ValueError("unsupported authoring schema_version")
    if ("scenes" in raw) == ("chapters" in raw):
        raise ValueError("authoring must contain exactly one of scenes or chapters")
    if not isinstance(raw.get("scenes", raw.get("chapters")), list):
        raise ValueError("authoring scenes must be a list")
    pending = []
    if not raw.get("scenes", raw.get("chapters")):
        pending.append("Complete authoring scenes and canonical sentence text.")
    if not isinstance(raw.get("title"), str) or not raw["title"].strip():
        pending.append("Provide a viewer-facing title.")
    authoring = deepcopy(raw) if pending else normalize_authoring(raw)
    result = {
        "schema_version": 1,
        "status": "incomplete" if pending else "plan_ready",
        "workspace": str(root),
        "project": project,
        "authoring": authoring,
        "style": style,
        "source_sha256": {
            "project": _sha(workspace_path(root, PROJECT_FILE)),
            "authoring": _sha(authoring_path),
            "normalized_authoring": json_sha256(authoring),
            "style": style["provenance"]["style_sha256"],
        },
        "pending": pending,
        "reviews": {
            name: "pending"
            for name in (
                "mathematical",
                "narrative",
                "visual",
                "listening",
                "audience_understanding",
                "style_author_confirmation",
            )
        },
        "voice_request": {
            "provider": project["voice"]["provider"],
            "mode": project["voice"]["mode"],
            "style": deepcopy(style["voice"]),
            "cases": [
                {"id": cue["id"], "text": cue["text"],
                 **({"figure_label_registry": deepcopy(authoring["figure_label_registry"])} if "figure_label_registry" in authoring else {}),
                 **{key: deepcopy(cue[key]) for key in ("figure_label_registry", "spans") if key in cue}}
                for scene in authoring.get("scenes", [])
                for cue in scene.get("sentences", [])
            ]
            if not pending
            else [],
        },
        "planning_scope": "Source validation only; no model, media or human review has run.",
    }
    _write_plan(root, result)
    return result

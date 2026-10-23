"""User-owned project directories, independent from immutable plugin installations."""

from __future__ import annotations

import json
from pathlib import Path

from .style import preset_ids, resolve_style

PROJECT_FILE = "mathcoffee.json"


def workspace_path(workspace: str | Path, relative: str) -> Path:
    root = Path(workspace).expanduser().resolve(strict=True)
    if not isinstance(relative, str) or not relative:
        raise ValueError("project paths must be nonempty text")
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("project paths must be relative to the workspace")
    result = (root / candidate).resolve()
    if not result.is_relative_to(root):
        raise ValueError("project path escapes workspace")
    return result


def init_workspace(
    path: str | Path, preset: str = "mathcoffee-shorts@1", brand: str = "", title: str = ""
) -> dict:
    if preset not in preset_ids():
        raise ValueError("unknown preset")
    if not isinstance(brand, str) or not isinstance(title, str):
        raise ValueError("brand and title must be text")
    root = Path(path).expanduser().absolute()
    if root.exists() or root.is_symlink():
        raise FileExistsError(f"workspace already exists: {root}")
    resolve_style(preset, brand=brand)
    root.mkdir(parents=True, exist_ok=False)
    root = root.resolve()
    project = {
        "schema_version": 1,
        "title": title,
        "brand": brand,
        "preset": preset,
        "style": {},
        "authoring": "authoring.json",
        "runtime": {
            name: None
            for name in (
                "render_python",
                "speech_python",
                "node",
                "browser_executable",
                "model_path",
            )
        },
        "voice": {"provider": "qwen_mlx", "mode": "synthesize", "index": None},
        "music": {"enabled": True},
    }
    authoring = {
        "schema_version": 1,
        "episode": "project",
        "title": title,
        "brief": {
            "audience": "",
            "question": "",
            "assumptions": [],
            "mathematical_scope": "",
            "external_services": [],
        },
        "math_states": {},
        "actions": [],
        "scenes": [],
    }
    for name, value in ((PROJECT_FILE, project), ("authoring.json", authoring)):
        with (root / name).open("x") as stream:
            stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    (root / "PROJECT.md").write_text(
        "# 视频创作工程\n\n"
        "先填写 authoring.json 的 brief、数学状态、场景和逐句原文，再运行 mathcoffee plan。\n"
        "mathcoffee.json 保存风格与运行时选择；作品和 build/ 产物属于你，不存放在插件目录。\n"
        "空模板不包含节目正文。数学审稿、真实试听和动态画面审查分别记录，不能由技术测试代签。\n"
    )
    return {
        "status": "initialized",
        "workspace": str(root),
        "project": str(root / PROJECT_FILE),
        "preset": preset,
        "next_step": "complete authoring.json then run plan",
    }


def load_project(path: str | Path) -> dict:
    root = Path(path).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("workspace must be a directory")
    config = workspace_path(root, PROJECT_FILE)
    data = json.loads(config.read_text())
    if (
        not isinstance(data, dict)
        or type(data.get("schema_version")) is not int
        or data["schema_version"] != 1
    ):
        raise ValueError("unsupported project schema_version")
    for name in ("title", "brand", "preset", "authoring"):
        if not isinstance(data.get(name), str):
            raise ValueError(f"project.{name}: expected text")
    workspace_path(root, data["authoring"])
    for name in ("style", "runtime", "voice", "music"):
        if not isinstance(data.get(name), dict):
            raise ValueError(f"project.{name}: expected object")
    if data["voice"].get("mode") not in {"synthesize", "imported", "silent"}:
        raise ValueError("voice.mode must be synthesize, imported or silent")
    if not isinstance(data["voice"].get("provider"), str):
        raise ValueError("voice.provider must be text")
    if data["voice"].get("index") is not None:
        workspace_path(root, data["voice"]["index"])
    for name, value in data["runtime"].items():
        if name not in {
            "render_python",
            "speech_python",
            "node",
            "browser_executable",
            "model_path",
            "remotion_root",
        }:
            raise ValueError(f"unknown runtime field: {name}")
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f"runtime.{name} must be a path or null")
    if type(data["music"].get("enabled")) is not bool:
        raise ValueError("music.enabled must be a boolean")
    resolve_style(data["preset"], data["style"], data["brand"])
    return data

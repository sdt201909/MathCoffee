"""Explicit, isolated local runtime preparation. Inspection never installs anything."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from mathcoffee import __version__
from mathcoffee.resources import data_path


def data_home() -> Path:
    return Path(os.environ.get("MATHCOFFEE_DATA_HOME", Path.home() / "Library/Application Support/MathCoffee")).expanduser().resolve()


def cache_home() -> Path:
    return Path(os.environ.get("MATHCOFFEE_CACHE_HOME", Path.home() / "Library/Caches/MathCoffee")).expanduser().resolve()


def runtime_config() -> dict:
    path = data_home() / "runtime.json"
    if not path.exists():
        return {}
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("runtime.json must be an object")
    return value


def runtime_for(project: dict | None = None) -> dict:
    result = runtime_config()
    result.update({k: v for k, v in (project or {}).get("runtime", {}).items() if v})
    return result


def _probe(command: list[str]) -> dict:
    try:
        output = subprocess.run(command, capture_output=True, text=True, timeout=25, check=False)
        return {"available": output.returncode == 0, "detail": output.stdout.strip() or output.stderr.strip(), "returncode": output.returncode}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"available": False, "detail": str(error)}


def doctor(project: dict | None = None) -> dict:
    runtime = runtime_for(project)
    python = str(runtime.get("render_python") or sys.executable)
    checks = {
        "core": {"available": True, "python": sys.executable, "version": __version__},
        "platform": {"available": platform.system() == "Darwin" and platform.machine() == "arm64", "system": platform.system(), "machine": platform.machine()},
        "manim": _probe([python, "-I", "-c", "import importlib.metadata as m; print(m.version('manim'))"]),
    }
    if checks["manim"]["available"]:
        checks["manim"]["available"] = checks["manim"]["detail"] == "0.20.1"
    for name in ("node", "ffmpeg", "ffprobe", "latex", "xelatex", "dvisvgm"):
        executable = runtime.get(name) or shutil.which(name)
        checks[name] = {"available": bool(executable), "executable": executable}
        if name == "node" and executable:
            version = _probe([str(executable), "--version"])
            checks[name].update(version)
            checks[name]["available"] = version["available"] and version["detail"].startswith("v24.")
    remotion = runtime.get("remotion_root")
    checks["remotion"] = {"available": bool(remotion and (Path(remotion) / "node_modules/remotion/package.json").is_file()), "directory": remotion}
    if checks["remotion"]["available"]:
        version = json.loads((Path(remotion) / "node_modules/remotion/package.json").read_text()).get("version")
        checks["remotion"].update(version=version, available=version == "4.0.531")
    speech = runtime.get("speech_python")
    checks["speech"] = (_probe([str(speech), "-I", "-c", "import importlib.metadata as m; print(m.version('mlx-audio'))"]) if speech else {"available": False, "detail": "speech runtime not configured"})
    if checks["speech"]["available"]:
        checks["speech"]["available"] = checks["speech"]["detail"] == "0.5.7"
    model = runtime.get("model_path")
    browser = runtime.get("browser_executable")
    checks["browser"] = {"available": bool(browser and Path(browser).is_file()), "executable": browser}
    checks["model"] = {"available": bool(model and (Path(model) / "config.json").is_file()), "directory": model, "integrity": "not_checked_by_doctor"}
    return {"status": "ready" if all(v["available"] for v in checks.values()) else "setup_required", "checks": checks, "runtime": runtime, "planning_available": True, "network_accessed": False}


def setup(component: str, *, execute: bool = False, wheel: Path | None = None) -> dict:
    """Return or execute explicit commands, all confined to managed runtime/cache roots."""
    base = data_home() / "runtimes" / __version__
    cache = cache_home() / __version__
    uv = shutil.which("uv") or "uv"
    commands: list[list[str]] = []
    updates: dict[str, str] = {}
    copies: list[tuple[Path, Path]] = []
    if component == "render":
        environment = base / "render"
        python = environment / "bin/python"
        commands.append([uv, "venv", "--python", "3.13", str(environment)])
        commands.append([uv, "pip", "sync", "--python", str(python), "--require-hashes", str(data_path("toolchains/render/requirements.lock"))])
        if wheel is not None:
            commands.append([uv, "pip", "install", "--python", str(python), "--no-deps", str(wheel.resolve(strict=True))])
        engine = cache / "remotion"
        copies.append((data_path("engines/remotion"), engine))
        commands.append(["npm", "ci", "--prefix", str(engine), "--ignore-scripts", "--no-audit", "--no-fund", "--cache", str(cache / "npm"), "--registry", "https://registry.npmjs.org"])
        commands.append(["npm", "--prefix", str(engine), "run", "browser:ensure"])
        updates = {"render_python": str(python), "remotion_root": str(engine)}
    elif component == "speech":
        environment = base / "speech"
        python = environment / "bin/python"
        commands = [[uv, "venv", "--python", "3.12", str(environment)], [uv, "pip", "sync", "--python", str(python), "--require-hashes", str(data_path("toolchains/speech/requirements.lock"))]]
        updates = {"speech_python": str(python)}
    elif component == "model":
        return _model_setup(execute)
    else:
        raise ValueError("component must be render, speech or model")
    result = {"status": "setup_plan", "component": component, "commands": commands, "copies": [{"source": str(a), "destination": str(b)} for a, b in copies], "downloads": "public runtime packages and browser; model weights are a separate component", "executed": False}
    if not execute:
        return result
    for selected, managed in [(environment, data_home()), *[(target, cache_home()) for _, target in copies]]:
        if selected.is_symlink() or not selected.resolve().is_relative_to(managed):
            raise ValueError("managed runtime/cache destination is a symlink or escapes its owner root")
        for parent in selected.parents:
            if parent == managed:
                break
            if parent.is_symlink():
                raise ValueError("managed runtime/cache ancestor is a symlink")
    base.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    # Never sync or replace a user-owned interpreter/environment.
    receipt_path = base / f"{component}.setup.json"
    source_hashes = {}
    for command in commands:
        for argument in command:
            file = Path(argument)
            if file.is_file() and file.suffix in {".lock", ".whl"}:
                source_hashes[str(file)] = hashlib.sha256(file.read_bytes()).hexdigest()
    for source, _ in copies:
        source_hashes.update({str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob("*") if p.is_file() and not any(x in {"node_modules", ".npm-cache", ".cache", "out", "__pycache__"} for x in p.relative_to(source).parts)})
    identity = hashlib.sha256(json.dumps({"plan": result, "sources": source_hashes}, sort_keys=True).encode()).hexdigest()
    receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else None
    if (environment.exists() or any(b.exists() for _, b in copies)) and not receipt:
        raise FileExistsError("existing runtime/cache is not owned by this setup receipt; retained without modification")
    if receipt and receipt.get("identity") != identity:
        raise ValueError("setup arguments differ from retained installation receipt")
    receipt = receipt or {"identity": identity, "status": "preparing", "completed_commands": []}
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    for source, destination in copies:
        if destination.exists():
            for original in source.rglob("*"):
                if original.is_file() and not any(x in {"node_modules", ".cache", ".npm-cache", "out", "__pycache__"} for x in original.relative_to(source).parts):
                    candidate = destination / original.relative_to(source)
                    if not candidate.is_file() or hashlib.sha256(candidate.read_bytes()).digest() != hashlib.sha256(original.read_bytes()).digest():
                        raise ValueError("retained engine cache differs from its fixed source")
            continue
        shutil.copytree(source, destination, ignore=shutil.ignore_patterns("node_modules", ".cache", ".npm-cache", "out", "__pycache__"))
    child = os.environ.copy()
    child.update(UV_PYTHON_DOWNLOADS="never", HF_HUB_DISABLE_IMPLICIT_TOKEN="1")
    for index, command in enumerate(commands):
        if index in receipt["completed_commands"]:
            continue
        # A failed venv creation can be resumed only if its interpreter exists.
        if not (command[1] == "venv" and (environment / "bin/python").is_file()):
            subprocess.run(command, check=True, env=child, stdout=sys.stderr)
        receipt["completed_commands"].append(index)
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    if component == "render":
        script = "const {createRequire}=require('module');const r=createRequire(process.argv[1]+'/package.json');r('@remotion/renderer').ensureBrowser({logLevel:'error'}).then(x=>process.stdout.write(JSON.stringify(x))).catch(e=>{console.error(e);process.exit(1)});"
        browser = subprocess.run(["node", "-e", script, str(engine)], cwd=engine, capture_output=True, text=True, check=True, env=child)
        status = json.loads(browser.stdout)
        if not status.get("path") or not Path(status["path"]).is_file():
            raise RuntimeError("explicit browser preparation did not return an existing executable")
        updates["browser_executable"] = status["path"]
    _register(updates)
    receipt["status"] = "prepared"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    return {**result, "status": "prepared", "executed": True, "runtime": runtime_config()}


def _register(updates: dict) -> None:
    root = data_home()
    root.mkdir(parents=True, exist_ok=True)
    path = root / "runtime.json"
    value = {**runtime_config(), **updates}
    temporary = path.with_suffix(".tmp.json")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def _model_setup(execute: bool) -> dict:
    spec = json.loads(data_path("speech/model_files.json").read_text())
    destination = cache_home() / "models" / spec["revision"]
    result = {"status": "setup_plan", "component": "model", "destination": str(destination), "repo": spec["repo"], "revision": spec["revision"], "bytes": sum(x["size"] for x in spec["files"]), "executed": False}
    if not execute:
        return result
    import urllib.request
    destination.mkdir(parents=True, exist_ok=True)
    entries = []
    for item in spec["files"]:
        target = (destination / item["path"]).resolve()
        if not target.is_relative_to(destination) or (destination / item["path"]).is_symlink():
            raise ValueError("model path escapes managed cache")
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            partial = target.with_name(target.name + ".partial")
            if partial.exists():
                raise FileExistsError(f"unfinished download retained for inspection: {partial}")
            url = f"https://huggingface.co/{spec['repo']}/resolve/{spec['revision']}/{item['path']}"
            with urllib.request.urlopen(url, timeout=45) as response, partial.open("xb") as output:
                shutil.copyfileobj(response, output, 8 * 1024 * 1024)
            _check_model_file(partial, item)
            partial.rename(target)
        entries.append(_check_model_file(target, item))
    _register({"model_path": str(destination)})
    return {**result, "status": "prepared", "executed": True, "files": entries}


def _check_model_file(path: Path, item: dict) -> dict:
    sha = hashlib.sha256()
    blob = hashlib.sha1(f"blob {path.stat().st_size}\0".encode())
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            sha.update(block)
            blob.update(block)
    expected = item.get("lfs", {}).get("oid", item["oid"])
    measured = sha.hexdigest() if item.get("lfs") else blob.hexdigest()
    if path.stat().st_size != item["size"] or measured != expected:
        raise ValueError(f"model integrity mismatch: {item['path']}")
    return {"path": item["path"], "bytes": path.stat().st_size, "sha256": sha.hexdigest()}

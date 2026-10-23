"""Agent-readable local CLI. Planning has no optional rendering/model imports."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from mathcoffee import __version__


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(prog="mathcoffee", description=__doc__)
    value.add_argument("--version", action="version", version=__version__)
    commands = value.add_subparsers(dest="command", required=True)
    for name in ("setup", "doctor", "init", "plan", "voice", "preview", "render", "verify", "status", "resume", "style", "bundle"):
        sub = commands.add_parser(name)
        sub.add_argument("--workspace", type=Path)
        sub.add_argument("--json", action="store_true", help="structured output (the default)")
        if name == "setup":
            sub.add_argument("--component", choices=("render", "speech", "model"), required=True)
            sub.add_argument("--execute", action="store_true")
            sub.add_argument("--wheel", type=Path)
        elif name == "init":
            sub.add_argument("--preset", default="mathcoffee-shorts@1")
            sub.add_argument("--brand", default="")
            sub.add_argument("--title", default="")
        elif name == "doctor":
            sub.add_argument("--profile", choices=("core", "render", "full"), default="full")
        elif name == "voice":
            sub.add_argument("--generate", action="store_true")
        elif name in {"render", "verify", "resume"}:
            sub.add_argument("--quality", choices=("draft", "final"), default="final" if name == "render" else "draft")
        elif name == "style":
            sub.add_argument("--preset", default="mathcoffee-shorts@1")
        elif name == "bundle":
            sub.add_argument("--host", choices=("codex", "claude"), required=True)
            sub.add_argument("--wheel", type=Path, required=True)
            sub.add_argument("--output", type=Path, required=True)
    return value


def run(args: argparse.Namespace) -> dict:
    from mathcoffee.authoring import plan_project
    from mathcoffee.workspace import init_workspace, load_project
    command = args.command
    if command == "setup":
        from mathcoffee.environment import setup
        return setup(args.component, execute=args.execute, wheel=args.wheel)
    if command == "doctor":
        from mathcoffee.environment import doctor
        return doctor(load_project(args.workspace) if args.workspace else None, profile=args.profile)
    if command == "init":
        if not args.workspace:
            raise ValueError("init requires --workspace pointing to a new directory")
        return init_workspace(args.workspace, args.preset, args.brand, args.title)
    if command == "bundle":
        from mathcoffee.plugin_bundle import build_bundle
        return build_bundle(args.output, args.host, args.wheel)
    if command == "style" and not args.workspace:
        from mathcoffee.style import resolve_style
        return resolve_style(args.preset)
    if not args.workspace:
        raise ValueError(f"{command} requires --workspace")
    if command in {"plan", "style"}:
        plan = plan_project(args.workspace)
        return plan["style"] if command == "style" else plan
    if command == "voice":
        from mathcoffee.voice import prepare_voice
        return prepare_voice(args.workspace, plan_project(args.workspace), generate=args.generate)
    if command == "status":
        from mathcoffee.pipeline import status
        return status(args.workspace)
    return _render_worker(args)


def _render_local(command: str, workspace: str, quality: str) -> dict:
    if command == "verify":
        from mathcoffee.verification import verify_build
        return verify_build(Path(workspace), quality=quality)
    from mathcoffee.pipeline import build
    return build(Path(workspace), quality=quality, resume=command == "resume")


def _render_worker(args: argparse.Namespace) -> dict:
    from mathcoffee.environment import runtime_environment, runtime_for
    from mathcoffee.workspace import load_project
    from mathcoffee.voice import _worker_bootstrap
    runtime = runtime_for(load_project(args.workspace))
    python = runtime.get("render_python") or sys.executable
    package, binding = _worker_bootstrap()
    code = binding + "\nimport json\nfrom mathcoffee.cli import _render_local\ntry:\n result=_render_local(sys.argv[1],sys.argv[2],sys.argv[3])\n print(json.dumps(result,ensure_ascii=False,allow_nan=False))\nexcept Exception as e:\n print(json.dumps({'status':'blocked','error':type(e).__name__,'message':str(e)},ensure_ascii=False))\n sys.exit(2)\n"
    env = runtime_environment(runtime)
    env.update(PYTHONDONTWRITEBYTECODE="1", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_IMPLICIT_TOKEN="1")
    quality = "draft" if args.command == "preview" else args.quality
    output = subprocess.run([str(python), "-I", "-c", code, package, args.command, str(args.workspace.resolve()), quality], capture_output=True, text=True, env=env)
    try:
        result = json.loads(output.stdout)
    except ValueError as error:
        raise RuntimeError(f"render worker did not return structured output: {output.stderr[-2000:]}") from error
    if output.returncode:
        raise RuntimeError(f"render worker failed ({result.get('error')}): {result.get('message')}")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result = run(args)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0 if result.get("status") not in {"incomplete", "BLOCKED", "blocked", "failed"} else 3
    except (ValueError, OSError, RuntimeError, KeyError, subprocess.CalledProcessError) as error:
        print(json.dumps({"status": "blocked", "error": type(error).__name__, "message": str(error)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

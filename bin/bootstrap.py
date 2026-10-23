#!/usr/bin/env python3
"""Explicit, resumable setup outside the immutable MathCoffee distribution.

This file uses only the standard library so a CLT Python can plan an installation.
The installed core always uses Homebrew Python 3.13; voice runs separately on 3.12.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from email.parser import BytesParser
from pathlib import Path, PurePosixPath

OWNER = "mathcoffee-bootstrap-v1"
BREW_PREFIX = Path("/opt/homebrew")
FORMULAE = {
    "core": ("uv", "python@3.13"),
    "render": ("uv", "python@3.13", "node@24", "cairo", "pango", "pkgconf", "ffmpeg"),
    "full": ("uv", "python@3.13", "node@24", "cairo", "pango", "pkgconf", "ffmpeg", "python@3.12"),
}
INSTALL_HINTS = {
    "xcode": (
        "Install Apple Command Line Tools with xcode-select --install, "
        "complete Apple's dialog, then rerun. https://developer.apple.com/xcode/resources/"
    ),
    "homebrew": (
        "Install native Apple Silicon Homebrew yourself from https://brew.sh/ "
        "and review its instructions. MathCoffee does not install it or accept legal terms for you."
    ),
    "wheel": (
        "Use a complete release ZIP containing exactly one wheels/*.whl, or build "
        "a wheel with uv build --wheel and pass --wheel /absolute/path/to/MathCoffee.whl."
    ),
}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--profile", choices=tuple(FORMULAE), default="core")
    result.add_argument(
        "--with-tex",
        action="store_true",
        help="Explicitly install missing MacTeX; its installer may ask for administrator approval",
    )
    result.add_argument(
        "--with-model",
        action="store_true",
        help="Explicitly download pinned public voice weights; requires --profile full",
    )
    result.add_argument(
        "--wheel", type=Path, help="Use this local wheel rather than the single bundled wheel"
    )
    result.add_argument(
        "--execute",
        action="store_true",
        help="Execute the displayed preparation; default is a read-only plan",
    )
    return result


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def check_path(path: Path) -> Path:
    """Reject symlinked destinations and ancestors before resolving any path."""
    candidate = path.expanduser().absolute()
    for part in (candidate, *candidate.parents):
        if part.is_symlink():
            raise ValueError(f"symlinked installation path is not supported: {part}")
    return candidate


def _roots(distribution: Path) -> tuple[Path, Path]:
    data = check_path(
        Path(
            os.environ.get("MATHCOFFEE_DATA_HOME")
            or Path.home() / "Library/Application Support/MathCoffee"
        )
    )
    cache = check_path(
        Path(os.environ.get("MATHCOFFEE_CACHE_HOME") or Path.home() / "Library/Caches/MathCoffee")
    )
    for path in (data, cache):
        if path == Path(path.anchor) or path == Path.home() or path.is_relative_to(distribution):
            raise ValueError(
                "runtime/cache roots must be dedicated directories outside the distribution"
            )
        if path.exists() and not path.is_dir():
            raise ValueError(f"runtime/cache root is not a directory: {path}")
    return data, cache


def wheel_info(path: Path) -> dict:
    path = check_path(path)
    if not path.is_file() or path.suffix != ".whl":
        raise ValueError("--wheel must name an existing regular MathCoffee .whl file")
    files = {}
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("wheel contains duplicate entries")
        for entry in archive.infolist():
            relative = PurePosixPath(entry.filename)
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or "\\" in entry.filename
                or str(relative) != entry.filename.rstrip("/")
                or (entry.external_attr >> 16) & 0o170000 == 0o120000
            ):
                raise ValueError("wheel contains an escaping path or symlink")
            if entry.filename.startswith("mathcoffee/") and not entry.is_dir():
                files[entry.filename[len("mathcoffee/") :]] = hashlib.sha256(
                    archive.read(entry)
                ).hexdigest()
        metadata = [n for n in names if n.endswith(".dist-info/METADATA")]
        if len(metadata) != 1:
            raise ValueError("wheel must contain exactly one distribution")
        fields = BytesParser().parsebytes(archive.read(metadata[0]))
        if fields.get("Name", "").lower().replace("_", "-") != "mathcoffee":
            raise ValueError("wheel distribution must be MathCoffee")
        version = fields.get("Version", "")
        if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)*(?:(?:a|b|rc)[0-9]+)?(?:\.post[0-9]+)?", version):
            raise ValueError("wheel version is not a supported canonical package version")
        entry_points = metadata[0].rsplit("/", 1)[0] + "/entry_points.txt"
        if (
            "__main__.py" not in files
            or entry_points not in names
            or b"mathcoffee = mathcoffee.cli:main" not in archive.read(entry_points)
        ):
            raise ValueError("wheel lacks the MathCoffee CLI entry point")
    return {"path": str(path), "version": version, "sha256": sha256(path), "files": files}


def find_wheel(explicit: Path | None, distribution: Path) -> dict | None:
    if explicit is not None:
        return wheel_info(explicit)
    choices = list((distribution / "wheels").glob("*.whl"))
    if len(choices) != 1:
        return None
    return wheel_info(choices[0])


def tex_available() -> bool:
    return all(
        shutil.which(name) or (Path("/Library/TeX/texbin") / name).is_file()
        for name in ("latex", "xelatex", "dvisvgm", "kpsewhich")
    )


def process_environment(data: Path, cache: Path, profile: str) -> dict:
    child = os.environ.copy()
    bins = [str(BREW_PREFIX / "opt" / name / "bin") for name in FORMULAE[profile]]
    child.update(
        PATH=os.pathsep.join([*bins, "/Library/TeX/texbin", child.get("PATH", "/usr/bin:/bin")]),
        MATHCOFFEE_DATA_HOME=str(data),
        MATHCOFFEE_CACHE_HOME=str(cache),
        UV_PYTHON_DOWNLOADS="never",
        PYTHONDONTWRITEBYTECODE="1",
        HOMEBREW_NO_AUTO_UPDATE="1",
        HOMEBREW_NO_INSTALL_UPGRADE="1",
        HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK="1",
        HOMEBREW_NO_INSTALL_CLEANUP="1",
        HF_HUB_DISABLE_IMPLICIT_TOKEN="1",
    )
    return child


def find_brew() -> str | None:
    selected = shutil.which("brew")
    fallback = BREW_PREFIX / "bin/brew"
    return selected or (
        str(fallback) if fallback.is_file() and os.access(fallback, os.X_OK) else None
    )


def create_plan(options: argparse.Namespace, distribution: Path | None = None) -> dict:
    if options.with_model and options.profile != "full":
        raise ValueError("--with-model requires --profile full")
    if options.with_tex and options.profile == "core":
        raise ValueError("--with-tex requires --profile render or full")
    distribution = (distribution or Path(__file__).resolve().parent.parent).resolve()
    data, cache = _roots(distribution)
    wheel = find_wheel(options.wheel, distribution)
    version = wheel["version"] if wheel else "<wheel-version>"
    base = data / "runtimes" / version
    core = base / "core"
    staged = base / "bootstrap-wheel" / Path(wheel["path"]).name if wheel else None
    brew = find_brew() or str(BREW_PREFIX / "bin/brew")
    missing = [
        name for name in FORMULAE[options.profile] if not (BREW_PREFIX / "opt" / name).is_dir()
    ]
    commands = [[brew, "install", "--formula", *missing]] if missing else []
    has_tex = tex_available()
    needs_tex = options.profile != "core" and not has_tex
    if needs_tex and options.with_tex:
        commands.append([brew, "install", "--cask", "mactex-no-gui"])
    if wheel:
        uv = str(BREW_PREFIX / "opt/uv/bin/uv")
        python = str(core / "bin/python")
        commands += [
            [
                uv,
                "venv",
                "--python",
                str(BREW_PREFIX / "opt/python@3.13/bin/python3.13"),
                str(core),
            ],
            [uv, "pip", "install", "--python", python, "--offline", "--no-deps", str(staged)],
        ]
        components = (
            (["render"] if options.profile != "core" else [])
            + (["speech"] if options.profile == "full" else [])
            + (["model"] if options.with_model else [])
        )
        for component in components:
            command = [
                python,
                "-I",
                "-B",
                "-m",
                "mathcoffee",
                "setup",
                "--component",
                component,
                "--execute",
            ]
            if component == "render":
                command += ["--wheel", str(staged)]
            commands.append(command)
    return {
        "status": "bootstrap_plan",
        "profile": options.profile,
        "executed": False,
        "host": {"system": platform.system(), "architecture": platform.machine()},
        "homebrew": brew,
        "wheel": {k: v for k, v in wheel.items() if k != "files"} if wheel else None,
        "data_home": str(data),
        "cache_home": str(cache),
        "core": str(core),
        "required_formulae": list(FORMULAE[options.profile]),
        "formulae_apparently_missing": missing,
        "commands": commands,
        "tex": {
            "available": has_tex,
            "required_for_profile": options.profile != "core",
            "requested": options.with_tex,
            "admin_prompt": (
                "MacTeX may request administrator approval through its standard package installer; "
                "no password or elevation bypass is provided."
            )
            if options.with_tex
            else None,
        },
        "model_download_requested": options.with_model,
        "downloads": (
            "Only explicit execution installs missing public runtime packages/browser. "
            "Voice weights require --with-model."
        ),
        "next_step": INSTALL_HINTS["wheel"]
        if wheel is None
        else "Review the plan, then rerun with --execute to prepare this profile.",
        "system_setup": INSTALL_HINTS,
    }


def run(command: list[str], *, env: dict, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        env=env,
        text=True,
        check=False,
        stdout=subprocess.PIPE if capture else sys.stderr,
        stderr=subprocess.PIPE if capture else sys.stderr,
    )


def checked(command: list[str], *, env: dict, capture: bool = False) -> subprocess.CompletedProcess:
    result = run(command, env=env, capture=capture)
    if result.returncode:
        detail = getattr(result, "stderr", "") or ""
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command)}; {detail}".strip()
        )
    return result


def read_json(path: Path) -> dict:
    check_path(path)
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"configuration must be a JSON object: {path}")
    return value


def write_json(path: Path, value: dict) -> None:
    check_path(path)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=path.name + ".",
        suffix=".tmp",
        delete=False,
    ) as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        temporary = Path(stream.name)
    temporary.replace(path)


def _ownership(base: Path, core: Path, wheel: dict) -> tuple[Path, dict | None]:
    for path in (base, core, base / "bootstrap-wheel", base / "core.bootstrap.json"):
        check_path(path)
    receipt_path = base / "core.bootstrap.json"
    receipt = read_json(receipt_path) if receipt_path.exists() else None
    if receipt:
        expected = {
            "owner": OWNER,
            "version": wheel["version"],
            "core": str(core),
            "wheel_sha256": wheel["sha256"],
        }
        if any(receipt.get(k) != v for k, v in expected.items()):
            raise ValueError(
                "this version's core receipt belongs to a different wheel or installation; "
                "existing environments were retained"
            )
        completed = receipt.get("completed")
        if (
            not isinstance(completed, list)
            or any(
                not isinstance(step, str)
                or step not in {"venv", "wheel", "render", "speech", "model"}
                for step in completed
            )
            or len(completed) != len(set(completed))
        ):
            raise ValueError("invalid bootstrap completion receipt")
    elif receipt_path.exists() or core.exists() or (base / "bootstrap-wheel").exists():
        raise FileExistsError(
            "existing core or staged-wheel directory is not owned by this bootstrap; "
            "retained without modification"
        )
    return receipt_path, receipt


def _verify_core(core: Path, wheel: dict, env: dict) -> None:
    command = [
        str(core / "bin/python"),
        "-I",
        "-B",
        "-c",
        (
            "import importlib.metadata as m,json,mathcoffee,sys; "
            "print(json.dumps({'version':m.version('mathcoffee'),'python':list(sys.version_info[:2]),"
            "'package':str(__import__('pathlib').Path(mathcoffee.__file__).parent)}))"
        ),
    ]
    value = json.loads(checked(command, env=env, capture=True).stdout)
    package = check_path(Path(value["package"]))
    if (
        value.get("version") != wheel["version"]
        or value.get("python") != [3, 13]
        or not package.is_relative_to(core)
    ):
        raise ValueError(
            "installed core version, interpreter, or package location differs from this wheel"
        )
    actual = {
        str(p.relative_to(package)): sha256(check_path(p))
        for p in package.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    }
    if actual != wheel["files"]:
        raise ValueError(
            "managed core package differs from its wheel; retained without overwriting it"
        )


@contextlib.contextmanager
def _lock(path: Path):
    import fcntl

    check_path(path)
    with path.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def execute(options: argparse.Namespace, distribution: Path | None = None) -> dict:
    plan = create_plan(options, distribution)
    if not options.execute:
        return plan
    if plan["host"] != {"system": "Darwin", "architecture": "arm64"}:
        raise RuntimeError(
            "execution requires a native Apple Silicon Mac (Darwin arm64); "
            "planning remains available on other hosts"
        )
    if not plan["wheel"]:
        raise ValueError(INSTALL_HINTS["wheel"])
    wheel = wheel_info(Path(plan["wheel"]["path"]))
    data, cache = Path(plan["data_home"]), Path(plan["cache_home"])
    base, core = data / "runtimes" / wheel["version"], Path(plan["core"])
    _ownership(base, core, wheel)
    config_path = data / "runtime.json"
    if config_path.exists() or config_path.is_symlink():
        read_json(config_path)
    env = process_environment(data, cache, options.profile)
    brew = find_brew()
    if not brew:
        raise RuntimeError(INSTALL_HINTS["homebrew"])
    prefix = checked([brew, "--prefix"], env=env, capture=True).stdout.strip()
    if prefix != str(BREW_PREFIX):
        raise RuntimeError(
            "Homebrew must use native /opt/homebrew, not an Intel or custom prefix. "
            + INSTALL_HINTS["homebrew"]
        )
    clt = run(["xcode-select", "-p"], env=env, capture=True)
    if clt.returncode or not clt.stdout.strip() or not Path(clt.stdout.strip()).is_dir():
        raise RuntimeError(INSTALL_HINTS["xcode"])
    missing = []
    for formula in FORMULAE[options.profile]:
        probe = run([brew, "list", "--formula", "--versions", formula], env=env, capture=True)
        if probe.returncode or not probe.stdout.strip():
            missing.append(formula)
    base.mkdir(parents=True, exist_ok=True)
    with _lock(base / "core.bootstrap.lock"):
        receipt_path, receipt = _ownership(base, core, wheel)
        receipt = receipt or {
            "owner": OWNER,
            "version": wheel["version"],
            "core": str(core),
            "wheel_sha256": wheel["sha256"],
            "source_wheel": wheel["path"],
            "completed": [],
            "status": "preparing",
            "commands": [],
        }
        write_json(receipt_path, receipt)
        try:
            if missing:
                command = [brew, "install", "--formula", *missing]
                receipt["commands"].append(command)
                write_json(receipt_path, receipt)
                checked(command, env=env)
            if options.profile != "core" and options.with_tex and not tex_available():
                print(
                    (
                        "MathCoffee: MacTeX is explicitly selected. Homebrew's standard "
                        "package installer may request administrator approval; "
                        "complete it interactively, or install TeX "
                        "manually and rerun this command. No password is handled by MathCoffee."
                    ),
                    file=sys.stderr,
                )
                command = [brew, "install", "--cask", "mactex-no-gui"]
                receipt["commands"].append(command)
                write_json(receipt_path, receipt)
                result = run(command, env=env)
                if result.returncode:
                    raise RuntimeError(
                        "MacTeX installation did not complete. Finish its normal "
                        "administrator dialog, or run brew install --cask mactex-no-gui "
                        "manually, then rerun this bootstrap; "
                        "its receipt is retained."
                    )
            staged_dir = base / "bootstrap-wheel"
            staged_dir.mkdir(exist_ok=True)
            staged = staged_dir / Path(wheel["path"]).name
            check_path(staged)
            if staged.exists():
                if sha256(staged) != wheel["sha256"]:
                    raise ValueError("retained staged wheel differs; no existing file was replaced")
            else:
                with tempfile.NamedTemporaryFile(
                    dir=staged_dir, prefix="wheel.", suffix=".partial", delete=False
                ) as stream:
                    temporary = Path(stream.name)
                    with Path(wheel["path"]).open("rb") as source:
                        shutil.copyfileobj(source, stream)
                if sha256(temporary) != wheel["sha256"]:
                    raise ValueError("source wheel changed during staging; partial copy retained")
                temporary.replace(staged)
            uv = str(BREW_PREFIX / "opt/uv/bin/uv")
            python = str(core / "bin/python")
            if "venv" not in receipt["completed"]:
                if not core.exists():
                    command = [
                        uv,
                        "venv",
                        "--python",
                        str(BREW_PREFIX / "opt/python@3.13/bin/python3.13"),
                        str(core),
                    ]
                    receipt["commands"].append(command)
                    write_json(receipt_path, receipt)
                    checked(command, env=env)
                if not (core / "bin/python").is_file():
                    raise RuntimeError(
                        "owned core creation is incomplete; no existing environment was replaced"
                    )
                receipt["completed"].append("venv")
                write_json(receipt_path, receipt)
            if not (core / "bin/python").is_file():
                raise RuntimeError(
                    "previously created core interpreter is missing; "
                    "retained receipt needs inspection"
                )
            if "wheel" not in receipt["completed"]:
                command = [
                    uv,
                    "pip",
                    "install",
                    "--python",
                    python,
                    "--offline",
                    "--no-deps",
                    str(staged),
                ]
                receipt["commands"].append(command)
                write_json(receipt_path, receipt)
                checked(command, env=env)
                _verify_core(core, wheel, env)
                receipt["completed"].append("wheel")
                write_json(receipt_path, receipt)
            else:
                _verify_core(core, wheel, env)
            config = read_json(config_path) if config_path.exists() else {}
            config["core_python"] = python
            if options.profile != "core":
                config["node"] = str(BREW_PREFIX / "opt/node@24/bin/node")
            write_json(config_path, config)
            components = (
                (["render"] if options.profile != "core" else [])
                + (["speech"] if options.profile == "full" else [])
                + (["model"] if options.with_model else [])
            )
            for component in components:
                if component in receipt["completed"]:
                    continue
                command = [
                    python,
                    "-I",
                    "-B",
                    "-m",
                    "mathcoffee",
                    "setup",
                    "--component",
                    component,
                    "--execute",
                ]
                if component == "render":
                    command += ["--wheel", str(staged)]
                receipt["commands"].append(command)
                write_json(receipt_path, receipt)
                result = json.loads(checked(command, env=env, capture=True).stdout)
                if result.get("status") != "prepared":
                    raise RuntimeError(
                        f"{component} setup did not report prepared; its evidence was retained"
                    )
                receipt["completed"].append(component)
                write_json(receipt_path, receipt)
            diagnostic_profile = (
                "full"
                if options.with_model
                else ("render" if options.profile == "full" else options.profile)
            )
            diagnostic = json.loads(
                checked(
                    [
                        python,
                        "-I",
                        "-B",
                        "-m",
                        "mathcoffee",
                        "doctor",
                        "--profile",
                        diagnostic_profile,
                    ],
                    env=env,
                    capture=True,
                ).stdout
            )
            receipt["status"] = "prepared"
            write_json(receipt_path, receipt)
        except (OSError, RuntimeError, ValueError, KeyError) as error:
            receipt["status"] = "interrupted"
            receipt["last_error"] = str(error)
            write_json(receipt_path, receipt)
            raise
    return {
        **plan,
        "status": "prepared",
        "executed": True,
        "core": str(core),
        "runtime_config": str(config_path),
        "receipt": str(receipt_path),
        "doctor": diagnostic,
        "ready": diagnostic.get("status") == "ready",
        "launchers": {
            "core": str(core / "bin/mathcoffee"),
            "plugin": str(
                (distribution or Path(__file__).resolve().parent.parent) / "bin/mathcoffee"
            ),
        },
        "voice": {
            "runtime_prepared": options.profile == "full",
            "model_download_requested": options.with_model,
            "model_status": "prepared"
            if options.with_model
            else "not_requested; run bin/mathcoffee setup --component model --execute when needed",
        },
        "next_step": (
            "Use bin/mathcoffee to create a separate user workspace. "
            "Inspect doctor checks for any remaining dependencies."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    options = parser().parse_args(argv)
    try:
        result = execute(options)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, RuntimeError, ValueError, KeyError, zipfile.BadZipFile) as error:
        print(
            json.dumps(
                {"status": "blocked", "error": type(error).__name__, "message": str(error)},
                ensure_ascii=False,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

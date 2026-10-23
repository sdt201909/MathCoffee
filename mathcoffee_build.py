"""PEP 517 adapter: assemble canonical external resources in a temporary tree."""

from __future__ import annotations

import contextlib
import os
import shutil
import tempfile
from pathlib import Path, PurePosixPath

IGNORED = shutil.ignore_patterns("__pycache__", "*.pyc", "node_modules", ".npm-cache", ".cache", "out")


def _copy_reviewed(source: Path, target: Path, prefix: str, reviewed: set[str]) -> None:
    for name in sorted(reviewed):
        if prefix and name != prefix and not name.startswith(prefix + "/"):
            continue
        original = source / name
        if not original.is_file() or any(p.is_symlink() for p in (original, *original.parents) if p != source and source in p.parents):
            raise ValueError(f"reviewed package input missing or symlinked: {name}")
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, destination)


@contextlib.contextmanager
def assembled():
    """Never generate package data in the source tree or copy production media."""
    source = Path(__file__).resolve().parent
    reviewed = {line for line in (source / "repository-files.txt").read_text().splitlines() if line and not line.startswith("#")}
    for name in reviewed:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or str(path) != name or "\\" in name:
            raise ValueError("invalid reviewed distribution path")
    with tempfile.TemporaryDirectory(prefix="mathcoffee-build-") as temporary:
        target = Path(temporary)
        _copy_reviewed(source, target, "", reviewed)
        data = target / "src/mathcoffee/data"
        distribution = data / "distribution"
        distribution.mkdir(parents=True, exist_ok=True)
        for name in ("skills", "bin", "docs", ".claude-plugin", ".agents"):
            if (source / name).is_dir():
                shutil.copytree(target / name, distribution / name, dirs_exist_ok=True, ignore=IGNORED)
        for name in ("LICENSE", "NOTICE", "README.md", "README.zh-CN.md", "AGENTS.md", "AGENTS.zh-CN.md",
                     "CONTRIBUTING.md", "CONTRIBUTING.zh-CN.md", "SECURITY.md", "SECURITY.zh-CN.md",
                     "THIRD_PARTY_NOTICES.md", "THIRD_PARTY_NOTICES.zh-CN.md", "Brewfile"):
            if (target / name).is_file():
                shutil.copy2(target / name, distribution / name)
        if (source / "plugin.json").is_file():
            shutil.copy2(source / "plugin.json", target / "plugin.json")
            shutil.copy2(source / "plugin.json", distribution / "plugin.json")
        for name in ("engines/remotion", "toolchains"):
            if (source / name).is_dir():
                shutil.copytree(target / name, data / name, dirs_exist_ok=True, ignore=IGNORED)
        previous = Path.cwd()
        try:
            os.chdir(target)
            yield
        finally:
            os.chdir(previous)


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    import uv_build
    output = str(Path(wheel_directory).resolve())
    with assembled():
        return uv_build.build_wheel(output, config_settings, metadata_directory)


def build_sdist(sdist_directory, config_settings=None):
    import uv_build
    output = str(Path(sdist_directory).resolve())
    with assembled():
        return uv_build.build_sdist(output, config_settings)


def get_requires_for_build_wheel(config_settings=None):
    return []


def get_requires_for_build_sdist(config_settings=None):
    return []

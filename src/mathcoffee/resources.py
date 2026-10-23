"""Read bundled, immutable resources without depending on a source checkout."""

from pathlib import Path, PurePosixPath


def data_path(relative: str) -> Path:
    """Return a bundled file or directory; callers must never write to this path."""
    if not isinstance(relative, str):
        raise ValueError("resource path must be text")
    path = PurePosixPath(relative)
    if (
        not relative
        or path.is_absolute()
        or str(path) != relative
        or ".." in path.parts
        or "\\" in relative
    ):
        raise ValueError("resource path must stay inside bundled data")
    root = Path(__file__).resolve().with_name("data")
    source = Path(__file__).resolve().parents[2]
    if not (root / relative).exists() and (source / "pyproject.toml").is_file():
        if relative == "distribution":
            return source
        if relative.startswith(("engines/remotion", "toolchains/")):
            result = (source / relative).resolve(strict=True)
            if not result.is_relative_to(source):
                raise ValueError("resource escapes source checkout")
            return result
    result = (root / relative).resolve(strict=True)
    if not result.is_relative_to(root) or not (result.is_file() or result.is_dir()):
        raise ValueError("resource must be a bundled file or directory")
    return result

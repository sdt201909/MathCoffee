#!/usr/bin/env python3
"""Check actual staged/committed bytes against the reviewed framework boundary."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "repository-files.txt"
MAX_BYTES = 2 * 1024 * 1024
BLOCKED_DIRECTORIES = {
    "media", "scenes", "episodes", "examples", "notebooks", "models",
    "node_modules", "__pycache__", ".local", "local", ".git",
}
BLOCKED_SUFFIXES = {
    ".mp4", ".mov", ".mkv", ".webm", ".avi", ".wav", ".mp3", ".m4a", ".aac",
    ".flac", ".ogg", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".pdf",
    ".ttf", ".otf", ".woff", ".woff2", ".safetensors", ".onnx", ".pt", ".pth",
    ".ckpt", ".bin", ".zip", ".tar", ".gz", ".7z", ".pem", ".key", ".p12",
    ".pfx", ".sqlite", ".db", ".ses", ".pyc",
}
SECRET_MARKERS = [
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"),
    re.compile(rb"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(rb"github_pat_[A-Za-z0-9_]{30,}"),
    re.compile(rb"\bAKIA[A-Z0-9]{16}\b"),
]


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT, stderr=subprocess.PIPE)


def parse_manifest(data: bytes) -> set[str]:
    paths = [line.strip() for line in data.decode("utf-8").splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    if len(set(paths)) != len(paths) or MANIFEST not in paths:
        raise ValueError("manifest must list itself and contain no duplicate paths")
    for path in paths:
        parsed = PurePosixPath(path)
        if parsed.is_absolute() or ".." in parsed.parts or str(parsed) != path:
            raise ValueError("manifest contains a noncanonical repository path")
    return set(paths)


def inspect_file(path: str, mode: str, data: bytes) -> list[str]:
    reasons = []
    parts = PurePosixPath(path).parts
    filename = parts[-1].lower()
    if any(p.lower() in BLOCKED_DIRECTORIES or p.startswith(".venv") for p in parts):
        reasons.append("production/runtime directory")
    if PurePosixPath(filename).suffix in BLOCKED_SUFFIXES:
        reasons.append("media, model, archive, cache or credential suffix")
    if filename == ".env" or filename.startswith(".env."):
        reasons.append("environment file")
    if filename.endswith(("_authoring.json", "_narration.md", "_delivery.md")):
        reasons.append("episode content")
    if mode not in {"100644", "100755"}:
        reasons.append("symlink or non-regular Git object")
    if len(data) > MAX_BYTES:
        reasons.append("file exceeds 2 MiB")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        reasons.append("non-UTF-8 content")
    if b"\0" in data:
        reasons.append("binary content")
    if any(pattern.search(data) for pattern in SECRET_MARKERS):
        reasons.append("possible credential marker")
    return [f"{path}: {reason}" for reason in reasons]


def read_tree(ref: str | None) -> dict[str, tuple[str, str]]:
    entries = {}
    raw = git("ls-tree", "-r", "-z", ref) if ref else git("ls-files", "--stage", "-z")
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        metadata, raw_path = entry.split(b"\t", 1)
        mode, middle, last = metadata.decode().split()
        if ref:
            oid = last
        else:
            oid = middle
            if last != "0":
                raise ValueError("unmerged index entries must be resolved first")
        entries[raw_path.decode("utf-8")] = (mode, oid)
    return entries


def check_tree(ref: str | None) -> list[str]:
    entries = read_tree(ref)
    if MANIFEST not in entries:
        return ["reviewed repository-files.txt is missing from this tree"]
    manifest = parse_manifest(git("cat-file", "blob", entries[MANIFEST][1]))
    errors = [f"{p}: outside reviewed allowlist" for p in sorted(set(entries) - manifest)]
    errors += [f"{p}: listed file is missing" for p in sorted(manifest - set(entries))]
    for path, (mode, oid) in sorted(entries.items()):
        if mode not in {"100644", "100755"}:
            errors += [f"{path}: symlink or non-regular Git object"]
            continue
        if int(git("cat-file", "-s", oid)) > MAX_BYTES:
            errors += [f"{path}: file exceeds 2 MiB"]
            continue
        errors += inspect_file(path, mode, git("cat-file", "blob", oid))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", help="check this commit tree instead of the Git index")
    parser.add_argument("--history", action="store_true", help="check every ancestor of --ref")
    args = parser.parse_args()
    if args.history and not args.ref:
        parser.error("--history requires --ref")
    try:
        refs = [None]
        if args.ref:
            commit = git("rev-parse", "--verify", f"{args.ref}^{{commit}}").decode().strip()
            refs = git("rev-list", commit).decode().splitlines() if args.history else [commit]
        count = 0
        for ref in refs:
            problems = check_tree(ref)
            if problems:
                print(f"BLOCKED ({ref or 'index'}):")
                print("\n".join(problems))
                return 1
            count += 1
        print(f"Framework repository boundary passed: {count} tree(s).")
        return 0
    except (subprocess.CalledProcessError, ValueError, UnicodeError) as exc:
        print(f"BLOCKED: unable to check repository boundary ({type(exc).__name__}).")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

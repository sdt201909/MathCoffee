"""Build host packages from reviewed resources and an explicit wheel, without installation."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
import zipfile
from email.parser import BytesParser
from pathlib import Path, PurePosixPath

SKILL_NAMES = ("setup", "create", "review", "revise")
SHARED_FILES = (
    "bin/mathcoffee",
    *(f"skills/{name}/SKILL.md" for name in SKILL_NAMES),
    "skills/create/references/workflow.md",
)
ENGINE_FILES = (
    "package.json", "package-lock.json", "tsconfig.json", "render.mjs", "render-shorts.mjs",
    "src/Timeline.tsx", "src/index.tsx", "src/schema.ts", "src/Shorts.tsx",
    "src/shorts-index.tsx", "src/shorts-schema.ts",
)
TOOLCHAIN_FILES = (
    "render/requirements.lock",
    "speech/requirements.in", "speech/requirements.lock", "speech/setup.sh",
    "speech/fetch_model.py", "speech/doctor.py", "speech/smoke.py",
    "speech/LICENSE-Qwen3-TTS.txt", "speech/LICENSE-mlx-audio.txt",
    "voice_qa/requirements.in", "voice_qa/requirements.lock", "voice_qa/setup.sh",
    "voice_qa/fetch_model.py",
)
HOST_MANIFESTS = {"codex": "plugin.json", "claude": ".claude-plugin/plugin.json"}
HOST_MARKETPLACES = {
    "codex": ".agents/plugins/marketplace.json",
    "claude": ".claude-plugin/marketplace.json",
}
FORBIDDEN_SUFFIXES = {
    ".mp4", ".mov", ".wav", ".mp3", ".png", ".jpg", ".jpeg", ".svg", ".pdf",
    ".onnx", ".pt", ".pth", ".safetensors", ".pem", ".key", ".pyc",
}


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _payload_roots() -> tuple[Path, Path, Path]:
    """Locate immutable wheel resources, or their canonical development checkout."""
    data = Path(__file__).with_name("data")
    packaged = data / "distribution"
    if (packaged / "plugin.json").is_file():
        return packaged, data / "engines/remotion", data / "toolchains"
    source = Path(__file__).resolve().parents[2]
    if (source / "plugin.json").is_file():
        return source, source / "engines/remotion", source / "toolchains"
    raise FileNotFoundError("MathCoffee distribution resources are absent from this installation")


def _safe_name(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts and "\\" not in name


def _read_regular(root: Path, relative: str) -> bytes:
    if not _safe_name(relative):
        raise ValueError("unsafe distribution resource name")
    root = root.resolve(strict=True)
    candidate = root / relative
    for component in (candidate, *candidate.parents):
        if component == root:
            break
        if component.is_symlink():
            raise ValueError(f"distribution resources cannot use symlinks: {relative}")
    if not candidate.resolve(strict=True).is_relative_to(root) or not candidate.is_file():
        raise ValueError(f"distribution resource is not a regular contained file: {relative}")
    return candidate.read_bytes()


def _release_key(version: str) -> str:
    return version.replace("-alpha.", "a").replace("-beta.", "b").replace("-rc.", "rc")


def _marketplace(host: str, source: bytes) -> dict:
    """Create a release catalog whose only source is this extracted bundle root."""
    catalog = json.loads(source)
    entries = [item for item in catalog.get("plugins", []) if item.get("name") == "mathcoffee"]
    if len(entries) != 1:
        raise ValueError("marketplace must declare exactly one MathCoffee entry")
    entry = entries[0]
    entry["source"] = {"source": "local", "path": "./"} if host == "codex" else "./"
    catalog["name"] = f"mathcoffee-{host}"
    catalog["plugins"] = [entry]
    if host == "codex":
        catalog["interface"] = {"displayName": "MathCoffee"}
    return catalog


def _wheel_metadata(path: Path) -> dict[str, str]:
    if path.suffix != ".whl" or path.is_symlink() or not path.is_file():
        raise ValueError("wheel_path must select a regular MathCoffee .whl file")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(set(names)) != len(names):
            raise ValueError("wheel contains duplicate paths")
        for entry in archive.infolist():
            if not _safe_name(entry.filename):
                raise ValueError("wheel contains an unsafe archive path")
            if stat.S_ISLNK(entry.external_attr >> 16):
                raise ValueError("wheel cannot contain symlinks")
            if PurePosixPath(entry.filename).suffix.lower() in FORBIDDEN_SUFFIXES:
                raise ValueError("wheel contains media, weights or credentials")
            if entry.file_size > 8 * 1024 * 1024:
                raise ValueError("wheel contains an unexpectedly large resource")
        metadata = [n for n in names if n.endswith(".dist-info/METADATA")]
        if len(metadata) != 1:
            raise ValueError("wheel must have one distribution metadata file")
        parsed = BytesParser().parsebytes(archive.read(metadata[0]))
        if parsed.get("Name", "").lower().replace("_", "-") != "mathcoffee":
            raise ValueError("wheel distribution must be MathCoffee")
        entry_points = metadata[0].rsplit("/", 1)[0] + "/entry_points.txt"
        if entry_points not in names or b"mathcoffee" not in archive.read(entry_points):
            raise ValueError("wheel has no MathCoffee CLI entry point")
        if "mathcoffee/__main__.py" not in names:
            raise ValueError("wheel has no python -m mathcoffee entry point")
        if not any(n.startswith("mathcoffee/data/presets/") and n.endswith(".json") for n in names):
            raise ValueError("wheel is missing style presets")
        return {"name": parsed["Name"], "version": parsed["Version"]}


def build_bundle(output: Path, host: str = "codex", wheel_path: Path | None = None) -> dict:
    """Create a new ZIP and receipt, refusing to overwrite either artifact."""
    if host not in HOST_MANIFESTS:
        raise ValueError("host must be codex or claude")
    if wheel_path is None:
        raise ValueError("an explicit built wheel_path is required")
    output = Path(output).absolute()
    if output.suffix.lower() != ".zip":
        raise ValueError("bundle output must end in .zip")
    sidecar = output.with_suffix(output.suffix + ".manifest.json")
    if output.exists() or output.is_symlink() or sidecar.exists() or sidecar.is_symlink():
        raise FileExistsError("refusing to overwrite an existing bundle or receipt")
    wheel_path = Path(wheel_path).absolute()
    wheel_metadata = _wheel_metadata(wheel_path)
    payload_root, engine_root, toolchain_root = _payload_roots()
    manifest_path = HOST_MANIFESTS[host]
    manifest_bytes = _read_regular(payload_root, manifest_path)
    manifest = json.loads(manifest_bytes)
    if manifest.get("name") != "mathcoffee":
        raise ValueError("host manifest has the wrong plugin identity")
    if _release_key(manifest.get("version", "")) != _release_key(wheel_metadata["version"]):
        raise ValueError("host manifest and wheel versions differ")
    files = {name: _read_regular(payload_root, name) for name in SHARED_FILES}
    files[manifest_path] = manifest_bytes
    marketplace_path = HOST_MARKETPLACES[host]
    marketplace = _marketplace(host, _read_regular(payload_root, marketplace_path))
    marketplace_json = json.dumps(marketplace, ensure_ascii=False, indent=2) + "\n"
    files[marketplace_path] = marketplace_json.encode()
    files.update({f"engines/remotion/{name}": _read_regular(engine_root, name)
                  for name in ENGINE_FILES})
    files.update({f"toolchains/{name}": _read_regular(toolchain_root, name)
                  for name in TOOLCHAIN_FILES})
    files[f"wheels/{wheel_path.name}"] = wheel_path.read_bytes()
    entries = {name: {"bytes": len(data), "sha256": _hash(data)}
               for name, data in sorted(files.items())}
    receipt = {
        "schema_version": 1, "host": host, "plugin": "mathcoffee",
        "marketplace": marketplace["name"],
        "version": manifest["version"], "core_version": wheel_metadata["version"],
        "files": entries,
        "validation_scope": (
            "Package contents and hashes; host loading, real rendering "
            "and human reviews are separate."
        ),
        "install_side_effects": "none; explicit setup prepares external dependencies",
    }
    manifest_json = json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    files["bundle-manifest.json"] = manifest_json.encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".mathcoffee-bundle-", dir=output.parent) as temporary:
        temporary_archive = Path(temporary) / "payload.zip"
        with zipfile.ZipFile(temporary_archive, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(files.items()):
                entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.create_system = 3
                entry.external_attr = (0o100755 if name == "bin/mathcoffee" else 0o100644) << 16
                archive.writestr(entry, data)
        validate_bundle(temporary_archive)
        os.link(temporary_archive, output)
    result = {**receipt, "output": str(output), "bytes": output.stat().st_size,
              "sha256": _hash(output.read_bytes()), "receipt": str(sidecar)}
    with sidecar.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


def validate_bundle(path: Path) -> dict:
    """Check the ZIP without extracting it or executing any packaged file."""
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or any(not _safe_name(n) for n in names):
            raise ValueError("bundle contains unsafe or duplicate paths")
        receipt = json.loads(archive.read("bundle-manifest.json"))
        if receipt.get("host") not in HOST_MANIFESTS:
            raise ValueError("bundle host is invalid")
        expected = set(receipt["files"]) | {"bundle-manifest.json"}
        if set(names) != expected:
            raise ValueError("bundle contains unlisted or missing payload files")
        if HOST_MANIFESTS[receipt["host"]] not in names:
            raise ValueError("bundle has no matching host manifest")
        marketplace_path = HOST_MARKETPLACES[receipt["host"]]
        if marketplace_path not in names:
            raise ValueError("bundle has no local installation catalog")
        marketplace = json.loads(archive.read(marketplace_path))
        expected_source = ({"source": "local", "path": "./"}
                           if receipt["host"] == "codex" else "./")
        entries = marketplace.get("plugins", [])
        if (len(entries) != 1 or entries[0].get("name") != "mathcoffee"
                or entries[0].get("source") != expected_source):
            raise ValueError("bundle catalog must reference this same plugin root")
        wheels = [name for name in names if name.startswith("wheels/") and name.endswith(".whl")]
        if len(wheels) != 1:
            raise ValueError("bundle must contain one installable core wheel")
        for name, item in receipt["files"].items():
            data = archive.read(name)
            if len(data) != item["bytes"] or _hash(data) != item["sha256"]:
                raise ValueError(f"bundle resource hash differs: {name}")
            if stat.S_ISLNK(archive.getinfo(name).external_attr >> 16):
                raise ValueError("bundle contains a symlink")
        return {"status": "PASS", "host": receipt["host"], "files": len(receipt["files"])}

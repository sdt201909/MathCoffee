"""Offline dependency/Metal/model-integrity check for the isolated speech runtime."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--verify-model", action="store_true", help="Read all 4.52 GB to verify hashes"
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    os.environ.update(
        HF_HUB_OFFLINE="1", HF_HUB_DISABLE_IMPLICIT_TOKEN="1", TRANSFORMERS_OFFLINE="1"
    )
    report = {
        "python": sys.version,
        "executable": sys.executable,
        "machine": platform.machine(),
        "dependencies": {},
        "offline": True,
    }
    for name in [
        "mlx-audio",
        "mlx",
        "mlx-metal",
        "transformers",
        "huggingface-hub",
        "numpy",
        "soundfile",
    ]:
        metadata = importlib.metadata.metadata(name)
        report["dependencies"][name] = {
            "version": metadata["Version"],
            "license": metadata.get("License-Expression") or metadata.get("License"),
        }
    try:
        import mlx.core as mx

        report["metal"] = {
            "available": mx.metal.is_available(),
            "device": str(mx.default_device()),
            "info": mx.device_info(),
        }
    except ImportError as exc:
        report["metal"] = {"available": False, "error": str(exc)}
    manifest_path = root / "media/reports/agent_upgrade/speech_runtime/model_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        rows = []
        for entry in manifest["files"]:
            path = root / entry["path"]
            ok = path.is_file() and path.stat().st_size == entry["size"]
            if ok and args.verify_model:
                with path.open("rb") as stream:
                    ok = hashlib.file_digest(stream, "sha256").hexdigest() == entry["sha256"]
            rows.append({"path": entry["path"], "ok": ok})
        report["model"] = {
            "repo": manifest["repo"],
            "revision": manifest["revision"],
            "files": rows,
            "sha256_checked": args.verify_model,
            "ready": all(x["ok"] for x in rows),
        }
    else:
        report["model"] = {"ready": False, "reason": "No completed verified snapshot manifest"}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["metal"]["available"] or not report["model"]["ready"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

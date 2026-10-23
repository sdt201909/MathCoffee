"""Download the public, pinned official snapshot without credentials or remote code."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = json.loads((ROOT / "src/mathcoffee/data/speech/model_files.json").read_text())
DEST = ROOT / "media/models/Qwen3-TTS-12Hz-1.7B-CustomVoice"
REPORT = ROOT / "media/reports/agent_upgrade/speech_runtime/model_manifest.json"


def checksum(path: Path, item: dict) -> dict:
    sha256 = hashlib.sha256()
    blob = hashlib.sha1(f"blob {path.stat().st_size}\0".encode())
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            sha256.update(chunk)
            blob.update(chunk)
    digest = sha256.hexdigest()
    assert path.stat().st_size == item["size"], f"Wrong size: {path}"
    if item.get("lfs"):
        assert digest == item["lfs"]["oid"], f"Wrong SHA256: {path}"
    else:
        assert blob.hexdigest() == item["oid"], f"Wrong Git blob SHA1: {path}"
    return {"path": str(path.relative_to(ROOT)), "size": item["size"], "sha256": digest}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", choices=["urllib", "hub"], default="hub")
    args = parser.parse_args()
    os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
    os.environ["HF_HOME"] = str(DEST / ".download_cache")
    os.environ["HF_XET_HIGH_PERFORMANCE"] = "1"
    DEST.mkdir(parents=True, exist_ok=True)
    results = []
    start = time.monotonic()
    if args.transport == "hub":
        from huggingface_hub import snapshot_download

        snapshot_download(
            repo_id=SPEC["repo"],
            revision=SPEC["revision"],
            allow_patterns=[x["path"] for x in SPEC["files"]],
            token=False,
            local_dir=DEST,
            max_workers=4,
        )
    for item in SPEC["files"]:
        path = DEST / item["path"]
        assert path.resolve().is_relative_to(DEST.resolve()) and not path.is_symlink()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            results.append(checksum(path, item))
            print(f"Verified existing: {item['path']}", flush=True)
            continue
        part = path.with_name(path.name + ".partial")
        assert not part.is_symlink()
        url = f"https://huggingface.co/{SPEC['repo']}/resolve/{SPEC['revision']}/{item['path']}"
        offset = part.stat().st_size if part.exists() else 0
        if offset < item["size"]:
            headers = {"User-Agent": "MathCoffee-local-model-fetch/1.0"}
            if offset:
                headers["Range"] = f"bytes={offset}-"
            # stdlib urllib has no Hugging Face token lookup or auth credential storage.
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=120) as response:
                append = response.status == 206 and offset > 0
                if append:
                    assert response.headers["Content-Range"].startswith(f"bytes {offset}-")
                with part.open("ab" if append else "wb") as stream:
                    for chunk in iter(lambda: response.read(8 * 1024 * 1024), b""):
                        stream.write(chunk)
                        if stream.tell() > item["size"]:
                            raise RuntimeError("Download exceeds pinned size")
        row = checksum(part, item)
        part.rename(path)
        row["path"] = str(path.relative_to(ROOT))
        results.append(row)
        print(f"Downloaded and verified: {item['path']} ({item['size']} bytes)", flush=True)
    manifest = {
        "repo": SPEC["repo"],
        "revision": SPEC["revision"],
        "source": "official Qwen snapshot",
        "license": "Apache-2.0",
        "authentication": "token=False; HF_HUB_DISABLE_IMPLICIT_TOKEN=1; dedicated empty HF_HOME"
        if args.transport == "hub"
        else "anonymous stdlib HTTP; no token lookup",
        "transport": args.transport,
        "remote_code": False,
        "quantization": None,
        "files": results,
        "bytes": sum(x["size"] for x in results),
        "fetch_seconds": time.monotonic() - start,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"report": str(REPORT), "bytes": manifest["bytes"]}), flush=True)


if __name__ == "__main__":
    main()

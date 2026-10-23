#!/usr/bin/env python3
"""Anonymous download of the pinned official WeSpeaker QA-only ONNX model."""

import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "media/models/wespeaker-voxceleb-resnet34-LM"
REVISION = "f0c48c298fd835726c27956a5d617bad7115627e"
FILENAME = "voxceleb_resnet34_LM.onnx"
EXPECTED_SHA = "7bb2f06e9df17cdf1ef14ee8a15ab08ed28e8d0ef5054ee135741560df2ec068"
EXPECTED_BYTES = 26530309
BASE = f"https://huggingface.co/Wespeaker/wespeaker-voxceleb-resnet34-LM/resolve/{REVISION}"


def fetch(name, url, expected_sha=None, expected_bytes=None):
    target = DEST / name
    if target.exists():
        data = target.read_bytes()
    else:
        request = urllib.request.Request(url, headers={"User-Agent": "MathCoffee-local-voice-QA/1"})
        # urllib uses no Hugging Face client, implicit token or account credential.
        with urllib.request.urlopen(request, timeout=120) as response:
            data = response.read(40_000_001)
        if len(data) > 40_000_000:
            raise RuntimeError(f"Unexpected oversized download: {name}")
    digest = hashlib.sha256(data).hexdigest()
    if expected_sha and digest != expected_sha:
        raise RuntimeError(f"SHA-256 mismatch: {name}")
    if expected_bytes and len(data) != expected_bytes:
        raise RuntimeError(f"Size mismatch: {name}")
    if not target.exists():
        with target.open("xb") as handle:
            handle.write(data)
    return {"path": str(target), "source": url, "bytes": len(data), "sha256": digest}


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    records = [fetch(FILENAME, f"{BASE}/{FILENAME}", EXPECTED_SHA, EXPECTED_BYTES)]
    records.append(fetch("MODEL_CARD.md", f"{BASE}/README.md"))
    records.append(
        fetch("LICENSE-CC-BY-4.0.txt", "https://creativecommons.org/licenses/by/4.0/legalcode.txt")
    )
    manifest = {
        "schema_version": 1,
        "model": "Wespeaker/wespeaker-voxceleb-resnet34-LM",
        "revision": REVISION,
        "license": "CC-BY-4.0",
        "attribution": (
            "WeSpeaker project, ResNet34-LM trained on VoxCeleb2 Dev; Wang et al., ICASSP 2023. "
            "Model unchanged; used only as a local diagnostic speaker-embedding proxy."
        ),
        "files": records,
        "audio_uploaded": False,
        "credential_access": False,
    }
    output = DEST / "download_manifest.json"
    content = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    if output.exists() and output.read_text() != content:
        raise RuntimeError("Existing provenance differs; refusing overwrite")
    if not output.exists():
        output.write_text(content)
    print(json.dumps({"path": str(output), "model_bytes": EXPECTED_BYTES, "sha256": EXPECTED_SHA}))


if __name__ == "__main__":
    main()

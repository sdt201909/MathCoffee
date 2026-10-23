"""Versioned, renderer-neutral media boundaries with an integer-frame clock.

Renderers exchange local files and receipts, not untyped shell commands. A v1
timeline has one mixed audio track and one caption track. Clip audio is muted.
The public asset directory is a small staging area, never the project root.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from fractions import Fraction
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA_VERSION = 1
SHA256 = re.compile(r"[0-9a-f]{64}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _integer(value: Any, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def local_asset(directory: Path, name: str) -> Path:
    """Resolve a renderer asset without URLs, traversal or symlink escapes."""
    if not isinstance(name, str) or not name or "\\" in name or ":" in name:
        raise ValueError("asset file must be a relative POSIX path")
    relative = PurePosixPath(name)
    if relative.is_absolute() or any(part in ("..", ".") for part in relative.parts):
        raise ValueError("asset path must remain inside the staging directory")
    directory = directory.resolve(strict=True)
    path = (directory / name).resolve(strict=True)
    if not path.is_relative_to(directory) or not path.is_file():
        raise ValueError("asset must be a regular file inside the staging directory")
    return path


def probe_media(path: Path) -> dict:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _asset(record: dict, directory: Path) -> tuple[Path, dict]:
    expected = record.get("sha256", "")
    if not isinstance(expected, str) or not SHA256.fullmatch(expected):
        raise ValueError("every asset needs its actual SHA-256")
    path = local_asset(directory, record.get("file"))
    if sha256_file(path) != expected:
        raise ValueError(f"asset hash changed: {record['file']}")
    return path, {"file": record["file"], "bytes": path.stat().st_size, "sha256": expected}


def _ordered_intervals(records: list, total: int, name: str) -> None:
    previous = 0
    ids = set()
    for record in records:
        identifier = record.get("id")
        if not isinstance(identifier, str) or not identifier or identifier in ids:
            raise ValueError(f"{name} require unique, nonempty IDs")
        ids.add(identifier)
        start = _integer(record.get("start_frame"), f"{name}.start_frame")
        end = _integer(record.get("end_frame"), f"{name}.end_frame", 1)
        if not previous <= start < end <= total:
            raise ValueError(f"{name} intervals must be ordered, disjoint and inside the timeline")
        previous = end


def validate_timeline(data: dict, asset_directory: Path, *, inspect_media: bool = True) -> dict:
    """Validate the immutable manifest and optionally inspect real media headers.

    End frames are exclusive. v1 uses integral frame rates; nonintegral rates
    need an explicit future schema instead of silently rounding timestamps.
    """
    if type(data.get("schema_version")) is not int or data["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported timeline schema_version")
    width = _integer(data.get("width"), "width", 2)
    height = _integer(data.get("height"), "height", 2)
    fps = _integer(data.get("fps"), "fps", 1)
    total = _integer(data.get("duration_frames"), "duration_frames", 1)
    if width % 2 or height % 2 or fps > 120:
        raise ValueError("H.264 dimensions must be even and v1 fps must not exceed 120")
    clips, captions = data.get("clips"), data.get("captions")
    if not isinstance(clips, list) or not isinstance(captions, list):
        raise ValueError("clips and captions must be arrays")
    bounds, assets = [], []
    for clip in clips:
        if clip.get("renderer") not in {"manim", "remotion"}:
            raise ValueError("unknown clip renderer")
        start = _integer(clip.get("start_frame"), "clip.start_frame")
        length = _integer(clip.get("duration_frames"), "clip.duration_frames", 1)
        source_in = _integer(clip.get("source_in_frame"), "clip.source_in_frame")
        bounds.append({"id": clip.get("id"), "start_frame": start, "end_frame": start + length})
        path, asset = _asset(clip, asset_directory)
        if inspect_media:
            probe = probe_media(path)
            videos = [s for s in probe["streams"] if s["codec_type"] == "video"]
            if len(videos) != 1:
                raise ValueError("clip must have exactly one video stream")
            stream = videos[0]
            if (stream["width"], stream["height"], Fraction(stream["avg_frame_rate"])) != (
                width,
                height,
                fps,
            ):
                raise ValueError("clip geometry/fps differ; explicitly normalize before rendering")
            frames = int(stream.get("nb_frames", 0))
            if not frames or source_in + length > frames:
                raise ValueError("clip source range exceeds its measured frame count")
            asset["probe"] = probe
            asset["audio_policy"] = "muted"
        assets.append(asset)
    _ordered_intervals(bounds, total, "clip")
    _ordered_intervals(captions, total, "caption")
    for caption in captions:
        if not isinstance(caption.get("text"), str) or not caption["text"].strip():
            raise ValueError("caption text must be nonempty")
    audio = data.get("audio")
    if not isinstance(audio, dict):
        raise ValueError("one final mixed audio asset is required")
    rate = _integer(audio.get("sample_rate"), "audio.sample_rate", 1)
    samples = _integer(audio.get("samples"), "audio.samples", 1)
    if rate != 48000 or Fraction(samples, rate) != Fraction(total, fps):
        raise ValueError("audio must contain exactly the timeline duration at 48000 Hz")
    path, asset = _asset(audio, asset_directory)
    if inspect_media:
        probe = probe_media(path)
        streams = [s for s in probe["streams"] if s["codec_type"] == "audio"]
        if len(streams) != 1 or any(s["codec_type"] == "video" for s in probe["streams"]):
            raise ValueError("mixed audio asset must have exactly one audio stream and no video")
        stream = streams[0]
        measured = Fraction(stream["duration_ts"]) * Fraction(stream["time_base"]) * rate
        if int(stream["sample_rate"]) != rate or stream["channels"] != 2 or measured != samples:
            raise ValueError("mixed audio header differs from declared sample rate/count/channels")
        asset["probe"] = probe
    assets.append(asset)
    anchors = data.get("qa", {}).get("anchor_frames", [])
    if not isinstance(anchors, list) or len(set(anchors)) != len(anchors):
        raise ValueError("QA anchor frames must be a unique list")
    for frame in anchors:
        if _integer(frame, "qa.anchor_frame") + 2 > total:
            raise ValueError("QA marker extends beyond the timeline")
    return {
        "status": "PASS",
        "schema_version": SCHEMA_VERSION,
        "width": width,
        "height": height,
        "fps": fps,
        "frames": total,
        "duration_seconds": total / fps,
        "audio_samples": samples,
        "clips": len(clips),
        "captions": len(captions),
        "assets": assets,
        "boundaries": "[start_frame, end_frame)",
        "mixed_audio_owner": "upstream mixer",
        "caption_owner": "final composition",
        "media_headers_inspected": inspect_media,
    }

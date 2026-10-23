"""Verify actual encoded containers and input identity, without claiming human review."""

from __future__ import annotations

import json
import math
import subprocess
from fractions import Fraction
from pathlib import Path


def verify_artifacts(workspace: Path, manifest: dict) -> None:
    from .pipeline import file_hash, workspace_file
    workspace = Path(workspace).resolve(strict=True)
    outputs = manifest.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        raise ValueError("build manifest has no hashed artifact inventory")
    found = set()
    for item in outputs:
        path = workspace_file(workspace, item["path"])
        if path in found or path.is_symlink():
            raise ValueError("build artifact inventory has duplicate paths or symlinks")
        found.add(path)
        if file_hash(path) != item["sha256"] or ("bytes" in item and path.stat().st_size != item["bytes"]):
            raise ValueError(f"build artifact changed after rendering: {path.name}")
    required = {workspace_file(workspace, manifest[field])
                for field in ("timeline", "schedule", "display_manifest")}
    required.add(workspace_file(workspace, manifest["output"]["path"]))
    if not required.issubset(found):
        raise ValueError("build artifact inventory omits a consumed timeline, schedule, display manifest or film")


def _video_frames(video: Path, timeline: dict, style: dict) -> dict:
    import av
    import numpy as np
    width, height, fps = (timeline[key] for key in ("width", "height", "fps"))
    rect = style["layout"]["caption_rect"]
    scale_x, scale_y = width / style["render"]["width"], height / style["render"]["height"]
    x, y, rw, rh = [round(v * (scale_x if i % 2 == 0 else scale_y)) for i, v in enumerate(rect)]
    expected_text = np.array([int(style["colors"]["text"][i:i + 2], 16) for i in (1, 3, 5)])
    captions = timeline["captions"]
    count, pixels_checked = 0, 0
    with av.open(str(video)) as container:
        if len(container.streams.video) != 1:
            raise ValueError("final container must contain exactly one video stream")
        stream = container.streams.video[0]
        if stream.codec_context.name != "h264":
            raise ValueError("delivery video must be H.264")
        if Fraction(stream.average_rate) != fps:
            raise ValueError("actual video FPS differs from authored timeline")
        for frame in container.decode(stream):
            if (frame.width, frame.height) != (width, height):
                raise ValueError("actual encoded dimensions differ from authored timeline")
            if frame.pts is None or frame.time_base is None or Fraction(frame.pts) * frame.time_base != Fraction(count, fps):
                raise ValueError("encoded video timestamps are not the complete regular frame grid")
            present = any(caption["start_frame"] <= count < caption["end_frame"] for caption in captions)
            if present:
                pixels = frame.to_ndarray(format="rgb24")[y:y + rh, x:x + rw]
                hits = np.count_nonzero(np.max(np.abs(pixels.astype(np.int16) - expected_text), axis=2) < 35)
                if hits < 3:
                    raise ValueError(f"declared caption is absent from the encoded caption region at frame {count}")
                pixels_checked += 1
            count += 1
    if count != timeline["duration_frames"]:
        raise ValueError(f"decoded frame count differs: {count} != {timeline['duration_frames']}")
    return {"status": "PASS", "decoded_frames": count, "pts": "complete regular grid",
            "width": width, "height": height, "fps": fps, "caption_active_frames_checked": pixels_checked,
            "caption_pixel_scope": "foreground presence during declared windows, not OCR or complete absence proof"}


def _audio(video: Path, timeline: dict, schedule: dict, directory: Path, premix: dict | None) -> dict:
    from .renderer_contract import probe_media
    streams = probe_media(video)["streams"]
    audio_streams = [stream for stream in streams if stream["codec_type"] == "audio"]
    if timeline["audio"] is None:
        if audio_streams:
            raise ValueError("explicit silent delivery unexpectedly contains an audio track")
        return {"status": "PASS", "mode": "explicit_silent", "audio_streams": 0}
    if len(audio_streams) != 1:
        raise ValueError("delivery must contain exactly one premixed audio stream")
    from .audio_validation import checked_audio_cache
    from .pipeline import file_hash
    samples = timeline["audio"]["samples"]
    cache_dir = directory / "audio-qa"
    cache_dir.mkdir(exist_ok=True)
    pcm, native, reused = checked_audio_cache(cache_dir, video, file_hash(video), samples)
    import numpy as np
    from scipy.signal import correlate
    from .pipeline import _decode_pcm
    encoded = np.memmap(pcm, dtype="<f4", mode="r").reshape(-1, 2)[:samples]
    reference, _ = _decode_pcm(Path(premix["path"]))
    if len(reference) != samples:
        raise ValueError("master premix changed its exact timeline duration")
    checks = []
    windows = [(cue["id"], cue["active_start_seconds"], cue["active_end_seconds"])
               for scene in schedule["scenes"] for cue in scene["sentences"] if "audio" in cue]
    if not windows:
        windows = [("premix", 0, samples / 48000)]
    for identifier, start, end in windows:
        first, last = round(start * 48000), min(round(end * 48000), round(start * 48000) + 120000)
        a = np.mean(reference[first:last], axis=1).astype(np.float64)
        b = np.mean(encoded[first:last], axis=1).astype(np.float64)
        if len(a) < 2048 or float(np.sqrt(np.mean(a * a))) < 1e-5:
            checks.append({"id": identifier, "status": "not_measurable", "reason": "short or silent source window"})
            continue
        a -= a.mean()
        b -= b.mean()
        zero = len(a) - 1
        cross = correlate(b, a, mode="full", method="fft")
        radius = min(4800, len(a) // 4)
        lag = int(np.argmax(cross[zero - radius:zero + radius + 1]) - radius)
        correlation = float(np.dot(a, b) / math.sqrt(np.dot(a, a) * np.dot(b, b)))
        if abs(lag) > 48 or correlation < 0.95:
            raise ValueError(f"encoded audio differs from its master near cue {identifier}: lag={lag}, correlation={correlation:.5f}")
        checks.append({"id": identifier, "status": "PASS", "lag_samples": lag,
                       "correlation": correlation, "checked_samples": len(a)})
    loudness = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(video),
                               "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"],
                              capture_output=True, text=True, check=True)
    loudness_path = directory / "loudness.log"
    loudness_path.write_text(loudness.stderr)
    return {"status": "PASS", "mode": "native_aac", "native": native, "cache_reused": reused,
            "encoded_sync": checks, "loudness_log": str(loudness_path),
            "scope": "native duration, PCM correlation and sync; loudness log is a measurement, not listening acceptance"}


def verify_build(workspace: str | Path, quality="draft", manifest_path: str | Path | None = None,
                 *, historical=False) -> dict:
    from .pipeline import file_hash, read, source_freshness, workspace_file, write
    workspace = Path(workspace).resolve(strict=True)
    if quality not in {"draft", "final"}:
        raise ValueError("quality must be draft or final")
    if manifest_path is None:
        latest = read(workspace / "build" / "latest.json")
        manifest_path = workspace / "build" / latest["identity"][:16] / quality / "manifest.json"
    path = workspace_file(workspace, manifest_path)
    manifest = read(path)
    if manifest["quality"] != quality:
        raise ValueError("manifest quality differs from requested verification")
    verify_artifacts(workspace, manifest)
    freshness = source_freshness(workspace, manifest)
    if freshness["status"] != "fresh" and not historical:
        raise ValueError("build sources are stale or unrecorded; rebuild or explicitly request historical artifact verification")
    output = workspace_file(workspace, manifest["output"]["path"])
    if file_hash(output) != manifest["output"]["sha256"]:
        raise ValueError("final container changed after rendering")
    directory = workspace_file(workspace, manifest["timeline"]).parent
    timeline, schedule = read(manifest["timeline"]), read(manifest["schedule"])
    style = manifest["plan"]["style"]
    if not style["layout"]["caption_enabled"] and timeline["captions"]:
        raise ValueError("caption-disabled style must have no rendered caption intervals")
    for scene in manifest["stages"]:
        for item in scene["outputs"]:
            if file_hash(workspace_file(workspace, item["path"])) != item["sha256"]:
                raise ValueError("a source clip or display receipt changed after rendering")
        receipt = read(scene["display_receipt"])
        if not receipt.get("entries") or not all(item["inside_allocated_rect"] for item in receipt["layout"]):
            raise ValueError("scene lacks complete display entries or its measured layout fails")
    from .audience import check_audience
    display = read(manifest["display_manifest"])
    engine = manifest["plan"]["project"].get("runtime", {}).get("remotion_root")
    source_roots = [workspace, Path(__file__).parent]
    if engine:
        source_roots.append(Path(engine).resolve())
    audience = check_audience(manifest["plan"]["authoring"], display_manifest=display,
                              timeline=schedule, authoring_sha256=manifest["plan"]["source_sha256"]["authoring"],
                              root=workspace, source_roots=source_roots)
    if audience["status"] != "DECLARED_SURFACES_TEXT_PASS":
        write(directory / "audience.json", audience)
        raise ValueError(f"audience text validation blocked; see {directory / 'audience.json'}")
    video = _video_frames(output, timeline, style)
    audio = _audio(output, timeline, schedule, directory, manifest.get("premix"))
    result = {"schema_version": 1, "identity": manifest["identity"], "technical_status": "PASS",
              "output": str(output), "sha256": file_hash(output), "video": video, "audio": audio,
              "source_freshness": freshness,
              "verification_scope": "current_project" if freshness["status"] == "fresh" else "historical_artifact",
              "audience": audience, "reviews": manifest["reviews"],
              "human_acceptance": "pending; automated verification cannot sign mathematical, editorial, visual or listening review"}
    write(directory / "verification.json", result)
    return result

#!/usr/bin/env python3
"""Generate three original theme beds and optionally mix a local narration WAV.

Examples (existing project environment, no network):
  .venv/bin/python scripts/create_theme_music.py
  .venv/bin/python scripts/create_theme_music.py --theme 数学 --mood 好奇 \
    --voice media/audio/my_voice_48k.wav --duration 24

Voice WAV must be uncompressed PCM at the chosen rate; resampling is explicit
in the existing audio pipeline, never silently done here. Only outputs with
verified hashes in manifest.json have status generated_and_verified.
The output directory must be new or empty; use a new --output-dir for each run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mathcoffee.music_library import (  # noqa: E402
    SYNTHESIS_VERSION,
    audio_metrics,
    generate_track,
    load_catalog,
    mix_narration,
    select_track,
)


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_wav(path: Path) -> tuple[int, np.ndarray]:
    with wave.open(str(path), "rb") as stream:
        if stream.getcomptype() != "NONE" or stream.getsampwidth() not in (2, 3, 4):
            raise ValueError("voice must be signed PCM16/24/32 WAV")
        if stream.getnchannels() not in (1, 2):
            raise ValueError("voice must be mono or stereo")
        raw = stream.readframes(stream.getnframes())
        width = stream.getsampwidth()
        if width == 3:
            octets = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
            values = octets[:, 0] | (octets[:, 1] << 8) | (octets[:, 2] << 16)
            values = (values ^ 0x800000) - 0x800000
        else:
            values = np.frombuffer(raw, dtype="<i2" if width == 2 else "<i4")
        return stream.getframerate(), values.reshape(-1, stream.getnchannels()) / 2 ** (
            8 * width - 1
        )


def write_wav(path: Path, audio: np.ndarray, sample_rate: int) -> dict:
    if not np.isfinite(audio).all() or np.max(np.abs(audio)) >= 1:
        raise ValueError("non-finite or clipping output")
    pcm = np.rint(audio * 32767).astype("<i2")
    with path.open("xb") as output, wave.open(output, "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(sample_rate)
        stream.writeframes(pcm.tobytes())
    rate, decoded = read_wav(path)
    if rate != sample_rate or decoded.shape != audio.shape:
        raise RuntimeError("written WAV changed length, channel count or sample rate")
    return {
        "path": str(path.resolve()),
        "status": "generated_and_verified",
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
        "sample_rate": rate,
        "channels": 2,
        "format": "pcm_s16le",
        "duration_seconds": len(decoded) / rate,
        "decoded_metrics": audio_metrics(decoded),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=ROOT / "src/mathcoffee/data/audio/music_catalog.json")
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "media/audio/agent_upgrade_demo/music"
    )
    parser.add_argument("--duration", type=float, default=24.0)
    parser.add_argument("--sample-rate", type=int, default=48_000)
    parser.add_argument("--seed", type=int, default=20260930)
    parser.add_argument("--theme", default="mathematics")
    parser.add_argument("--mood", default="curious")
    parser.add_argument("--section", default="explanation")
    parser.add_argument("--voice", type=Path)
    parser.add_argument("--voice-offset", type=float, default=0.0)
    parser.add_argument(
        "--activity-json",
        type=Path,
        help="JSON [[start,end],...] in output timeline seconds; optional RMS override",
    )
    args = parser.parse_args()
    if args.output_dir.exists() and (
        not args.output_dir.is_dir() or any(args.output_dir.iterdir())
    ):
        parser.error("output directory must be new or empty; choose another --output-dir")
    catalog = load_catalog(args.catalog)
    selected = select_track(catalog, args.theme, args.mood, args.seed, args.section)
    voice = None
    voice_sha256 = None
    activity = None
    activity_sha256 = None
    if args.voice:
        voice_sha256 = sha256(args.voice)
        rate, voice = read_wav(args.voice)
        if sha256(args.voice) != voice_sha256:
            parser.error("voice source changed while reading; retry with a stable input")
        if rate != args.sample_rate:
            parser.error(f"voice is {rate} Hz; explicitly resample to {args.sample_rate} Hz first")
        if not np.isfinite(args.voice_offset) or args.voice_offset < 0:
            parser.error("voice offset must be finite and nonnegative")
        voice = np.pad(voice, ((round(args.voice_offset * rate), 0), (0, 0)))
        if len(voice) > round(args.duration * rate):
            parser.error(
                "voice exceeds requested program; increase --duration, never truncate words"
            )
        if args.activity_json:
            activity_bytes = args.activity_json.read_bytes()
            activity = json.loads(activity_bytes)
            activity_sha256 = hashlib.sha256(activity_bytes).hexdigest()
    elif args.activity_json:
        parser.error("--activity-json requires --voice")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    selected_audio = None
    for track in catalog["tracks"]:
        audio = generate_track(track, args.duration, args.sample_rate, args.seed)
        if track["id"] == selected["id"]:
            selected_audio = audio
        result = write_wav(args.output_dir / f"{track['id']}.wav", audio, args.sample_rate)
        result.update(
            {
                "track_id": track["id"],
                "recipe": track["recipe"],
                "bpm": track["bpm"],
                "track_metadata": track,
            }
        )
        outputs.append(result)
    manifest = {
        "schema_version": 1,
        "synthesis_version": SYNTHESIS_VERSION,
        "generator": "scripts/create_theme_music.py",
        "source_sha256": {
            "scripts/create_theme_music.py": sha256(Path(__file__)),
            "src/mathcoffee/music_library.py": sha256(ROOT / "src/mathcoffee/music_library.py"),
            "catalog": sha256(args.catalog),
        },
        "environment": {"python": platform.python_version(), "numpy": np.__version__},
        "license": catalog["license"],
        "parameters": {
            "duration_seconds": args.duration,
            "sample_rate": args.sample_rate,
            "seed": args.seed,
        },
        "selection": {
            "theme": args.theme,
            "mood": args.mood,
            "section": args.section,
            "selected_track": selected["id"],
            "rule": "mood=4, theme=3, section=1; hash tie",
        },
        "outputs": outputs,
        "limitations": [
            "Three procedural recipes, not a mature multi-track music collection.",
            "RMS/sample peak measurements are not LUFS/true peak.",
            "Automated waveform checks do not substitute for listening.",
        ],
    }
    if voice is not None:
        mixed, report = mix_narration(
            selected_audio,
            voice,
            args.sample_rate,
            music_gain_db=selected["mix_gain_db"],
            duck_db=selected["duck_db"],
            activity_intervals=activity,
        )
        manifest["mix"] = {
            **write_wav(args.output_dir / "narration_mix.wav", mixed, args.sample_rate),
            "voice_path": str(args.voice.resolve()),
            "voice_sha256": voice_sha256,
            "voice_offset_seconds": args.voice_offset,
            "activity_json_sha256": activity_sha256,
            "report": report,
        }
    target = args.output_dir / "manifest.json"
    with target.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "manifest": str(target.resolve()),
                "tracks": len(outputs),
                "selected": selected["id"],
                "mixed": voice is not None,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

"""Shared native AAC validation and immutable decoded-PCM QA cache.

Extracted unchanged from the rejected episode's verifier. Valid duration is
checked before exporting PCM; decoder end padding is accounted for explicitly.
"""
from __future__ import annotations

import json
import subprocess
from fractions import Fraction
from pathlib import Path

import av

from mathcoffee.renderer_contract import sha256_file

RATE = 48000
PCM_EXPORT_POLICY = "exact-container-duration-or-complete-native-aac-frames-v1"


def read(path):
    return json.loads(Path(path).read_text())


def integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def validate_native_audio(video, expected_samples):
    """Decode original AAC timestamps before any format conversion can hide them."""
    integer(expected_samples, "expected audio samples", 1)
    count, frame_count = 0, 0
    with av.open(str(video)) as container:
        if len(container.streams.video) != 1 or len(container.streams.audio) != 1:
            raise ValueError("expected one original video and one original audio stream")
        stream = container.streams.audio[0]
        codec = stream.codec_context
        if codec.name != "aac" or codec.sample_rate != RATE or len(codec.layout.channels) != 2:
            raise ValueError("native delivery audio must be AAC, 48000 Hz, two channels")
        if stream.start_time is None or Fraction(stream.start_time) * stream.time_base != 0:
            raise ValueError("native audio stream has a missing or nonzero start timestamp")
        if (
            stream.duration is None
            or Fraction(stream.duration) * stream.time_base * RATE != expected_samples
        ):
            raise ValueError("container audio duration differs from the exact master")
        duration_ticks, time_base = stream.duration, str(stream.time_base)
        for frame in container.decode(stream):
            if frame.pts is None or frame.time_base is None:
                raise ValueError("decoded native audio frame has no timestamp")
            position = Fraction(frame.pts) * frame.time_base * RATE
            if position != count:
                raise ValueError(
                    f"native audio PTS gap/offset: {position} samples, expected {count}"
                )
            if frame.sample_rate != RATE or len(frame.layout.channels) != 2 or frame.samples <= 0:
                raise ValueError("native audio format changed during playback")
            if count >= expected_samples:
                raise ValueError("native AAC includes a complete frame beyond container duration")
            count += frame.samples
            frame_count += 1
    if not frame_count or not 0 <= count - expected_samples <= 2048:
        raise ValueError("native AAC sample duration differs from the exact master")
    return {
        "codec": "aac",
        "sample_rate": RATE,
        "channels": 2,
        "first_pts_samples": 0,
        "all_frame_timestamps": "PASS",
        "frames_decoded": frame_count,
        "decoded_samples": count,
        "container_valid_samples": expected_samples,
        "container_duration_ticks": duration_ticks,
        "container_time_base": time_base,
        "aac_padding_samples": count - expected_samples,
        "pyav_version": av.__version__,
        "pyav_library_versions": {key: list(value) for key, value in av.library_versions.items()},
    }


def pcm_export_metadata(size, native, expected_samples):
    """Account for decoder end-padding semantics without accepting arbitrary truncation."""
    if (
        (
            native["codec"],
            native["sample_rate"],
            native["channels"],
            native["first_pts_samples"],
        )
        != ("aac", RATE, 2, 0)
        or native["container_valid_samples"] != expected_samples
        or Fraction(native["container_duration_ticks"])
        * Fraction(native["container_time_base"])
        * RATE
        != expected_samples
        or native["aac_padding_samples"] != native["decoded_samples"] - expected_samples
        or not 0 <= native["aac_padding_samples"] <= 2048
        or native.get("all_frame_timestamps") != "PASS"
    ):
        raise ValueError("QA native-audio receipt is inconsistent; choose a new --qa-dir")
    samples, remainder = divmod(size, 8)
    if remainder or samples not in {expected_samples, native["decoded_samples"]}:
        raise ValueError(
            "PCM export must equal container valid duration or native complete AAC frames; "
            "unreceipted file retained"
        )
    return {
        "policy": PCM_EXPORT_POLICY,
        "samples": samples,
        "valid_samples": expected_samples,
        "tail_padding_samples": samples - expected_samples,
        "decoder_length_semantics": (
            "container_valid_samples"
            if samples == expected_samples
            else "native_aac_frames_including_tail_padding"
        ),
        "waveform_transformation": "none; native-rate stereo float export only",
    }


def checked_audio_cache(report_dir, video, video_hash, expected_samples):
    """Reuse only a PCM file bound to this exact video and a successful native check."""
    audio_path = report_dir / "decoded_audio.f32"
    receipt_path = report_dir / "decoded_audio.f32.json"
    identity = {
        "schema_version": 2,
        "video_sha256": video_hash,
        "verifier_sha256": sha256_file(Path(__file__)),
        "expected_samples": expected_samples,
        "pyav_version": av.__version__,
        "pyav_library_versions": {key: list(value) for key, value in av.library_versions.items()},
        "ffmpeg_version": subprocess.run(
            ["ffmpeg", "-version"], check=True, capture_output=True, text=True
        ).stdout.strip(),
        "pcm_export_policy": PCM_EXPORT_POLICY,
    }
    if audio_path.exists() or receipt_path.exists():
        if not audio_path.is_file() or not receipt_path.is_file():
            raise ValueError("unreceipted QA audio retained; choose a new --qa-dir")
        receipt = read(receipt_path)
        if receipt.get("identity") != identity or receipt.get("status") != "PASS":
            raise ValueError("QA audio belongs to different inputs/checks; choose a new --qa-dir")
        if (
            audio_path.stat().st_size != receipt["bytes"]
            or sha256_file(audio_path) != receipt["sha256"]
            or receipt["native_audio"].get("all_frame_timestamps") != "PASS"
        ):
            raise ValueError("QA audio or its receipt changed; choose a new --qa-dir")
        native = receipt["native_audio"]
        metadata = pcm_export_metadata(receipt["bytes"], native, expected_samples)
        if receipt.get("pcm_export") != metadata:
            raise ValueError("QA PCM receipt is inconsistent; choose a new --qa-dir")
        return audio_path, native, True
    native = validate_native_audio(video, expected_samples)
    # Deliberately omit -ar and -ac: native format has already been checked.
    command = [
        "ffmpeg",
        "-v",
        "error",
        "-nostdin",
        "-n",
        "-i",
        str(video),
        "-map",
        "0:a:0",
        "-f",
        "f32le",
        "-acodec",
        "pcm_f32le",
        str(audio_path),
    ]
    subprocess.run(command, check=True)
    size = audio_path.stat().st_size
    # FFmpeg versions differ in honoring the final packet's discard_padding.
    # Accept only the two exact, independently established lengths. No -t,
    # resampling, padding, trimming or waveform adjustment is performed here.
    pcm_export = pcm_export_metadata(size, native, expected_samples)
    receipt = {
        "status": "PASS",
        "identity": identity,
        "native_audio": native,
        "pcm_export": pcm_export,
        "command": command,
        "bytes": size,
        "sha256": sha256_file(audio_path),
    }
    temporary = receipt_path.with_suffix(".tmp.json")
    temporary.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(receipt_path)
    return audio_path, native, False

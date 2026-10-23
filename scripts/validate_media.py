#!/usr/bin/env python3
"""Decode a rendered video and validate its core stream properties."""

from __future__ import annotations

import argparse
import math
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def positive_fraction(value: str) -> Fraction:
    try:
        parsed = Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise argparse.ArgumentTypeError(
            "must be a positive number or fraction, such as 60 or 30000/1001"
        ) from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return parsed


def positive_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be a finite number greater than zero")
    return parsed


def nonnegative_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0:
        raise argparse.ArgumentTypeError("must be a finite number that is zero or greater")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Open a video with PyAV, decode every frame, and optionally check "
            "its dimensions, frame rate, codec, audio stream count, and duration."
        )
    )
    parser.add_argument("video", type=Path, help="video file produced by Manim")
    parser.add_argument(
        "--width",
        "--expected-width",
        dest="expected_width",
        type=positive_int,
        help="expected video width in pixels",
    )
    parser.add_argument(
        "--height",
        "--expected-height",
        dest="expected_height",
        type=positive_int,
        help="expected video height in pixels",
    )
    parser.add_argument(
        "--fps",
        "--expected-fps",
        dest="expected_fps",
        type=positive_fraction,
        help="expected average frame rate (for example 60 or 30000/1001)",
    )
    parser.add_argument(
        "--fps-tolerance",
        type=nonnegative_float,
        default=0.01,
        help="maximum absolute FPS difference allowed (default: 0.01)",
    )
    parser.add_argument(
        "--codec",
        "--expected-codec",
        dest="expected_codec",
        help="expected video codec name reported by PyAV (for example h264)",
    )
    parser.add_argument(
        "--audio-streams",
        "--expected-audio-streams",
        dest="expected_audio_streams",
        type=nonnegative_int,
        help="expected number of audio streams (use 0 for silent deliverables)",
    )
    parser.add_argument(
        "--duration",
        "--expected-duration",
        dest="expected_duration",
        type=positive_float,
        help="expected duration in seconds; checked against decoded frame count",
    )
    parser.add_argument(
        "--frames",
        "--expected-frames",
        dest="expected_frames",
        type=positive_int,
        help="expected number of decoded video frames",
    )
    parser.add_argument(
        "--duration-tolerance-frames",
        "--frame-tolerance",
        dest="duration_tolerance_frames",
        type=nonnegative_int,
        default=1,
        help="allowed decoded-frame difference for duration/frame checks (default: 1)",
    )
    return parser


def stream_rate(stream: Any) -> Fraction | None:
    for attribute in ("average_rate", "base_rate", "guessed_rate"):
        rate = getattr(stream, attribute, None)
        if rate is None:
            continue
        try:
            numerator = int(rate.numerator)
            denominator = int(rate.denominator)
            if numerator > 0 and denominator > 0:
                return Fraction(numerator, denominator)
        except (AttributeError, TypeError, ValueError, ZeroDivisionError):
            continue
    return None


def fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 1


def main() -> int:
    args = build_parser().parse_args()
    video_path = args.video.expanduser().resolve()

    if not video_path.is_file():
        return fail(f"video file does not exist: {video_path}")
    if video_path.stat().st_size == 0:
        return fail(f"video file is empty: {video_path}")

    try:
        import av
    except ImportError:
        return fail(
            "PyAV is not installed in this Python environment. "
            "Run this script with 'uv run python scripts/validate_media.py ...'."
        )

    try:
        with av.open(str(video_path), mode="r") as container:
            if not container.streams.video:
                return fail(f"no video stream found in: {video_path}")

            stream = container.streams.video[0]
            rate = stream_rate(stream)
            codec_name = stream.codec_context.name or "unknown"
            audio_streams = len(container.streams.audio)
            stream_width = int(stream.codec_context.width or 0)
            stream_height = int(stream.codec_context.height or 0)

            decoded_frames = 0
            decoded_width = 0
            decoded_height = 0
            for frame in container.decode(stream):
                decoded_frames += 1
                if decoded_frames == 1:
                    decoded_width = int(frame.width)
                    decoded_height = int(frame.height)
                elif frame.width != decoded_width or frame.height != decoded_height:
                    return fail(
                        "video dimensions change during decoding: "
                        f"frame 1 is {decoded_width}x{decoded_height}, "
                        f"frame {decoded_frames} is {frame.width}x{frame.height}"
                    )

            container_duration = container.duration
    except Exception as exc:
        return fail(f"PyAV could not fully decode '{video_path}': {type(exc).__name__}: {exc}")

    if decoded_frames == 0:
        return fail(f"video stream contains no decodable frames: {video_path}")

    actual_width = decoded_width or stream_width
    actual_height = decoded_height or stream_height
    if actual_width <= 0 or actual_height <= 0:
        return fail(f"decoded video has invalid dimensions: {actual_width}x{actual_height}")
    if (
        stream_width > 0
        and stream_height > 0
        and (stream_width != actual_width or stream_height != actual_height)
    ):
        return fail(
            "stream metadata dimensions do not match decoded frames: "
            f"metadata={stream_width}x{stream_height}, "
            f"decoded={actual_width}x{actual_height}"
        )

    if args.expected_width is not None and actual_width != args.expected_width:
        return fail(f"expected width {args.expected_width}, decoded {actual_width}: {video_path}")
    if args.expected_height is not None and actual_height != args.expected_height:
        return fail(
            f"expected height {args.expected_height}, decoded {actual_height}: {video_path}"
        )
    if args.expected_fps is not None:
        if rate is None:
            return fail(
                f"expected {float(args.expected_fps):g} FPS, "
                "but the video stream has no usable frame-rate metadata"
            )
        fps_difference = abs(float(rate) - float(args.expected_fps))
        if fps_difference > args.fps_tolerance:
            return fail(
                f"expected {float(args.expected_fps):g} FPS "
                f"(tolerance {args.fps_tolerance:g}), "
                f"but decoded metadata reports {float(rate):g} FPS"
            )
    if args.expected_codec is not None:
        if codec_name.casefold() != args.expected_codec.casefold():
            return fail(
                f"expected codec {args.expected_codec!r}, "
                f"but video stream reports {codec_name!r}: {video_path}"
            )
    if args.expected_audio_streams is not None and audio_streams != args.expected_audio_streams:
        return fail(
            f"expected {args.expected_audio_streams} audio stream(s), "
            f"found {audio_streams}: {video_path}"
        )

    if args.expected_frames is not None:
        frame_difference = abs(decoded_frames - args.expected_frames)
        if frame_difference > args.duration_tolerance_frames:
            return fail(
                f"expected {args.expected_frames} decoded frame(s) "
                f"(tolerance {args.duration_tolerance_frames}), "
                f"decoded {decoded_frames}: {video_path}"
            )

    if args.expected_duration is not None:
        duration_rate = args.expected_fps or rate
        if duration_rate is None:
            return fail(
                f"duration validation needs --fps or usable frame-rate metadata: {video_path}"
            )
        exact_expected_frames = args.expected_duration * float(duration_rate)
        rounded_expected_frames = round(exact_expected_frames)
        if not math.isclose(exact_expected_frames, rounded_expected_frames, abs_tol=1e-7):
            return fail(
                f"expected duration {args.expected_duration:g}s at "
                f"{float(duration_rate):g} FPS does not represent a whole number of frames "
                f"({exact_expected_frames:g})"
            )
        frame_difference = abs(decoded_frames - rounded_expected_frames)
        if frame_difference > args.duration_tolerance_frames:
            return fail(
                f"expected duration {args.expected_duration:g}s = "
                f"{rounded_expected_frames} frame(s) at {float(duration_rate):g} FPS "
                f"(tolerance {args.duration_tolerance_frames}), "
                f"decoded {decoded_frames}: {video_path}"
            )

    fps_text = "unknown"
    if rate is not None:
        fps_text = f"{float(rate):g}"
        if rate.denominator != 1:
            fps_text += f" ({rate})"

    duration_seconds: float | None = None
    if container_duration is not None:
        # PyAV exposes container duration in AV_TIME_BASE (microseconds).
        duration_seconds = float(container_duration) / 1_000_000
    elif rate is not None:
        duration_seconds = decoded_frames / float(rate)

    duration_text = f"{duration_seconds:.3f}s" if duration_seconds is not None else "unknown"
    print(f"Video validation passed: {video_path}")
    print(
        f"  codec={codec_name}, dimensions={actual_width}x{actual_height}, "
        f"fps={fps_text}, frames={decoded_frames}, duration={duration_text}, "
        f"audio_streams={audio_streams}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Auditable local music recipes, deterministic selection, and narration ducking.

The three recipes are a starter palette, not downloaded/licensed commercial music.
Catalog entries describe recipes; only a generated file's manifest proves availability.
Measurements here are sample peak and RMS, not LUFS or oversampled true peak.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

SYNTHESIS_VERSION = "1.0.0"
RECIPES = {"warm_pad_chimes_v1", "exploration_arpeggio_v1", "suspense_pedal_v1"}


def load_catalog(path: str | Path) -> dict[str, Any]:
    catalog = json.loads(Path(path).read_text(encoding="utf-8"))
    if catalog.get("schema_version") != 1 or not catalog.get("license", {}).get("source"):
        raise ValueError("unsupported or unattributed music catalog")
    tracks = catalog.get("tracks", [])
    if not tracks or len({track["id"] for track in tracks}) != len(tracks):
        raise ValueError("music catalog must contain unique track IDs")
    for track in tracks:
        if track["recipe"] not in RECIPES or track["asset_status"] != "generated_on_demand":
            raise ValueError("catalog must name an implemented, generated-on-demand recipe")
        if not track["themes"] or not track["moods"] or not track["sections"]:
            raise ValueError("track needs theme, mood and section metadata")
        if not 20 <= track["bpm"] <= 240 or not -60 <= track["target_rms_dbfs"] <= -10:
            raise ValueError("invalid tempo or source music level")
    return catalog


def select_track(
    catalog: dict[str, Any],
    theme: str,
    mood: str,
    seed: int = 0,
    section: str | None = None,
) -> dict[str, Any]:
    """Choose by mood (4), theme (3), section (1); stable hash breaks ties.

    At least one theme OR mood tag must match; both need not match. Only a request
    with no theme/mood match in any track raises. Section alone is insufficient.
    Callers must inspect the returned tags, not assume every requested tag matched.
    Seed changes only ties, never the best tag match.
    """
    theme, mood = theme.strip().casefold(), mood.strip().casefold()
    candidates = []
    for track in catalog["tracks"]:
        score = 3 * (theme in {v.casefold() for v in track["themes"]})
        score += 4 * (mood in {v.casefold() for v in track["moods"]})
        if not score:
            continue
        score += bool(section and section.casefold() in {v.casefold() for v in track["sections"]})
        tie = hashlib.sha256(f"{seed}:{track['id']}".encode()).hexdigest()
        candidates.append((score, tie, track["id"], track))
    if not candidates:
        raise ValueError(f"no catalog music matches theme={theme!r}, mood={mood!r}")
    return max(candidates, key=lambda item: item[:3])[3]


def audio_metrics(audio: np.ndarray) -> dict[str, float | int | None]:
    samples = np.asarray(audio, dtype=np.float64)
    if samples.size == 0 or not np.isfinite(samples).all():
        raise ValueError("audio must be nonempty and finite")
    peak = float(np.max(np.abs(samples)))
    rms = float(np.sqrt(np.mean(samples**2)))
    return {
        "samples": len(samples),
        "peak": peak,
        "sample_peak_dbfs": 20 * math.log10(peak) if peak else None,
        "rms_dbfs": 20 * math.log10(rms) if rms else None,
        "clipped_samples": int(np.count_nonzero(np.abs(samples) >= 1)),
    }


def _stereo(audio: np.ndarray) -> np.ndarray:
    audio = np.asarray(audio, dtype=np.float64)
    if audio.ndim == 1:
        audio = np.repeat(audio[:, None], 2, axis=1)
    elif audio.ndim == 2 and audio.shape[1] == 1:
        audio = np.repeat(audio, 2, axis=1)
    if audio.ndim != 2 or audio.shape[1] != 2 or not len(audio):
        raise ValueError("expected nonempty mono or stereo audio")
    if not np.isfinite(audio).all():
        raise ValueError("audio has non-finite samples")
    return audio


def _sample_rate(sample_rate: int) -> None:
    if isinstance(sample_rate, bool) or int(sample_rate) != sample_rate or sample_rate < 8000:
        raise ValueError("sample rate must be an integer of at least 8000 Hz")


def generate_track(
    track: dict[str, Any], duration_seconds: float, sample_rate: int = 48_000, seed: int = 0
) -> np.ndarray:
    """Synthesize a complete stereo bed; no voice, external samples or recordings.

    Returns exact round(duration * sample_rate) float32 frames. Reproduction is
    sample-deterministic with the same NumPy version, recipe, rate, duration and seed.
    """
    _sample_rate(sample_rate)
    if not np.isfinite(duration_seconds) or not 0.1 <= duration_seconds <= 1800:
        raise ValueError("duration must be between 0.1 and 1800 seconds")
    recipe = track["recipe"]
    if recipe not in RECIPES:
        raise ValueError(f"unknown music recipe: {recipe}")
    samples = round(duration_seconds * sample_rate)
    out = np.zeros((samples, 2), dtype=np.float64)
    rng = np.random.default_rng((int(track["seed"]) + int(seed)) % (2**64))
    beat = 60.0 / track["bpm"]

    def note(
        onset: float, duration: float, midi: float, amplitude: float, pan: float, style: str
    ) -> None:
        start = round(onset * sample_rate)
        end = min(samples, start + round(duration * sample_rate))
        if start >= samples or end <= start:
            return
        age = np.arange(end - start, dtype=float) / sample_rate
        f = 440 * 2 ** ((midi - 69) / 12)
        phase = float(rng.uniform(0, 2 * np.pi))
        wave = np.sin(2 * np.pi * f * age + phase)
        if style == "pad":
            wave += 0.12 * np.sin(2 * np.pi * f * 1.002 * age + phase + 0.6)
            envelope = np.minimum(age / min(1.8, duration / 3), 1)
            envelope *= np.minimum(np.maximum(duration - age, 0) / min(2, duration / 3), 1)
        else:
            wave += 0.22 * np.sin(2 * np.pi * f * (2.01 if style == "chime" else 2) * age)
            envelope = np.minimum(age / 0.015, 1) * np.exp(-age / (duration / 5))
            envelope *= np.clip((duration - age) / 0.03, 0, 1)
        rendered = amplitude * wave * envelope
        out[start:end, 0] += rendered * math.cos((pan + 1) * np.pi / 4)
        out[start:end, 1] += rendered * math.sin((pan + 1) * np.pi / 4)

    if recipe == "warm_pad_chimes_v1":
        chords = ((48, 55, 64, 74), (45, 52, 60, 67), (41, 48, 57, 64), (43, 50, 59, 69))
        for bar, onset in enumerate(np.arange(0, duration_seconds, 8 * beat)):
            for i, midi in enumerate(chords[bar % len(chords)]):
                note(float(onset), 10 * beat, midi, 0.24, (-0.4, 0.3, -0.2, 0.5)[i], "pad")
            note(
                float(onset + 2.5 * beat),
                4 * beat,
                chords[bar % 4][2] + 12,
                0.10,
                (-1) ** bar * 0.55,
                "chime",
            )
    elif recipe == "exploration_arpeggio_v1":
        chords = (
            (50, 57, 62, 66, 69, 74),
            (47, 54, 59, 62, 66, 71),
            (43, 50, 55, 59, 62, 67),
            (45, 52, 57, 61, 64, 69),
        )
        for i, onset in enumerate(np.arange(0, duration_seconds, beat / 2)):
            chord = chords[(i // 16) % 4]
            note(
                float(onset),
                0.65,
                chord[(0, 2, 3, 1, 4, 2, 5, 3)[i % 8]],
                0.15 if i % 2 else 0.21,
                (-1) ** i * 0.4,
                "pluck",
            )
            if i % 8 == 0:
                note(float(onset), 2.1, chord[0] - 12, 0.27, 0, "pluck")
            if i % 2 == 0:
                note(float(onset), 0.045, 86, 0.065, 0.1, "pluck")
    else:
        for onset in np.arange(0, duration_seconds, 6 * beat):
            note(float(onset), 9 * beat, 38, 0.36, -0.08, "pad")
            note(float(onset), 9 * beat, 45, 0.13, 0.12, "pad")
        onset = 1.6
        i = 0
        while onset < duration_seconds:
            note(onset, 3.8, (63, 57, 64, 58, 69)[i % 5], 0.14, (-1) ** i * 0.6, "chime")
            onset += (2.4, 4.2, 3.1, 5.0)[i % 4]
            i += 1
        # Seeded low-passed air, not a borrowed sound recording.
        noise = rng.standard_normal((math.ceil(samples / 96) + 1, 2))
        time = np.arange(samples) / sample_rate
        for channel in range(2):
            air = np.interp(np.arange(samples) / 96, np.arange(len(noise)), noise[:, channel])
            out[:, channel] += 0.035 * air * np.sin(np.pi * time / 8) ** 4

    time = np.arange(samples) / sample_rate
    fade_in = np.sin(np.pi / 2 * np.clip(time / min(0.8, duration_seconds / 4), 0, 1)) ** 2
    fade_out = (
        np.sin(
            np.pi
            / 2
            * np.clip(((samples - 1) / sample_rate - time) / min(1.6, duration_seconds / 4), 0, 1)
        )
        ** 2
    )
    out *= (fade_in * fade_out)[:, None]
    rms = np.sqrt(np.mean(out**2))
    if rms:
        target = 10 ** (float(track["target_rms_dbfs"]) / 20)
        ceiling = 10 ** (float(track["peak_ceiling_dbfs"]) / 20)
        out *= min(target / rms, ceiling / np.max(np.abs(out)))
    return out.astype(np.float32)


def detect_activity(
    voice: np.ndarray,
    sample_rate: int,
    threshold_dbfs: float = -38,
    window_seconds: float = 0.02,
    bridge_seconds: float = 0.16,
) -> list[tuple[float, float]]:
    """RMS activity detector, not speech recognition; authored intervals can override it."""
    _sample_rate(sample_rate)
    signal = _stereo(voice)
    if not np.isfinite(threshold_dbfs) or not 0.001 <= window_seconds <= 1:
        raise ValueError("invalid activity detector settings")
    if not np.isfinite(bridge_seconds) or bridge_seconds < 0:
        raise ValueError("bridge must be finite and nonnegative")
    width = max(1, round(window_seconds * sample_rate))
    threshold = 10 ** (threshold_dbfs / 20)
    intervals: list[tuple[float, float]] = []
    for first in range(0, len(signal), width):
        last = min(first + width, len(signal))
        if float(np.sqrt(np.mean(signal[first:last] ** 2))) < threshold:
            continue
        start, end = first / sample_rate, last / sample_rate
        if intervals and start - intervals[-1][1] <= bridge_seconds + 1e-9:
            intervals[-1] = (intervals[-1][0], end)
        else:
            intervals.append((start, end))
    return intervals


def duck_music(
    music: np.ndarray,
    voice: np.ndarray,
    sample_rate: int,
    activity_intervals: list[tuple[float, float]] | None = None,
    duck_db: float = 12,
    attack_seconds: float = 0.04,
    release_seconds: float = 0.35,
    hold_seconds: float = 0.10,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Offline look-ahead duck: fully lowered at speech onset; smooth release.

    Explicit intervals are seconds in the shared timeline (not per-clip offsets).
    Close/overlapping intervals combine by minimum gain, without pumping upwards.
    """
    _sample_rate(sample_rate)
    music, voice = _stereo(music), _stereo(voice)
    if len(music) != len(voice):
        raise ValueError("ducking inputs must share the exact timeline length")
    if not all(np.isfinite(v) for v in (duck_db, attack_seconds, release_seconds, hold_seconds)):
        raise ValueError("ducking settings must be finite")
    if not 0 <= duck_db <= 60 or min(attack_seconds, release_seconds) <= 0 or hold_seconds < 0:
        raise ValueError("invalid ducking amount, attack, release or hold")
    intervals = (
        detect_activity(voice, sample_rate) if activity_intervals is None else activity_intervals
    )
    gain = np.ones(len(music), dtype=np.float64)
    reduced = 10 ** (-duck_db / 20)
    for start, end in intervals:
        if not np.isfinite(start + end) or not 0 <= start < end <= len(music) / sample_rate + 1e-9:
            raise ValueError("activity interval outside audio timeline")
        first = max(0, math.floor((start - attack_seconds) * sample_rate))
        last = min(len(music), math.ceil((end + hold_seconds + release_seconds) * sample_rate))
        time = np.arange(first, last) / sample_rate
        envelope = np.interp(
            time,
            [
                start - attack_seconds,
                start,
                end + hold_seconds,
                end + hold_seconds + release_seconds,
            ],
            [1, reduced, reduced, 1],
        )
        gain[first:last] = np.minimum(gain[first:last], envelope)
    report = {
        "activity_source": "rms_detector" if activity_intervals is None else "authored_intervals",
        "activity_intervals_seconds": [list(interval) for interval in intervals],
        "duck_db": duck_db,
        "attack_seconds": attack_seconds,
        "release_seconds": release_seconds,
        "hold_seconds": hold_seconds,
        "minimum_gain": float(gain.min()),
        "before": audio_metrics(music),
        "after": audio_metrics(music * gain[:, None]),
    }
    return (music * gain[:, None]).astype(np.float32), gain.astype(np.float32), report


def mix_narration(
    music: np.ndarray,
    voice: np.ndarray,
    sample_rate: int,
    music_gain_db: float = 0,
    voice_gain_db: float = 0,
    peak_ceiling_dbfs: float = -1,
    **duck_options: Any,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Pad to longer input, duck, add, then use transparent global gain if needed.

    No clipping/limiter distortion or hidden voice time shift. This is a mixing
    primitive; delivery still needs the project's LUFS/true-peak FFmpeg checks.
    """
    _sample_rate(sample_rate)
    if not all(np.isfinite(v) for v in (music_gain_db, voice_gain_db, peak_ceiling_dbfs)):
        raise ValueError("mix gains must be finite")
    if not -60 <= music_gain_db <= 24 or not -60 <= voice_gain_db <= 24:
        raise ValueError("mix gain must be between -60 and +24 dB")
    if not -24 <= peak_ceiling_dbfs <= 0:
        raise ValueError("sample peak ceiling must be between -24 and 0 dBFS")
    music, voice = _stereo(music), _stereo(voice)
    count = max(len(music), len(voice))
    music = np.pad(music, ((0, count - len(music)), (0, 0))) * 10 ** (music_gain_db / 20)
    voice = np.pad(voice, ((0, count - len(voice)), (0, 0))) * 10 ** (voice_gain_db / 20)
    ducked, _, duck_report = duck_music(music, voice, sample_rate, **duck_options)
    mixed = voice + ducked
    peak = float(np.max(np.abs(mixed)))
    master_gain = min(1.0, 10 ** (peak_ceiling_dbfs / 20) / peak) if peak else 1.0
    mixed = (mixed * master_gain).astype(np.float32)
    return mixed, {
        "sample_rate": sample_rate,
        "channels": 2,
        "duration_seconds": count / sample_rate,
        "music_gain_db": music_gain_db,
        "voice_gain_db": voice_gain_db,
        "peak_ceiling_dbfs": peak_ceiling_dbfs,
        "master_gain": master_gain,
        "voice_shift_samples": 0,
        "ducking": duck_report,
        "output": audio_metrics(mixed),
    }

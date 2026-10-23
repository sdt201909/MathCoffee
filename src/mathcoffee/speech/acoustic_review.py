"""Content-confounded acoustic review aids, never speaker-identity verdicts.

These measurements can order A/B clips for listening. They cannot separate
phonetic content, acting, register, and speaker identity. A lower dispersion is
not automatically better narration. No model downloads or audio mutation occur.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

import numpy as np
from scipy import fft, signal

METHOD = "acoustic_review_v1_24k_10ms_energy_40ms_spectrum"
LIMITATION = (
    "MFCC, spectrum and F0 depend on phonetic content and prosody; F0 may contain "
    "octave errors. These are review proxies, not speaker embeddings, identity "
    "verification, pronunciation checks or human listening. Lower dispersion "
    "does not by itself mean a better or more consistent perceived voice."
)
ANALYSIS_RATE = 24_000


def acoustic_features(wave, sample_rate: int) -> dict:
    """Measure one mono waveform; preserve silence as missing speech measures.

    Inputs must be floating PCM in [-1, 1]. Resampling is analysis only. A 10 ms
    RMS gate selects speech-energy windows; 40 ms Hann windows supply spectral
    summaries. Cepstral C0 is excluded to reduce gain sensitivity. The restricted
    100–420 Hz autocorrelation F0 is a review aid for the current Serena material,
    not a universal pitch estimator or a definition of gender.
    """
    original = np.asarray(wave)
    if original.ndim != 1 or not len(original):
        raise ValueError("expected nonempty mono waveform")
    if not np.issubdtype(original.dtype, np.floating):
        raise ValueError("expected floating PCM, not unscaled integer samples")
    if not np.all(np.isfinite(original)) or np.max(np.abs(original)) > 1:
        raise ValueError("expected finite PCM in [-1, 1]")
    if isinstance(sample_rate, bool) or not isinstance(sample_rate, (int, np.integer)):
        raise ValueError("sample rate must be an integer")
    if not 8_000 <= sample_rate <= 192_000:
        raise ValueError("unsupported analysis sample rate")
    wave = original.astype(np.float64)
    if sample_rate != ANALYSIS_RATE:
        divisor = math.gcd(int(sample_rate), ANALYSIS_RATE)
        wave = signal.resample_poly(wave, ANALYSIS_RATE // divisor, sample_rate // divisor)
    hop, frame_length = 240, 960
    peak = float(np.max(np.abs(wave)))
    energy = np.array([
        np.sqrt(np.mean(wave[i:i + hop] ** 2)) for i in range(0, len(wave), hop)
    ])
    active = energy > max(peak * 0.012, 0.0006)
    result = {
        "schema_version": 1, "method": METHOD, "review_status": "proxy_only",
        "limitation": LIMITATION, "input_sample_rate": int(sample_rate),
        "analysis_sample_rate": ANALYSIS_RATE,
        "duration_seconds": len(original) / sample_rate,
        "energy_hop_seconds": 0.01,
        "active_energy_windows": int(active.sum()), "energy_windows": len(energy),
        "active_fraction": float(active.mean()),
        "active_rms_dbfs": None, "spectral_centroid_median_hz": None,
        "spectral_rolloff90_median_hz": None, "mfcc_median": None,
        "spectral_frames": 0, "f0_median_hz": None, "f0_p10_hz": None,
        "f0_p90_hz": None, "f0_confidence_median": None, "voiced_frames": 0,
    }
    if not active.any():
        result["measurement_status"] = "no_active_energy"
        return result
    result["active_rms_dbfs"] = float(20 * np.log10(np.sqrt(np.mean(energy[active] ** 2))))
    if len(wave) < frame_length:
        result["measurement_status"] = "insufficient_duration_for_spectrum"
        return result
    frames = np.lib.stride_tricks.sliding_window_view(wave, frame_length)[::hop]
    centers = (np.arange(len(frames)) * hop + frame_length // 2) // hop
    frames = frames[active[centers]]
    if not len(frames):
        result["measurement_status"] = "no_active_spectral_frames"
        return result
    window = np.hanning(frame_length)
    frequencies = fft.rfftfreq(2048, 1 / ANALYSIS_RATE)
    power = np.abs(fft.rfft(frames * window, n=2048, axis=1)) ** 2
    total = power.sum(axis=1)
    power = power[total > 1e-15]
    total = total[total > 1e-15]
    if not len(power):
        result["measurement_status"] = "no_active_spectral_power"
        return result
    centroid = (power * frequencies).sum(axis=1) / total
    rolloff_indices = np.argmax(np.cumsum(power, axis=1) >= total[:, None] * 0.9, axis=1)
    # Fixed 26 mel bands and 13 non-energy coefficients, shared across conditions.
    mel_edges = np.linspace(2595 * np.log10(1 + 80 / 700),
                            2595 * np.log10(1 + 8000 / 700), 28)
    edges = 700 * (10 ** (mel_edges / 2595) - 1)
    banks = np.array([
        np.maximum(0, np.minimum((frequencies - left) / (middle - left),
                                (right - frequencies) / (right - middle)))
        for left, middle, right in zip(edges[:-2], edges[1:-1], edges[2:], strict=True)
    ])
    mfcc = fft.dct(np.log(np.maximum(power @ banks.T, 1e-14)),
                   type=2, axis=1, norm="ortho")[:, 1:14]
    result.update(
        measurement_status="measured", spectral_frames=len(power),
        spectral_centroid_median_hz=float(np.median(centroid)),
        spectral_rolloff90_median_hz=float(np.median(frequencies[rolloff_indices])),
        mfcc_median=np.median(mfcc, axis=0).tolist(),
    )
    # Low-pass autocorrelation excludes much unvoiced high-frequency energy.
    low = signal.sosfilt(signal.butter(4, 1000, fs=ANALYSIS_RATE, output="sos"), wave)
    pitch, confidence = [], []
    low_frames = np.lib.stride_tricks.sliding_window_view(low, frame_length)[::hop]
    for frame in low_frames[active[centers]]:
        frame = (frame - frame.mean()) * window
        correlation = signal.fftconvolve(frame, frame[::-1], mode="full")[frame_length - 1:]
        if correlation[0] < 1e-10:
            continue
        first, last = int(ANALYSIS_RATE / 420), int(ANALYSIS_RATE / 100)
        peaks, _ = signal.find_peaks(correlation[first:last])
        peaks += first
        if not len(peaks):
            continue
        index = int(peaks[np.argmax(correlation[peaks])])
        strength = correlation[index] / correlation[0]
        if strength < 0.65:
            continue
        denominator = correlation[index - 1] - 2 * correlation[index] + correlation[index + 1]
        delta = 0.5 * (correlation[index - 1] - correlation[index + 1]) / denominator
        pitch.append(float(ANALYSIS_RATE / (index + delta)))
        confidence.append(float(strength))
    if pitch:
        result.update(
            f0_median_hz=float(np.median(pitch)), f0_p10_hz=float(np.quantile(pitch, 0.1)),
            f0_p90_hz=float(np.quantile(pitch, 0.9)), voiced_frames=len(pitch),
            f0_confidence_median=float(np.median(confidence)),
        )
    return result


def group_dispersion(groups: Mapping[str, Mapping[str, dict]], baseline: str) -> dict:
    """Compare conditions with the same ordered cue IDs, using one fixed scale.

    Caller must ensure IDs refer to identical text and record WAV/text hashes in
    its report. Per-condition MFCC dispersion is centered on that condition's own
    median; a uniform voice change could reduce this value while being unwanted.
    Paired distances to baseline are therefore retained, with no pass threshold.
    Missing speech or mismatched cue sets is an error, never a good low score.
    """
    if baseline not in groups or not groups[baseline]:
        raise ValueError("baseline condition is missing or empty")
    ids = list(groups[baseline])
    if len(ids) < 2:
        raise ValueError("dispersion requires at least two identical-text cues")
    arrays = {}
    for name, cases in groups.items():
        if set(cases) != set(ids):
            raise ValueError("conditions must contain identical cue IDs")
        features = [cases[key] for key in ids]
        if any(f.get("method") != METHOD or f.get("mfcc_median") is None for f in features):
            raise ValueError("conditions need measured features from the same method")
        values = np.asarray([f["mfcc_median"] for f in features], dtype=float)
        if values.shape != (len(ids), 13) or not np.all(np.isfinite(values)):
            raise ValueError("expected 13 finite MFCC coefficients per cue")
        arrays[name] = values
    scale = np.maximum(np.std(arrays[baseline], axis=0), 0.1)
    conditions = {}
    for name, values in arrays.items():
        centered = (values - np.median(values, axis=0)) / scale
        distances = np.sqrt(np.mean(centered ** 2, axis=1))
        paired = np.sqrt(np.mean(((values - arrays[baseline]) / scale) ** 2, axis=1))
        pitches = np.array([groups[name][key].get("f0_median_hz") or np.nan for key in ids])
        valid = pitches[np.isfinite(pitches) & (pitches > 0)]
        conditions[name] = {
            "mfcc_dispersion_rms": float(np.sqrt(np.mean(centered ** 2))),
            "mfcc_distance_to_own_center_median": float(np.median(distances)),
            "mfcc_distance_to_own_center_max": float(np.max(distances)),
            "paired_mfcc_distance_to_baseline": dict(zip(ids, paired.tolist(), strict=True)),
            "f0_available_cues": len(valid),
            "f0_between_cue_std_semitones": (
                float(np.std(12 * np.log2(valid))) if len(valid) >= 2 else None
            ),
        }
    return {
        "schema_version": 1, "method": METHOD, "review_status": "proxy_only",
        "limitation": LIMITATION, "baseline": baseline, "ordered_cue_ids": ids,
        "caller_must_verify_same_text": True,
        "mfcc_scale": scale.tolist(), "scale_rule": "baseline std, each coefficient floor 0.1",
        "conditions": conditions,
    }

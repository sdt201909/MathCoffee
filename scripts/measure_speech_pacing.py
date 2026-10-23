#!/usr/bin/env python3
"""Measure energy-based pacing proxies, with same-text comparisons and no listening claim.

Run with .venv-speech/bin/python (numpy and soundfile already installed). The input
is a synthesize_voice manifest or chapter/cue voice index; audio is read, never changed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import unicodedata
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
METHOD = "speech_pacing_energy_v1"
LIMITATION = (
    "10 ms RMS energy activity is not speech VAD, phoneme/syllable alignment, "
    "pronunciation validation or human listening. Breaths/noise can be active; quiet "
    "consonants can be missed. Articulation here is an energy-derived duration proxy. "
    "Characters and English words remain separate orthographic counts, never true syllables. "
    "Review thresholds identify candidates, not failed voice identity or automatic approval."
)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def runs(mask):
    """Half-open true runs, including one-window and terminal runs."""
    edges = np.diff(np.r_[False, mask, False].astype(np.int8))
    return list(zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1), strict=True))


def measure_wave(wave, sample_rate, *, merge_gap_seconds=0.08):
    """Sample-rate-independent 10 ms RMS gate and short internal-gap closing."""
    wave = np.asarray(wave)
    if wave.ndim != 1 or not len(wave) or not np.issubdtype(wave.dtype, np.floating):
        raise ValueError("expected nonempty mono floating PCM")
    if not np.all(np.isfinite(wave)) or np.max(np.abs(wave)) > 1:
        raise ValueError("expected finite PCM in [-1, 1]")
    if (isinstance(sample_rate, bool) or not isinstance(sample_rate, (int, np.integer))
            or not 8000 <= sample_rate <= 192000):
        raise ValueError("sample rate must be an integer from 8000 to 192000")
    if not math.isfinite(merge_gap_seconds) or not 0 <= merge_gap_seconds <= 0.3:
        raise ValueError("merge gap must be finite and between 0 and 0.3 seconds")
    # Rational boundaries avoid accumulated rounding at rates not divisible by 100.
    count = (len(wave) * 100 + sample_rate - 1) // sample_rate
    starts = np.arange(count, dtype=np.int64) * sample_rate // 100
    ends = np.minimum((np.arange(count, dtype=np.int64) + 1) * sample_rate // 100, len(wave))
    energy = np.asarray([np.sqrt(np.mean(wave[a:b].astype(np.float64) ** 2))
                         for a, b in zip(starts, ends, strict=True)])
    peak = float(np.max(np.abs(wave)))
    threshold = max(0.0006, peak * 0.012)
    active = energy > threshold
    if not np.any(active):
        raise ValueError("no detectable energy activity; silence cannot pass pacing review")
    intervals = [(int(starts[a]), int(ends[b - 1])) for a, b in runs(active)]
    merged = []
    for start, end in intervals:
        if merged and start - merged[-1][1] <= round(merge_gap_seconds * sample_rate):
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    pauses = [(left[1], right[0]) for left, right in zip(merged[:-1], merged[1:], strict=True)]
    energy_samples = sum(end - start for start, end in intervals)
    articulation_samples = sum(end - start for start, end in merged)
    envelope_samples = intervals[-1][1] - intervals[0][0]
    pause_samples = envelope_samples - articulation_samples
    return {
        "method": METHOD, "sample_rate": int(sample_rate), "samples": len(wave),
        "duration_seconds": len(wave) / sample_rate,
        "window_seconds": 0.01, "merge_gap_seconds": merge_gap_seconds,
        "rms_threshold": threshold, "threshold_rule": "max(0.0006, peak_abs_PCM * 0.012)",
        "peak_abs_pcm": peak, "energy_active_seconds": energy_samples / sample_rate,
        "articulation_proxy_seconds": articulation_samples / sample_rate,
        "active_envelope_seconds": envelope_samples / sample_rate,
        "leading_silence_seconds": intervals[0][0] / sample_rate,
        "trailing_silence_seconds": (len(wave) - intervals[-1][1]) / sample_rate,
        "internal_pause_seconds": pause_samples / sample_rate,
        "internal_pause_ratio": pause_samples / envelope_samples,
        "energy_inactive_ratio": 1 - energy_samples / len(wave),
        "internal_pause_count": len(pauses),
        "longest_internal_pause_seconds": max((b - a for a, b in pauses), default=0) / sample_rate,
        "energy_intervals_samples": intervals,
        "articulation_intervals_samples": merged, "internal_pauses_samples": pauses,
    }


def is_han(char):
    cp = ord(char)
    return (0x3400 <= cp <= 0x4DBF or 0x4E00 <= cp <= 0x9FFF
            or 0xF900 <= cp <= 0xFAFF or 0x20000 <= cp <= 0x323AF)


def text_counts(spoken_text):
    """Count the actual normalized model input, not original subtitle numbers."""
    if not isinstance(spoken_text, str) or not spoken_text.strip():
        raise ValueError("nonempty spoken_text is required; no subtitle fallback")
    han = sum(is_han(char) for char in spoken_text)
    words = re.findall(r"[A-Za-z]+(?:['’\-][A-Za-z]+)*", spoken_text)
    digits = re.findall(r"\d+(?:[.,]\d+)*", spoken_text)
    punct = sum(unicodedata.category(char).startswith("P") for char in spoken_text)
    others = [char for char in spoken_text if not is_han(char)
              and unicodedata.category(char).startswith("L") and not char.isascii()]
    kind = ("mixed_or_unresolved" if digits or others or (han and words)
            else "zh_only" if han else "en_only" if words else "unresolved")
    # This denominator is only a textual punctuation density, never syllable load.
    text_units = han + len(words)
    length = han if kind == "zh_only" else len(words) if kind == "en_only" else None
    band = ("mixed_or_unresolved" if length is None else
            "short" if length < (20 if kind == "zh_only" else 10) else
            "medium" if length < (40 if kind == "zh_only" else 20) else "long")
    density = punct / max(text_units, 1)
    return {
        "han_characters": han, "english_words": len(words), "english_word_tokens": words,
        "unexpanded_numeric_tokens": digits, "other_letters": sorted(set(others)),
        "punctuation_marks": punct, "punctuation_per_orthographic_unit": density,
        "language_class": kind, "length_band": band,
        "punctuation_density_band": "sparse" if density < 0.1 else "dense",
        "syllable_estimation": "not_performed",
        "warning": "English counts include letter names; word tokens are not phonetic syllables.",
    }


def rate_fields(counts, acoustic):
    durations = {"envelope": acoustic["active_envelope_seconds"],
                 "articulation_proxy": acoustic["articulation_proxy_seconds"],
                 "energy_active": acoustic["energy_active_seconds"],
                 "file": acoustic["duration_seconds"]}
    units = (("han_chars", "han_characters"), ("english_words", "english_words"))
    result = {f"{unit}_per_{kind}_second": counts[field] / duration
              for unit, field in units
              for kind, duration in durations.items()}
    # Mixed-language partial rates are displayed separately and never used as one rate.
    result["within_language_review_unit"] = (
        "han_chars" if counts["language_class"] == "zh_only" else
        "english_words" if counts["language_class"] == "en_only" else None)
    return result


def load_input(path):
    path = Path(path).resolve(strict=True)
    data = json.loads(path.read_text())
    if "chapters" in data:
        items = [(chapter["id"], cue) for chapter in data["chapters"] for cue in chapter["cues"]]
        kind = "chapter_voice_index"
    elif "cases" in data:
        items = [(None, cue) for cue in data["cases"]]
        kind = "synthesize_manifest"
    else:
        raise ValueError("input must contain chapters/cues or synthesize cases")
    normalized, seen = [], set()
    for chapter, cue in items:
        cid = cue["id"]
        if cid in seen:
            raise ValueError(f"duplicate cue ID: {cid}")
        seen.add(cid)
        audio = cue.get("audio", cue)
        wav = Path(audio["path"])
        if not wav.is_absolute():
            wav = ROOT / wav if (ROOT / wav).is_file() else path.parent / wav
        expected_hash = audio.get("sha256")
        if not expected_hash or not re.fullmatch(r"[a-f0-9]{64}", expected_hash):
            raise ValueError(f"missing audio SHA-256: {cid}")
        spoken = cue.get("spoken_text")
        text_counts(spoken)
        normalized.append({"id": cid, "chapter": chapter, "path": str(wav.resolve(strict=True)),
                           "sha256": expected_hash, "spoken_text": spoken,
                           "text": cue.get("subtitle_text", cue.get("text")),
                           "declared_signal": cue.get("signal", cue)})
    if not normalized:
        raise ValueError("no cues")
    return {"path": str(path), "sha256": sha(path), "kind": kind}, normalized


def measure_input(path, merge_gap_seconds=0.08, cue_ids=None):
    import soundfile as sf

    source, cues = load_input(path)
    if cue_ids is not None:
        selected = set(cue_ids)
        if not selected or len(selected) != len(cue_ids):
            raise ValueError("cue selection must be nonempty and unique")
        missing = selected - {cue["id"] for cue in cues}
        if missing:
            raise ValueError(f"requested cue IDs missing: {sorted(missing)}")
        cues = [cue for cue in cues if cue["id"] in selected]
        source["selected_cue_ids"] = [cue["id"] for cue in cues]
        source["kind"] += "_subset"
    measured = []
    for cue in cues:
        actual_hash = sha(cue["path"])
        if actual_hash != cue["sha256"]:
            raise ValueError(f"audio SHA mismatch: {cue['id']}")
        pcm, rate = sf.read(cue["path"], dtype="float64", always_2d=False)
        if sha(cue["path"]) != actual_hash:
            raise ValueError(f"audio changed while reading: {cue['id']}")
        for field, actual in (("samples", len(pcm)), ("sample_rate", rate), ("channels", 1)):
            if field in cue["declared_signal"] and cue["declared_signal"][field] != actual:
                raise ValueError(f"declared {field} mismatch: {cue['id']}")
        acoustic = measure_wave(pcm, rate, merge_gap_seconds=merge_gap_seconds)
        counts = text_counts(cue["spoken_text"])
        measured.append({key: value for key, value in cue.items() if key != "declared_signal"}
                        | {"bytes": Path(cue["path"]).stat().st_size,
                           "pcm_sha256_f64le": hashlib.sha256(
                               pcm.astype("<f8").tobytes()).hexdigest(),
                           "acoustic": acoustic, "text_counts": counts,
                           "rates": rate_fields(counts, acoustic)})
    return {"source": source, "cues": measured, "summary": summarize(measured),
            "adjacent_rate_review": adjacent_review(measured, source["kind"])}


def distribution(values):
    if not values:
        return {"count": 0}
    array = np.asarray(values, dtype=float)
    return {"count": len(values), "mean": float(np.mean(array)),
            "median": float(np.median(array)), "p10": float(np.quantile(array, 0.1)),
            "p90": float(np.quantile(array, 0.9)), "min": float(np.min(array)),
            "max": float(np.max(array)), "cv": float(np.std(array) / np.mean(array))
            if np.mean(array) else None}


def stratum(cue):
    counts = cue["text_counts"]
    return "/".join(counts[key] for key in
                    ("language_class", "length_band", "punctuation_density_band"))


def review_rate(cue):
    unit = cue["rates"]["within_language_review_unit"]
    return cue["rates"][f"{unit}_per_articulation_proxy_second"] if unit else None


def summarize(cues):
    strata = {}
    for cue in cues:
        if review_rate(cue) is not None:
            strata.setdefault(stratum(cue), []).append(cue)
    return {
        "cue_count": len(cues),
        "duration_seconds": sum(c["acoustic"]["duration_seconds"] for c in cues),
        "articulation_proxy_seconds": sum(
            c["acoustic"]["articulation_proxy_seconds"] for c in cues),
        "active_envelope_seconds": sum(c["acoustic"]["active_envelope_seconds"] for c in cues),
        "internal_pause_seconds": sum(c["acoustic"]["internal_pause_seconds"] for c in cues),
        "internal_pause_ratio": distribution([c["acoustic"]["internal_pause_ratio"] for c in cues]),
        "strata": {key: {"articulation_rate": distribution([review_rate(c) for c in group]),
                          "cue_ids": [c["id"] for c in group]}
                   for key, group in strata.items()},
        "mixed_or_unresolved_ids": [c["id"] for c in cues if review_rate(c) is None],
    }


def adjacent_review(cues, source_kind):
    medians = {key: value["articulation_rate"]["median"]
               for key, value in summarize(cues)["strata"].items()}
    result = []
    for left, right in zip(cues[:-1], cues[1:], strict=True):
        # An A/B selection can skip production sentences: disclose sequence adjacency.
        item = {"from": left["id"], "to": right["id"],
                "adjacency": "production_index" if source_kind == "chapter_voice_index"
                else "manifest_order_not_necessarily_production_neighbors",
                "cross_chapter": left["chapter"] != right["chapter"],
                "strata": [stratum(left), stratum(right)], "review_candidate": False}
        a, b = review_rate(left), review_rate(right)
        same_language = (left["text_counts"]["language_class"]
                         == right["text_counts"]["language_class"])
        if a and b and same_language:
            raw = b / a
            normalized = (b / medians[stratum(right)]) / (a / medians[stratum(left)])
            enough = all(c["text_counts"]["han_characters"] >= 12
                         if c["text_counts"]["language_class"] == "zh_only"
                         else c["text_counts"]["english_words"] >= 5 for c in (left, right))
            item.update(next_over_previous_rate=raw,
                        length_punctuation_stratum_normalized_ratio=normalized,
                        enough_text_for_review_flag=enough,
                        review_candidate=enough and (max(raw, 1 / raw) >= 1.35
                                                      or max(normalized, 1 / normalized) >= 1.35))
        else:
            item["reason"] = "different language classes or unresolved/mixed text; no unified rate"
        result.append(item)
    return {"threshold_symmetric_rate_ratio": 1.35,
            "normalization": "divide each rate by its language/length/punctuation stratum median; "
            "small strata are unstable; not a prosody correction or identity verdict",
            "candidates": [x for x in result if x["review_candidate"]], "pairs": result}


def compare_inputs(current, baseline):
    reference = {cue["id"]: cue for cue in baseline["cues"]}
    pairs, unmatched = [], []
    for cue in current["cues"]:
        old = reference.get(cue["id"])
        if old is None:
            unmatched.append(cue["id"])
            continue
        if cue["spoken_text"] != old["spoken_text"]:
            raise ValueError(f"same ID has different spoken_text: {cue['id']}")
        item = {"id": cue["id"], "spoken_text_sha256": hashlib.sha256(
            cue["spoken_text"].encode()).hexdigest(), "stratum": stratum(cue)}
        for key in ("duration_seconds", "active_envelope_seconds", "articulation_proxy_seconds",
                    "energy_active_seconds"):
            item[f"{key}_speed_ratio"] = old["acoustic"][key] / cue["acoustic"][key]
        item["internal_pause_ratio_delta"] = (cue["acoustic"]["internal_pause_ratio"]
                                               - old["acoustic"]["internal_pause_ratio"])
        pairs.append(item)
    totals = {}
    current_by_id = {c["id"]: c for c in current["cues"]}
    for key in ("duration_seconds", "active_envelope_seconds", "articulation_proxy_seconds"):
        old_sum = sum(reference[p["id"]]["acoustic"][key] for p in pairs)
        new_sum = sum(current_by_id[p["id"]]["acoustic"][key] for p in pairs)
        totals[key] = {"baseline": old_sum, "current": new_sum,
                       "pooled_same_text_speed_ratio": old_sum / new_sum if new_sum else None}
    return {"same_spoken_text_pair_count": len(pairs), "unmatched_ids_excluded": unmatched,
            "ratio_interpretation": "baseline duration / current duration; >1 means faster "
            "for exactly the same normalized text; no syllable estimate or voice approval",
            "pooled_durations": totals, "paired_distributions": {
                key: distribution([p[key] for p in pairs]) for key in
                ("duration_seconds_speed_ratio", "active_envelope_seconds_speed_ratio",
                 "articulation_proxy_seconds_speed_ratio", "energy_active_seconds_speed_ratio")},
            "pairs": pairs}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--cue-id", action="append", help="repeat to select matched input IDs")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--merge-gap-ms", type=float, default=80)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to replace report: {args.output}")
    current = measure_input(args.input, args.merge_gap_ms / 1000, args.cue_id)
    report = {"schema_version": 1, "method": METHOD, "review_status": "proxy_only",
              "limitation": LIMITATION, "script_sha256": sha(__file__), "current": current}
    if args.baseline:
        baseline = measure_input(args.baseline, args.merge_gap_ms / 1000, args.cue_id)
        report.update(baseline=baseline, comparison=compare_inputs(current, baseline))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"output": str(args.output.resolve()), "cues": len(current["cues"]),
                      "adjacent_review_candidates": len(
                          current["adjacent_rate_review"]["candidates"]),
                      "pooled_comparison": report.get("comparison", {}).get("pooled_durations")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()

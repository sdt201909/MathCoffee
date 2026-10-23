#!/usr/bin/env python3
"""Generate offline speech samples and an auditable spoken/subtitle manifest.

Examples:
  .venv/bin/python scripts/synthesize_voice.py --provider qwen_mlx --all --dry-run \
    --output-dir media/speech_smoke/plan
  .venv-kokoro/bin/python scripts/synthesize_voice.py --provider kokoro \
    --case polyphone_row --output-dir media/speech_smoke/kokoro-row

Use separate output directories for language/profile A/B comparisons. Existing
outputs are never overwritten. A generated WAV is not a pronunciation approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import re
import sys
import time
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mathcoffee.speech.planning import make_plan  # noqa: E402
from mathcoffee.speech.providers import CAPABILITIES, PROVIDERS, sha256  # noqa: E402


def save_json(path, value):
    temporary = path.with_suffix(".tmp.json")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def timestamp(seconds):
    value = round(seconds * 1000)
    hours, value = divmod(value, 3_600_000)
    minutes, value = divmod(value, 60_000)
    seconds, milliseconds = divmod(value, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


def signal_report(wave, rate, max_seconds):
    import numpy as np

    if wave.ndim != 1 or not len(wave) or not np.all(np.isfinite(wave)):
        raise ValueError("empty, non-mono or nonfinite generated audio")
    peak = float(np.max(np.abs(wave)))
    if peak >= 1 or peak < 1e-5:
        raise ValueError(f"clipped or silent generated audio: peak={peak}")
    duration = len(wave) / rate
    if duration > max_seconds:
        raise ValueError(f"generated cue exceeded {max_seconds}s; possible run-on speech")
    rms = float(np.sqrt(np.mean(wave.astype(np.float64) ** 2)))
    hop = max(1, round(rate * 0.01))
    energies = np.array([
        np.sqrt(np.mean(wave[i:i + hop].astype(np.float64) ** 2))
        for i in range(0, len(wave), hop)
    ])
    active = np.flatnonzero(energies > max(peak * 0.012, 0.0006))
    if not len(active):
        raise ValueError("generated audio contains no detectable speech energy")
    return {
        "sample_rate": rate, "channels": 1, "samples": len(wave), "duration_seconds": duration,
        "peak": peak, "peak_dbfs": 20 * math.log10(peak), "rms": rms,
        "active_start_sample": max(0, int(active[0]) * hop - round(rate * 0.04)),
        "active_end_sample": min(len(wave), (int(active[-1]) + 1) * hop + round(rate * 0.06)),
        "signal_check": "passed", "semantic_accuracy": "pending_human_listening",
    }


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=tuple(PROVIDERS), required=True)
    parser.add_argument("--profile", default="science_female")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--case", action="append", help="repeat for several stable case IDs")
    selection.add_argument("--all", action="store_true")
    selection.add_argument("--text", help="custom single cue; use case JSON for bilingual spans")
    parser.add_argument("--cases", type=Path, default=ROOT / "assets/speech/smoke_cases.json")
    parser.add_argument("--lexicon", type=Path, default=ROOT / "assets/speech/lexicon.json")
    parser.add_argument("--profiles", type=Path, default=ROOT / "assets/speech/voice_profiles.json")
    parser.add_argument("--model-path", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--language", choices=("auto", "Chinese", "English"))
    parser.add_argument("--instruct", help="Qwen 1.7B style instruction; never sent to Kokoro")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-tokens", type=int)
    parser.add_argument("--gap", type=float, default=0.35)
    parser.add_argument("--max-seconds", type=float, default=60.0)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main():
    args = arguments()
    if not 0 <= args.seed < 2**32 or not math.isfinite(args.gap) or not 0 <= args.gap <= 5:
        raise ValueError("invalid seed or cue gap")
    if not math.isfinite(args.max_seconds) or not 0 < args.max_seconds <= 300:
        raise ValueError("max-seconds must be finite and between 0 and 300")
    if args.provider == "kokoro" and any(
        v is not None for v in (args.instruct, args.language, args.max_tokens)
    ):
        raise ValueError("Kokoro cannot honor Qwen style/language/token-generation options")
    profiles = json.loads(args.profiles.read_text())["profiles"]
    profile = deepcopy(profiles[args.profile][args.provider])
    if args.instruct is not None:
        profile["instruct"] = args.instruct
    if args.language is not None:
        profile["language"] = args.language
    if args.max_tokens is not None:
        if not 32 <= args.max_tokens <= 4096:
            raise ValueError("max-tokens must be between 32 and 4096")
        profile["max_tokens"] = args.max_tokens
    lexicon = json.loads(args.lexicon.read_text())
    cases = json.loads(args.cases.read_text())["cases"]
    if args.text:
        cases = [{"id": "custom", "text": args.text}]
    elif args.case:
        catalog = {case["id"]: case for case in cases}
        if len(set(args.case)) != len(args.case):
            raise ValueError("duplicate requested case IDs")
        cases = [catalog[key] for key in args.case]
    if not cases or len({case["id"] for case in cases}) != len(cases):
        raise ValueError("empty or duplicate case IDs")
    if any(not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", case["id"]) for case in cases):
        raise ValueError("case IDs must be safe lowercase filenames")
    plans = [make_plan(case, args.provider, lexicon) for case in cases]
    output = args.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"refusing to overwrite existing output directory: {output}")
    output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1, "status": "planned", "provider": args.provider,
        "capabilities": CAPABILITIES[args.provider], "profile": args.profile,
        "parameters": profile, "seed": args.seed, "gap_seconds": args.gap,
        "platform": {"system": platform.system(), "machine": platform.machine(),
                     "python": platform.python_version()},
        "inputs": {str(p.resolve()): sha256(p) for p in (args.cases, args.lexicon, args.profiles)},
        "adapter_sources": {str(p.relative_to(ROOT)): sha256(p) for p in [
            Path(__file__), *sorted((ROOT / "src/mathcoffee/speech").glob("*.py"))
        ]},
        "review_status": "pending_human_listening",
        "review_warning": "Signal checks and phoneme rules do not prove audible correctness, "
                          "a more natural voice, or emotional quality.",
        "cases": plans,
    }
    manifest_path = output / "manifest.json"
    save_json(manifest_path, manifest)
    if args.dry_run:
        print(json.dumps({"status": "planned", "manifest": str(manifest_path)}, ensure_ascii=False))
        return
    started = time.perf_counter()
    try:
        import numpy as np
        import soundfile as sf

        provider = PROVIDERS[args.provider](profile, plans, lexicon, args.model_path)
        manifest.update(status="generating", runtime=provider.metadata)
        # There is intentionally no waveform cache/reuse in this entry point.
        # Identity still covers source and model content for future cache consumers.
        identity = {
            "provider": args.provider, "parameters": profile, "seed": args.seed,
            "gap_seconds": args.gap, "plans": plans,
            "inputs": manifest["inputs"], "adapter_sources": manifest["adapter_sources"],
            "runtime": {k: v for k, v in provider.metadata.items() if k != "load_seconds"},
        }
        manifest["synthesis_identity_sha256"] = hashlib.sha256(
            json.dumps(identity, ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest()
        manifest["cache_policy"] = "No waveform reuse; nonempty output directories are refused."
        save_json(manifest_path, manifest)
        segments, cursor, subtitles = [], 0, []
        rate = provider.sample_rate
        for index, plan in enumerate(plans):
            wave, details = provider.synthesize(plan, args.seed)
            checks = signal_report(wave, rate, args.max_seconds)
            audio_path = output / f"{plan['id']}.wav"
            sf.write(audio_path, wave, rate, subtype="PCM_24")
            # Read actual written PCM, checking frame count and decoder accessibility.
            decoded, written_rate = sf.read(audio_path, dtype="float32")
            if written_rate != rate or len(decoded) != len(wave):
                raise ValueError("written waveform changed rate or length")
            written_checks = signal_report(decoded, rate, args.max_seconds)
            plan.update(
                synthesis=details, signal=written_checks,
                audio={"path": str(audio_path), "sha256": sha256(audio_path),
                       "bytes": audio_path.stat().st_size},
                timeline={"start_sample": cursor, "end_sample": cursor + len(wave)},
            )
            duration = checks["duration_seconds"]
            plan["synthesis"]["rtf_compute_over_audio"] = details["generation_seconds"] / duration
            start = (cursor + checks["active_start_sample"]) / rate
            end = (cursor + checks["active_end_sample"]) / rate
            subtitles.append(
                f"{index + 1}\n{timestamp(start)} --> {timestamp(end)}\n{plan['subtitle_text']}\n"
            )
            plan["subtitle"] = {"start_seconds": start, "end_seconds": end,
                                "text": plan["subtitle_text"]}
            segments.append(decoded)
            cursor += len(decoded)
            if index < len(plans) - 1:
                gap = np.zeros(round(args.gap * rate), dtype=np.float32)
                segments.append(gap)
                cursor += len(gap)
            save_json(manifest_path, manifest)
            print(f"{plan['id']}: {duration:.3f}s; listening pending", flush=True)
        merged = np.concatenate(segments)
        combined_path = output / "narration.wav"
        sf.write(combined_path, merged, rate, subtype="PCM_24")
        decoded, decoded_rate = sf.read(combined_path, dtype="float32")
        if decoded_rate != rate or len(decoded) != cursor or not np.allclose(
            decoded, merged, atol=2**-22, rtol=0
        ):
            raise ValueError("combined waveform decode or concatenation validation failed")
        subtitle_path = output / "narration.srt"
        subtitle_path.write_text("\n".join(subtitles), encoding="utf-8")
        manifest.update(
            status="generated_signal_checked", elapsed_seconds=time.perf_counter() - started,
            output={"audio": str(combined_path), "srt": str(subtitle_path),
                    "audio_sha256": sha256(combined_path), "srt_sha256": sha256(subtitle_path),
                    "sample_rate": rate, "channels": 1, "samples": cursor,
                    "duration_seconds": cursor / rate, "bytes": combined_path.stat().st_size},
        )
        save_json(manifest_path, manifest)
        print(json.dumps({"status": manifest["status"], "manifest": str(manifest_path),
                          **manifest["output"]}, ensure_ascii=False))
    except Exception as error:
        manifest.update(
            status="failed", error={"type": type(error).__name__, "message": str(error)}
        )
        save_json(manifest_path, manifest)
        raise


if __name__ == "__main__":
    main()

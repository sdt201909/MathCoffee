#!/usr/bin/env python3
"""Generate a frozen, episode-independent offline Serena voice revision.

The original voice index and all delivered files remain unchanged. The chosen
profile must name explicit text conditioning; an optional A/B review is verified.
Signal/embedding measurements never set a human listening approval.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from synthesize_voice import signal_report  # noqa: E402

from mathcoffee.speech.providers import local_model_manifest, sha256  # noqa: E402
from mathcoffee.speech.qwen_context import UPSTREAM_SHA256  # noqa: E402


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.json")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def protect(path, value):
    if path.exists():
        if read(path) != value:
            raise ValueError(f"inputs changed; use a new revision: {path}")
    else:
        save(path, value)


def selected_chapters(source, source_sha, cut=None):
    """Map authoring structures to one ordered voice index without changing text."""
    if ("chapters" in source) == ("scenes" in source):
        raise ValueError("authoring must contain exactly one of chapters or scenes")
    raw = source.get("chapters", source.get("scenes"))
    chapters, all_ids, chapter_ids = [], [], set()
    for chapter in raw:
        chapter_id = chapter["id"]
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", chapter_id) or chapter_id in chapter_ids:
            raise ValueError("chapter IDs must be safe, lowercase and unique")
        chapter_ids.add(chapter_id)
        cues = chapter.get("cues", chapter.get("sentences"))
        if not isinstance(cues, list) or not cues:
            raise ValueError("chapter must have nonempty cues or sentences")
        for cue in cues:
            if not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", cue["id"]):
                raise ValueError("cue IDs must be safe lowercase names; no silent ID rewrite")
            if not isinstance(cue["text"], str) or not cue["text"].strip():
                raise ValueError("cue text must be nonempty")
            all_ids.append(cue["id"])
        chapters.append({**chapter, "cues": cues})
    if not chapters or len(all_ids) != len(set(all_ids)):
        raise ValueError("empty authoring or duplicate cue IDs")
    omitted = set()
    if cut is not None:
        if cut["source_authoring_sha256"] != source_sha:
            raise ValueError("cut source mismatch")
        for cue in cut["excluded_cues"]:
            if cue["id"] not in all_ids or cue["id"] in omitted:
                raise ValueError("cut IDs must be unique known cues")
            if not isinstance(cue.get("reason"), str) or not cue["reason"].strip():
                raise ValueError("each excluded cue needs a reason")
            omitted.add(cue["id"])
    result = [dict(ch, cues=[c for c in ch["cues"] if c["id"] not in omitted])
              for ch in chapters]
    if any(not chapter["cues"] for chapter in result):
        raise ValueError("cut cannot remove a whole chapter")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", required=True)
    parser.add_argument("--authoring", type=Path, required=True)
    parser.add_argument("--cut", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--expected-count", type=int)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--profiles", type=Path, default=ROOT / "src/mathcoffee/data/speech/voice_profiles.json")
    parser.add_argument("--profile", default="science_female")
    parser.add_argument("--review", type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--generate", action="store_true")
    args = parser.parse_args()
    if any(not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", value)
           for value in (args.revision, args.episode)):
        raise ValueError("unsafe episode or revision")
    if not 0 <= args.seed < 2**32:
        raise ValueError("seed outside uint32")
    authoring_path = args.authoring.resolve(strict=True)
    cut_path = args.cut.resolve(strict=True) if args.cut else None
    lexicon = ROOT / "src/mathcoffee/data/speech/lexicon.json"
    cli = ROOT / "scripts/synthesize_voice.py"
    model_path = ROOT / "media/models/Qwen3-TTS-12Hz-1.7B-CustomVoice"
    profiles = args.profiles.resolve(strict=True)
    review = args.review.resolve(strict=True) if args.review else None
    for path in (authoring_path, cut_path, profiles, review):
        if path is not None and not path.is_relative_to(ROOT):
            raise ValueError("frozen inputs must stay in this project")
    parameters = read(profiles)["profiles"][args.profile]["qwen_mlx"]
    if parameters["speaker"] != "Serena" or parameters.get("text_conditioning") != "full_text":
        raise ValueError("repair requires the reviewed Serena full-text profile")
    if parameters.get("stream") is not False:
        raise ValueError("repair requires one complete waveform per cue")
    if review is not None:
        selection = read(review)
        if selection.get("selected_profile") != args.profile:
            raise ValueError("A/B review does not select this profile")
        if selection.get("profiles_sha256") != sha256(profiles):
            raise ValueError("A/B selected profile file changed")
    source = read(authoring_path)
    source_sha = sha256(authoring_path)
    chapters = selected_chapters(source, source_sha, read(cut_path) if cut_path else None)
    expected_ids = [c["id"] for ch in chapters for c in ch["cues"]]
    if args.expected_count is not None and len(expected_ids) != args.expected_count:
        raise ValueError("selected cue count differs from --expected-count")
    directory = (
        args.output_dir or ROOT / "media/voiceover" / args.episode / args.revision
    ).resolve()
    if not directory.is_relative_to(ROOT):
        raise ValueError("voice output must stay in this project")
    source_paths = [Path(__file__), cli, authoring_path, lexicon, profiles,
                    *sorted((ROOT / "src/mathcoffee/speech").glob("*.py"))]
    source_paths.extend(p for p in (cut_path, review) if p is not None)
    sources = {str(p.relative_to(ROOT)): sha256(p) for p in source_paths}
    model_identity = local_model_manifest(model_path)["content_sha256"]
    versions = {name: importlib.metadata.version(name)
                for name in ("mlx-audio", "mlx", "numpy", "soundfile")}
    upstream = Path(importlib.metadata.distribution("mlx-audio").locate_file(
        "mlx_audio/tts/models/qwen3_tts/qwen3_tts.py"))
    if sha256(upstream) != UPSTREAM_SHA256:
        raise ValueError("installed Qwen implementation changed; cached voices cannot be reused")
    request = {"schema_version": 1, "revision": args.revision,
               "parameters": parameters, "seed": args.seed, "sources": sources,
               "runtime_versions": versions, "model_content_sha256": model_identity,
               "upstream_source_sha256": sha256(upstream),
               "review_status": ("proxy_only_pending_human_listening" if review
                                 else "not_reviewed_pending_human_listening"),
               "authoring_path": str(authoring_path),
               "cut_path": str(cut_path) if cut_path else None,
               "selected_ids": expected_ids}
    protect(directory / "request.json", request)
    results = []
    for chapter in chapters:
        part = directory / chapter["id"]
        cases = part / "cases.json"
        protect(cases, {"schema_version": 1, "cases": [
            {"id": c["id"], "text": c["text"]} for c in chapter["cues"]]})
        generated = part / "generated"
        if not args.generate:
            continue
        if not (generated / "manifest.json").exists():
            environment = os.environ.copy()
            environment.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
                               HF_HUB_DISABLE_TELEMETRY="1", HF_HUB_DISABLE_IMPLICIT_TOKEN="1")
            subprocess.run([
                sys.executable, str(cli), "--provider", "qwen_mlx",
                "--profile", args.profile, "--profiles", str(profiles),
                "--cases", str(cases), "--all", "--model-path", str(model_path),
                "--seed", str(args.seed), "--gap", "0", "--max-seconds", "60",
                "--output-dir", str(generated),
            ], cwd=ROOT, env=environment, check=True)
        manifest = read(generated / "manifest.json")
        if manifest["status"] != "generated_signal_checked":
            raise ValueError("incomplete synthesis; inspect failure and use a new revision")
        expected_inputs = {str(p.resolve()): sha256(p) for p in (cases, lexicon, profiles)}
        adapter = {str(p.relative_to(ROOT)): sha256(p) for p in [
            cli, *sorted((ROOT / "src/mathcoffee/speech").glob("*.py"))]}
        if (manifest["provider"] != "qwen_mlx" or manifest["parameters"] != parameters
                or manifest["seed"] != args.seed or manifest["inputs"] != expected_inputs
                or manifest["adapter_sources"] != adapter):
            raise ValueError("generated or reused voice request differs")
        runtime = manifest["runtime"]
        if (runtime["versions"] != versions
                or runtime["model"]["content_sha256"] != model_identity
                or runtime["text_conditioning"]["effective_text_context"] != "full_text"
                or runtime["text_conditioning"]["upstream_source_sha256"] != UPSTREAM_SHA256):
            raise ValueError("generated or reused voice runtime/conditioning differs")
        import numpy as np
        import soundfile as sf

        verified = []
        if [c["id"] for c in manifest["cases"]] != [c["id"] for c in chapter["cues"]]:
            raise ValueError("cue order changed")
        for authored, cue in zip(chapter["cues"], manifest["cases"], strict=True):
            synthesis = cue["synthesis"]
            if (synthesis["seed"] != args.seed
                    or synthesis["speaker"] != parameters["speaker"]
                    or synthesis["language"] != parameters["language"]
                    or synthesis["instruct"] != parameters["instruct"]
                    or synthesis["effective_generation_parameters"]
                    != runtime["effective_generation_parameters"]
                    or synthesis["text_conditioning"] != runtime["text_conditioning"]):
                raise ValueError(f"per-cue synthesis identity differs: {cue['id']}")
            path = Path(cue["audio"]["path"]).resolve(strict=True)
            if path.parent != generated.resolve() or sha256(path) != cue["audio"]["sha256"]:
                raise ValueError(f"changed or unsafe voice asset {cue['id']}")
            wave, rate = sf.read(path, dtype="float32")
            signal = signal_report(wave, rate, 60)
            if rate != 24000 or not np.isfinite(wave).all():
                raise ValueError("unexpected speech format")
            if signal != cue["signal"] or cue["subtitle_text"] != authored["text"]:
                raise ValueError("actual speech signal or subtitle differs from receipt")
            verified.append({"id": cue["id"], "text": authored["text"],
                             "spoken_text": cue["spoken_text"], "path": str(path),
                             "sha256": cue["audio"]["sha256"], "bytes": path.stat().st_size,
                             **signal, "synthesis": cue["synthesis"],
                             "listening_status": "pending_user_mac_review"})
        results.append({"id": chapter["id"], "chapter_id": chapter["id"],
                        "cues": verified, "runtime": runtime,
                        "manifest": str(generated / "manifest.json"),
                        "manifest_sha256": sha256(generated / "manifest.json")})
        print(f"{chapter['id']}: {len(verified)} decoded cues checked", flush=True)
    if args.generate:
        protect(directory / "index.json", {
            "schema_version": 1, "episode": args.episode, "revision": args.revision,
            "source_sha256": source_sha, "request_sha256": sha256(directory / "request.json"),
            "chapters": results, "cues": [cue for chapter in results for cue in chapter["cues"]],
            "authoring_path": str(authoring_path),
            "listening_status": "pending_user_mac_review",
            "consistency_status": "proxy_review_required_not_human_verified",
        })
        print(directory / "index.json")


if __name__ == "__main__":
    main()

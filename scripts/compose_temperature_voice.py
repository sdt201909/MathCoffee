#!/usr/bin/env python3
"""Compose explicitly selected temperature-only Serena retakes immutably.

Only temperature 0.7 -> 0.5 is allowed. Speaker-embedding selection is a review
proxy; this script never grants human listening or voice-identity acceptance.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from synthesize_voice import signal_report  # noqa: E402

from mathcoffee.speech.providers import sha256  # noqa: E402


def read(path):
    return json.loads(Path(path).read_text())


def write_new(path, value):
    with Path(path).open("x") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def unique_cases(cases):
    result = {cue["id"]: cue for cue in cases}
    if len(result) != len(cases):
        raise ValueError("duplicate cue IDs")
    return result


def validate_identity(manifest, cue):
    runtime = manifest["runtime"]
    parameters = manifest["parameters"]
    expected_generation = {k: v for k, v in parameters.items() if k != "text_conditioning"}
    if (manifest["status"] != "generated_signal_checked" or manifest["provider"] != "qwen_mlx"
            or parameters["speaker"] != "Serena" or parameters.get("stream") is not False
            or parameters.get("text_conditioning") != "full_text"):
        raise ValueError("expected completed, non-streamed Serena full-text synthesis")
    context = runtime["text_conditioning"]
    if (runtime["parameters"] != parameters
            or runtime["effective_generation_parameters"] != expected_generation
            or context["effective_text_context"] != "full_text"
            or context.get("reference_conditioning") is not False):
        raise ValueError("inconsistent effective runtime identity")
    synthesis = cue["synthesis"]
    if (synthesis["seed"] != manifest["seed"]
            or synthesis["text_conditioning"] != context
            or synthesis["effective_generation_parameters"] != expected_generation
            or any(synthesis[key] != parameters[key]
                   for key in ("speaker", "language", "instruct"))):
        raise ValueError(f"per-cue identity mismatch: {cue['id']}")


def validate_retake(base, old_manifest, retake, new_manifest):
    """Require the same utterance and voice setup with one declared numeric change."""
    validate_identity(old_manifest, base)
    validate_identity(new_manifest, retake)
    for key in ("id", "subtitle_text", "spoken_text"):
        if base[key] != retake[key]:
            raise ValueError(f"retake {key} changed: {base['id']}")
    old, new = old_manifest["runtime"], new_manifest["runtime"]
    if (old["model"]["content_sha256"] != new["model"]["content_sha256"]
            or any(old[key] != new[key] for key in (
                "versions", "model_repo", "model_revision", "text_conditioning", "context_scope",
            ))
            or old_manifest["adapter_sources"] != new_manifest["adapter_sources"]
            or old_manifest["seed"] != new_manifest["seed"]):
        raise ValueError("retake model/runtime/context/seed differs")
    for key in ("parameters", "effective_generation_parameters"):
        before, after = old[key], new[key]
        expected = {**before, "temperature": 0.5}
        if before["temperature"] != 0.7 or after != expected:
            raise ValueError("retake allows only temperature 0.7 -> 0.5")


def validate_wave(cue, manifest_path):
    import soundfile as sf

    path = Path(cue["audio"]["path"]).resolve(strict=True)
    if path.parent != Path(manifest_path).resolve().parent:
        raise ValueError("cue WAV escaped its source manifest directory")
    if sha256(path) != cue["audio"]["sha256"] or path.stat().st_size != cue["audio"]["bytes"]:
        raise ValueError(f"source WAV hash/size changed: {cue['id']}")
    wave, rate = sf.read(path, dtype="float32")
    measured = signal_report(wave, rate, 60)
    if rate != 24000 or measured != cue["signal"]:
        raise ValueError(f"decoded source WAV differs from receipt: {cue['id']}")
    return path, measured


def compose(base_path, retake_path, output, ids, *, expected_count=None):
    base_path = Path(base_path).resolve(strict=True)
    retake_path = Path(retake_path).resolve(strict=True)
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("composition output exists; never overwrite a voice revision")
    base, retakes = read(base_path), read(retake_path)
    base_sha, retake_sha = sha256(base_path), sha256(retake_path)
    old_ids = [c["id"] for chapter in base["chapters"] for c in chapter["cues"]]
    expected_count = len(old_ids) if expected_count is None else expected_count
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("explicit retake IDs must be nonempty and unique")
    if (len(old_ids) != expected_count or len(set(old_ids)) != expected_count
            or not set(ids) <= set(old_ids)):
        raise ValueError("base cue count/IDs differ from the selected episode")
    candidates = unique_cases(retakes["cases"])
    if not set(ids) <= candidates.keys():
        raise ValueError("retake manifest lacks one of the explicitly selected IDs")
    verified, source_manifests = {}, []
    # Complete all source validation before creating the new output directory.
    for chapter in base["chapters"]:
        manifest_path = Path(chapter["manifest"]).resolve(strict=True)
        if sha256(manifest_path) != chapter["manifest_sha256"]:
            raise ValueError("base source manifest changed")
        manifest = read(manifest_path)
        if chapter["runtime"] != manifest["runtime"]:
            raise ValueError("base index runtime differs from its source manifest")
        source_manifests.append({"path": str(manifest_path), "sha256": sha256(manifest_path)})
        originals = unique_cases(manifest["cases"])
        for indexed in chapter["cues"]:
            cue_id = indexed["id"]
            original = originals[cue_id]
            validate_identity(manifest, original)
            old_path, old_signal = validate_wave(original, manifest_path)
            if (indexed["text"] != original["subtitle_text"]
                    or indexed["spoken_text"] != original["spoken_text"]
                    or Path(indexed["path"]).resolve() != old_path
                    or indexed["sha256"] != original["audio"]["sha256"]
                    or indexed["synthesis"] != original["synthesis"]
                    or any(indexed[k] != v for k, v in old_signal.items())):
                raise ValueError(f"base index cue differs from manifest: {cue_id}")
            if cue_id in ids:
                replacement = candidates[cue_id]
                validate_retake(original, manifest, replacement, retakes)
                new_path, signal = validate_wave(replacement, retake_path)
                verified[cue_id] = (replacement, new_path, signal)
    output.mkdir(parents=True, exist_ok=False)
    takes_directory = output / "retakes"
    takes_directory.mkdir()
    snapshot = takes_directory / "source_manifest.json"
    shutil.copyfile(retake_path, snapshot)
    if sha256(snapshot) != retake_sha:
        raise ValueError("retake manifest changed during copy")
    take_receipts, chapters = [], []
    for chapter in base["chapters"]:
        updated = {k: deepcopy(v) for k, v in chapter.items()
                   if k not in ("runtime", "manifest", "manifest_sha256", "cues")}
        updated.update(
            base_runtime=deepcopy(chapter["runtime"]),
            base_manifest=chapter["manifest"], base_manifest_sha256=chapter["manifest_sha256"],
            runtime_policy="base_runtime describes retained takes only; use each cue's synthesis",
            cues=[],
        )
        for old_cue in chapter["cues"]:
            cue = deepcopy(old_cue)
            cue.update(source_manifest=chapter["manifest"],
                       source_manifest_sha256=chapter["manifest_sha256"], take_kind="retained_base")
            if cue["id"] in verified:
                replacement, source_wav, signal = verified[cue["id"]]
                destination = takes_directory / f"{cue['id']}.wav"
                shutil.copyfile(source_wav, destination)
                if sha256(destination) != replacement["audio"]["sha256"]:
                    raise ValueError("retake WAV changed during copy")
                cue.update(
                    **signal, path=str(destination), sha256=sha256(destination),
                    bytes=destination.stat().st_size, synthesis=deepcopy(replacement["synthesis"]),
                    source_manifest=str(snapshot), source_manifest_sha256=retake_sha,
                    source_audio_path=str(source_wav), take_kind="explicit_temperature_retake",
                )
                take_receipts.append({
                    "id": cue["id"], "old_audio_path": old_cue["path"],
                    "old_audio_sha256": old_cue["sha256"], "new_audio_path": str(destination),
                    "new_audio_sha256": cue["sha256"], "source_audio_path": str(source_wav),
                    "old_temperature": 0.7, "new_temperature": 0.5,
                })
            cue["listening_status"] = "pending_user_mac_review"
            updated["cues"].append(cue)
        chapters.append(updated)
    receipt = {
        "schema_version": 1, "policy": "explicit fixed-ID retakes; only temperature may change",
        "script": str(Path(__file__).resolve()), "script_sha256": sha256(__file__),
        "base_index": str(base_path), "base_index_sha256": base_sha,
        "retake_manifest": str(retake_path), "retake_manifest_sha256": retake_sha,
        "preserved_manifest_snapshot": str(snapshot), "source_manifests": source_manifests,
        "retake_ids": list(ids), "retakes": take_receipts,
        "retained_cue_count": expected_count - len(ids), "replaced_cue_count": len(ids),
        "human_listening": "not_performed_pending_user_mac_review",
        "limitation": "Speaker metrics select review candidates; "
                      "they do not certify perceived identity.",
    }
    receipt_path = output / "retake_receipt.json"
    write_new(receipt_path, receipt)
    index = {k: deepcopy(v) for k, v in base.items()
             if k not in ("revision", "chapters", "request_sha256")}
    index.update(
        revision=output.name, chapters=chapters,
        base_index=str(base_path), base_index_sha256=base_sha,
        retake_receipt=str(receipt_path), retake_receipt_sha256=sha256(receipt_path),
        synthesis_policy={"retained_temperature": 0.7, "retake_temperature": 0.5,
                          "retake_ids": list(ids), "parameter_scope": "per cue"},
        listening_status="pending_user_mac_review",
        consistency_status="proxy_review_required_not_human_verified",
    )
    if "cues" in base:
        index["cues"] = [cue for chapter in chapters for cue in chapter["cues"]]
    # Recheck every retained/copied output and both frozen inputs after assembly.
    for chapter in chapters:
        for cue in chapter["cues"]:
            if sha256(cue["path"]) != cue["sha256"]:
                raise ValueError("selected audio changed during composition")
    if sha256(base_path) != base_sha or sha256(retake_path) != retake_sha:
        raise ValueError("source index/manifest changed during composition")
    write_new(output / "index.json", index)
    return output / "index.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-index", type=Path, required=True)
    parser.add_argument("--retake-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--ids", nargs="+", required=True)
    parser.add_argument("--expected-count", type=int)
    args = parser.parse_args()
    for path in (args.base_index, args.retake_manifest, args.output_dir):
        if not path.resolve().is_relative_to(ROOT):
            raise ValueError("composition inputs and output must remain in the project")
    print(compose(args.base_index, args.retake_manifest, args.output_dir, args.ids,
                  expected_count=args.expected_count))


if __name__ == "__main__":
    main()

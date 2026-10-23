#!/usr/bin/env python3
"""Compose explicit seed-only Serena retakes into a new, immutable voice index.

Run in .venv-speech; no model inference, network, tempo or pitch changes occur.
Every source is checked before writing. A completed index is written last.
This verifies recorded text and signals, not audible omissions or voice quality.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from compose_temperature_voice import (  # noqa: E402
    read,
    sha256,
    unique_cases,
    validate_identity,
    validate_wave,
    write_new,
)
from synthesize_voice import signal_report as signal_report  # noqa: E402

from mathcoffee.speech.planning import make_plan  # noqa: E402

GENERATED_FIELDS = {"synthesis", "signal", "audio", "timeline", "subtitle"}


def digest_json(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def runtime_identity(manifest):
    # Load timing is a measurement, not a generation parameter. No other runtime
    # field is discarded, including model provenance, device and context scope.
    return {k: v for k, v in manifest["runtime"].items() if k != "load_seconds"}


def validate_retake(base, old_manifest, retake, new_manifest):
    validate_identity(old_manifest, base)
    validate_identity(new_manifest, retake)
    for field in (
        "id",
        "subtitle_text",
        "spoken_text",
        "spans",
        "normalization_changes",
        "expected_readings",
        "provider",
    ):
        if base[field] != retake[field]:
            raise ValueError(f"retake {field} changed: {base['id']}")
    for field in (
        "profile",
        "provider",
        "parameters",
        "capabilities",
        "platform",
        "adapter_sources",
        "gap_seconds",
    ):
        if old_manifest[field] != new_manifest[field]:
            raise ValueError(f"seed-only policy forbids changed {field}")
    if runtime_identity(old_manifest) != runtime_identity(new_manifest):
        raise ValueError("seed-only policy forbids changed model/runtime/context")
    for manifest in (old_manifest, new_manifest):
        if type(manifest["seed"]) is not int or not 0 <= manifest["seed"] < 2**32:
            raise ValueError("seed must be uint32")
    if old_manifest["seed"] == new_manifest["seed"]:
        raise ValueError("explicit seed-only retake requires a different seed")
    if base["synthesis"]["context_scope"] != retake["synthesis"]["context_scope"]:
        raise ValueError("per-cue context scope changed")


class SourceGuard:
    """Hash each distinct dependency once, then recheck before publishing index."""

    def __init__(self):
        self.sources = {}

    def check(self, path, expected):
        path = Path(path).resolve(strict=True)
        if not path.is_file():
            raise ValueError(f"source is not a file: {path}")
        previous = self.sources.get(str(path))
        if previous is not None and previous != expected:
            raise ValueError(f"conflicting source hashes: {path}")
        if previous is None and sha256(path) != expected:
            raise ValueError(f"stale source hash: {path}")
        self.sources[str(path)] = expected
        return path

    def recheck(self):
        for path, expected in self.sources.items():
            if sha256(path) != expected:
                raise ValueError(f"source changed during composition: {path}")


def validate_manifest(manifest, guard, root):
    """Rebuild text plans and cache identity from the preserved real input files."""
    cases = unique_cases(manifest["cases"])
    if not cases:
        raise ValueError("empty generated manifest")
    inputs = {}
    for source, digest in manifest["inputs"].items():
        source = guard.check(source, digest)
        value = read(source)
        keys = [key for key in ("cases", "profiles", "aliases") if key in value]
        if len(keys) != 1 or keys[0] in inputs:
            raise ValueError("ambiguous or duplicate synthesis input roles")
        inputs[keys[0]] = (source, value)
    if set(inputs) != {"cases", "profiles", "aliases"}:
        raise ValueError("missing case/profile/lexicon source")
    source_cases = unique_cases(inputs["cases"][1]["cases"])
    profiles = inputs["profiles"][1]["profiles"]
    if profiles[manifest["profile"]][manifest["provider"]] != manifest["parameters"]:
        raise ValueError("profile parameters differ from frozen source")
    plans = []
    for cue in cases.values():
        validate_identity(manifest, cue)
        if cue["synthesis"]["context_scope"] != manifest["runtime"]["context_scope"]:
            raise ValueError("per-cue context scope differs from runtime")
        plan = make_plan(source_cases[cue["id"]], manifest["provider"], inputs["aliases"][1])
        if plan != {k: v for k, v in cue.items() if k not in GENERATED_FIELDS}:
            raise ValueError(f"text/normalization plan differs from source: {cue['id']}")
        plans.append(plan)
    for source, digest in manifest["adapter_sources"].items():
        guard.check(root / source, digest)
    runtime = manifest["runtime"]
    context = runtime["text_conditioning"]
    guard.check(context["upstream_source_path"], context["upstream_source_sha256"])
    model = runtime["model"]
    if digest_json(model["files"]) != model["content_sha256"]:
        raise ValueError("model file ledger content identity differs")
    model_root = Path(model["directory"]).resolve(strict=True)
    for entry in model["files"]:
        model_path = (model_root / entry["path"]).resolve(strict=True)
        if not model_path.is_relative_to(model_root):
            raise ValueError("model file escaped model directory")
        guard.check(model_path, entry["sha256"])
        if model_path.stat().st_size != entry["bytes"]:
            raise ValueError("model file size differs")
    source = model["source"]
    guard.check(source["manifest_path"], source["manifest_sha256"])
    if (
        source["status"] != "matched_pinned_source"
        or source["repo"] != runtime["model_repo"]
        or source["revision"] != runtime["model_revision"]
    ):
        raise ValueError("model source/runtime revision differs")
    identity = {
        "provider": manifest["provider"],
        "parameters": manifest["parameters"],
        "seed": manifest["seed"],
        "gap_seconds": manifest["gap_seconds"],
        "plans": plans,
        "inputs": manifest["inputs"],
        "adapter_sources": manifest["adapter_sources"],
        "runtime": runtime_identity(manifest),
    }
    if digest_json(identity) != manifest["synthesis_identity_sha256"]:
        raise ValueError("synthesis identity hash differs from recorded request")
    # Selected-case manifests may share a larger input case catalog. The two
    # non-case sources must be exactly identical between original and retake.
    return {
        key: (str(inputs[key][0]), guard.sources[str(inputs[key][0])])
        for key in ("profiles", "aliases")
    }


def compose(base_path, retake_path, output, ids, *, authoring_path, cut_path=None,
            expected_count=None, project_root=ROOT):
    root = Path(project_root).resolve(strict=True)
    base_path, retake_path = (Path(p).resolve(strict=True) for p in (base_path, retake_path))
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("composition output exists; never overwrite a voice revision")
    if (
        not ids
        or len(set(ids)) != len(ids)
        or any(not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", cue_id) for cue_id in ids)
    ):
        raise ValueError("explicit retake IDs must be nonempty, unique safe names")
    guard = SourceGuard()
    base_sha, retake_sha = sha256(base_path), sha256(retake_path)
    guard.check(base_path, base_sha)
    guard.check(retake_path, retake_sha)
    base, retakes = read(base_path), read(retake_path)
    selected_ids = [c["id"] for chapter in base["chapters"] for c in chapter["cues"]]
    expected_count = len(selected_ids) if expected_count is None else expected_count
    if (
        len(selected_ids) != expected_count
        or len(set(selected_ids)) != expected_count
        or not set(ids) <= set(selected_ids)
    ):
        raise ValueError("base cue count/IDs differ from selected episode")
    request_path = guard.check(base_path.parent / "request.json", base["request_sha256"])
    request = read(request_path)
    if request["selected_ids"] != selected_ids:
        raise ValueError("base index order differs from original request")
    for source, digest in request["sources"].items():
        guard.check(root / source, digest)
    authored_path = guard.check(authoring_path, base["source_sha256"])
    authored = read(authored_path)
    if "scenes" in authored and "chapters" not in authored:
        authored = {**authored, "chapters": [
            {**scene, "cues": scene["sentences"]} for scene in authored["scenes"]
        ]}
    excluded = set()
    if cut_path is not None:
        cut_path = Path(cut_path).resolve(strict=True)
        cut_key = str(cut_path.relative_to(root))
        if cut_key not in request["sources"]:
            raise ValueError("cut is not frozen by original voice request")
        cut = read(guard.check(cut_path, request["sources"][cut_key]))
        if cut["source_authoring_sha256"] != base["source_sha256"]:
            raise ValueError("cut source differs from authoring")
        excluded = {c["id"] for c in cut["excluded_cues"]}
    expected_chapters = [
        [(c["id"], c["text"]) for c in chapter["cues"] if c["id"] not in excluded]
        for chapter in authored["chapters"]
    ]
    if expected_chapters != [
        [(c["id"], c["text"]) for c in chapter["cues"]] for chapter in base["chapters"]
    ] or [c["id"] for c in authored["chapters"]] != [c["id"] for c in base["chapters"]]:
        raise ValueError("base index order/text differs from selected authoring")
    candidates = unique_cases(retakes["cases"])
    if not set(ids) <= candidates.keys():
        raise ValueError("retake manifest lacks an explicitly selected ID")
    retake_inputs = validate_manifest(retakes, guard, root)
    verified, source_manifests = {}, []
    for chapter in base["chapters"]:
        manifest_path = guard.check(chapter["manifest"], chapter["manifest_sha256"])
        manifest = read(manifest_path)
        original_inputs = validate_manifest(manifest, guard, root)
        if chapter["runtime"] != manifest["runtime"]:
            raise ValueError("base index runtime differs from source manifest")
        if (
            manifest["parameters"] != request["parameters"]
            or manifest["seed"] != request["seed"]
            or manifest["runtime"]["model"]["content_sha256"] != request["model_content_sha256"]
            or manifest["runtime"]["versions"] != request["runtime_versions"]
        ):
            raise ValueError("base manifest identity differs from original request")
        originals = unique_cases(manifest["cases"])
        if list(originals) != [c["id"] for c in chapter["cues"]]:
            raise ValueError("base chapter index/manifest cue order differs")
        source_manifests.append({"path": str(manifest_path), "sha256": sha256(manifest_path)})
        for indexed in chapter["cues"]:
            cue_id = indexed["id"]
            original = originals[cue_id]
            old_path, old_signal = validate_wave(original, manifest_path)
            guard.check(old_path, original["audio"]["sha256"])
            if (
                indexed["text"] != original["subtitle_text"]
                or indexed["spoken_text"] != original["spoken_text"]
                or Path(indexed["path"]).resolve() != old_path
                or indexed["sha256"] != original["audio"]["sha256"]
                or indexed["bytes"] != original["audio"]["bytes"]
                or indexed["synthesis"] != original["synthesis"]
                or any(indexed[k] != v for k, v in old_signal.items())
            ):
                raise ValueError(f"base index cue differs from manifest: {cue_id}")
            if cue_id in ids:
                replacement = candidates[cue_id]
                validate_retake(original, manifest, replacement, retakes)
                if original_inputs != retake_inputs:
                    raise ValueError("seed-only policy forbids changed profile/lexicon source")
                new_path, signal = validate_wave(replacement, retake_path)
                guard.check(new_path, replacement["audio"]["sha256"])
                verified[cue_id] = (replacement, new_path, signal)
    output.mkdir(parents=True, exist_ok=False)
    snapshots = output / "sources"
    snapshots.mkdir()
    for name, source, digest in [
        ("base_index.json", base_path, base_sha),
        ("base_request.json", request_path, sha256(request_path)),
        ("retake_manifest.json", retake_path, retake_sha),
        *[
            (f"base_manifest_{i:02}.json", Path(item["path"]), item["sha256"])
            for i, item in enumerate(source_manifests)
        ],
    ]:
        destination = snapshots / name
        shutil.copyfile(source, destination)
        guard.check(destination, digest)
    takes = output / "retakes"
    takes.mkdir()
    chapters, receipts = [], []
    for chapter in base["chapters"]:
        updated = {
            k: deepcopy(v)
            for k, v in chapter.items()
            if k not in ("runtime", "manifest", "manifest_sha256", "cues")
        }
        updated.update(
            base_runtime=deepcopy(chapter["runtime"]),
            base_manifest=chapter["manifest"],
            base_manifest_sha256=chapter["manifest_sha256"],
            runtime_policy="Identical configuration; read seed from each cue's synthesis.",
            cues=[],
        )
        for old_cue in chapter["cues"]:
            cue = deepcopy(old_cue)
            cue.update(
                source_manifest=chapter["manifest"],
                source_manifest_sha256=chapter["manifest_sha256"],
                take_kind="retained_base",
            )
            if cue["id"] in verified:
                replacement, source_wav, signal = verified[cue["id"]]
                destination = takes / f"{cue['id']}.wav"
                shutil.copyfile(source_wav, destination)
                guard.check(destination, replacement["audio"]["sha256"])
                cue.update(
                    **signal,
                    path=str(destination),
                    sha256=sha256(destination),
                    bytes=destination.stat().st_size,
                    synthesis=deepcopy(replacement["synthesis"]),
                    source_manifest=str(snapshots / "retake_manifest.json"),
                    source_manifest_sha256=retake_sha,
                    source_audio_path=str(source_wav),
                    take_kind="explicit_seed_retake",
                )
                receipts.append(
                    {
                        "id": cue["id"],
                        "old_audio_path": old_cue["path"],
                        "old_audio_sha256": old_cue["sha256"],
                        "new_audio_path": str(destination),
                        "new_audio_sha256": cue["sha256"],
                        "source_audio_path": str(source_wav),
                        "old_seed": old_cue["synthesis"]["seed"],
                        "new_seed": cue["synthesis"]["seed"],
                    }
                )
            cue["listening_status"] = "pending_user_mac_review"
            updated["cues"].append(cue)
        chapters.append(updated)
    receipt = {
        "schema_version": 1,
        "policy": "explicit IDs; only generation seed may change",
        "script": str(Path(__file__).resolve()),
        "script_sha256": sha256(__file__),
        "validator_script": str(ROOT / "scripts/compose_temperature_voice.py"),
        "validator_script_sha256": sha256(ROOT / "scripts/compose_temperature_voice.py"),
        "base_index": str(base_path),
        "base_index_sha256": base_sha,
        "retake_manifest": str(retake_path),
        "retake_manifest_sha256": retake_sha,
        "retake_ids": list(ids),
        "retakes": receipts,
        "retained_cue_count": expected_count - len(ids),
        "replaced_cue_count": len(ids),
        "validated_sources": guard.sources,
        "human_listening": "not_performed_pending_user_mac_review",
        "limitation": "Recorded text and decoded signals do not prove audible pronunciation, "
        "completeness, naturalness or speaker consistency.",
    }
    receipt_path = output / "retake_receipt.json"
    write_new(receipt_path, receipt)
    index = {
        k: deepcopy(v)
        for k, v in base.items()
        if k not in ("revision", "chapters", "request_sha256")
    }
    index.update(
        revision=output.name,
        chapters=chapters,
        base_index=str(base_path),
        base_index_sha256=base_sha,
        retake_receipt=str(receipt_path),
        retake_receipt_sha256=sha256(receipt_path),
        synthesis_policy={
            "parameters": deepcopy(retakes["parameters"]),
            "retake_ids": list(ids),
            "seed_scope": "per cue",
            "postprocessing": "none",
        },
        listening_status="pending_user_mac_review",
        consistency_status="proxy_review_required_not_human_verified",
    )
    if "cues" in base:
        index["cues"] = [cue for chapter in chapters for cue in chapter["cues"]]
    guard.recheck()
    write_new(output / "index.json", index)
    return output / "index.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-index", type=Path, required=True)
    parser.add_argument("--retake-manifest", type=Path, required=True)
    parser.add_argument("--ids", nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--authoring", type=Path, required=True)
    parser.add_argument("--cut", type=Path)
    parser.add_argument("--expected-count", type=int)
    args = parser.parse_args()
    for path in (args.base_index, args.retake_manifest, args.output_dir):
        if not path.resolve().is_relative_to(ROOT):
            raise ValueError("composition inputs and output must remain in the project")
    print(compose(args.base_index, args.retake_manifest, args.output_dir, args.ids,
                  authoring_path=args.authoring, cut_path=args.cut,
                  expected_count=args.expected_count))


if __name__ == "__main__":
    main()

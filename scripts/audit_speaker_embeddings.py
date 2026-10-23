#!/usr/bin/env python3
"""Local speaker consistency proxy; never a human-listening or identity verdict.

Accepts {items:[{id,path,...}]} JSON, synthesize_voice.py manifests (cases),
or a chapter/cue voice index (chapters/cues). Inputs and model are read-only.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import platform
import time
from pathlib import Path

import kaldi_native_fbank as knf
import numpy as np
import onnxruntime as ort
import soundfile as sf
from scipy.signal import resample_poly

ort.disable_telemetry_events()

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "media/models/wespeaker-voxceleb-resnet34-LM/voxceleb_resnet34_LM.onnx"
MODEL_SHA = "7bb2f06e9df17cdf1ef14ee8a15ab08ed28e8d0ef5054ee135741560df2ec068"
REVISION = "f0c48c298fd835726c27956a5d617bad7115627e"
FEATURE_PARAMETERS = {
    "sample_rate": 16000,
    "num_mel_bins": 80,
    "frame_length_ms": 25,
    "frame_shift_ms": 10,
    "dither": 0.0,
    "window_type": "hamming",
    "use_energy": False,
    "snip_edges": True,
    "remove_dc_offset": True,
    "preemph_coeff": 0.97,
    "low_freq": 20.0,
    "high_freq": 0.0,
    "pcm_float_scale": 32768,
    "mean_normalization": "per_utterance_per_feature",
    "variance_normalization": False,
    "resampling": "scipy.signal.resample_poly",
    "crop": "metadata_active_start_end_if_present_else_full_wave",
}
LIMITATIONS = [
    "Proxy only: this is not a human listening or same-voice identity verdict.",
    "VoxCeleb-trained model: Chinese synthetic speech and emotion are outside "
    "its benchmark calibration.",
    "No pass/fail similarity threshold is asserted; duration, phonetics, prosody "
    "and channel can affect scores.",
    "Compare matched text sets and preprocessing. Low-score samples require listening; "
    "higher scores do not prove repair.",
]


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def resolve_path(value, manifest):
    path = Path(value)
    if path.is_absolute():
        return path
    if (manifest.parent / path).exists():
        return (manifest.parent / path).resolve()
    return (ROOT / path).resolve()


def load_items(manifest, excluded):
    data = json.loads(manifest.read_text())
    if isinstance(data, list):
        rows = data
    elif "items" in data:
        rows = data["items"]
    elif "cases" in data:
        rows = data["cases"]
    elif "chapters" in data:
        rows = [
            dict(cue, chapter_id=chapter["chapter_id"])
            for chapter in data["chapters"]
            for cue in chapter["cues"]
        ]
    else:
        raise ValueError("Expected items, cases, or chapters/cues in input JSON")
    items = []
    for row in rows:
        if row["id"] in excluded:
            continue
        info = row.get("audio", row)
        signal = row.get("signal", row)
        path = resolve_path(info["path"], manifest)
        items.append(
            {
                "id": row["id"],
                "path": str(path),
                "expected_sha256": info.get("sha256"),
                "active_start_sample": signal.get("active_start_sample"),
                "active_end_sample": signal.get("active_end_sample"),
                "chapter_id": row.get("chapter_id", row["id"].split("_")[0]),
                "text": row.get("spoken_text", row.get("text", row.get("subtitle_text", ""))),
            }
        )
    if not items or len({item["id"] for item in items}) != len(items):
        raise ValueError("Input must contain nonempty unique item IDs")
    return items


def features(wave, sample_rate):
    if wave.ndim != 1 or not np.isfinite(wave).all():
        raise ValueError("Expected finite mono waveform")
    gcd = math.gcd(sample_rate, 16000)
    if sample_rate != 16000:
        wave = resample_poly(wave, 16000 // gcd, sample_rate // gcd)
    if len(wave) < 8000:
        raise ValueError("Under 0.5 seconds: too short for this diagnostic")
    opts = knf.FbankOptions()
    opts.frame_opts.samp_freq = 16000
    opts.frame_opts.frame_length_ms = 25
    opts.frame_opts.frame_shift_ms = 10
    opts.frame_opts.dither = 0.0
    opts.frame_opts.window_type = "hamming"
    opts.frame_opts.snip_edges = True
    opts.frame_opts.remove_dc_offset = True
    opts.frame_opts.preemph_coeff = 0.97
    opts.mel_opts.num_bins = 80
    opts.mel_opts.low_freq = 20
    opts.mel_opts.high_freq = 0
    opts.use_energy = False
    fbank = knf.OnlineFbank(opts)
    fbank.accept_waveform(16000, (wave.astype(np.float32) * 32768).tolist())
    fbank.input_finished()
    mat = np.stack([fbank.get_frame(i) for i in range(fbank.num_frames_ready)])
    mat -= mat.mean(axis=0, keepdims=True)
    return mat.astype(np.float32)


def embed(item, session):
    started = time.monotonic()
    path = Path(item["path"])
    digest = sha(path)
    if item.get("expected_sha256") and digest != item["expected_sha256"]:
        raise ValueError(f"Audio hash mismatch: {path}")
    wave, sr = sf.read(path, dtype="float32", always_2d=True)
    samples, channels = wave.shape
    wave = wave.mean(axis=1)
    start = item.get("active_start_sample") or 0
    end = item.get("active_end_sample")
    end = samples if end is None else end
    if not (0 <= start < end <= samples):
        raise ValueError(f"Invalid active bounds: {item['id']}")
    mat = features(wave[start:end], sr)
    value = np.asarray(session.run(["embs"], {"feats": mat[None]})[0]).reshape(-1)
    if value.shape != (256,) or not np.isfinite(value).all() or np.linalg.norm(value) < 1e-10:
        raise ValueError(f"Invalid embedding: {item['id']}")
    value = value / np.linalg.norm(value)
    result = {k: v for k, v in item.items() if k != "expected_sha256"}
    result.update(
        {
            "sha256": digest,
            "bytes": path.stat().st_size,
            "sample_rate": sr,
            "samples": samples,
            "channels": channels,
            "crop_start_sample": start,
            "crop_end_sample": end,
            "duration_used_seconds": (end - start) / sr,
            "feature_frames": len(mat),
            "embedding": value.tolist(),
            "elapsed_seconds": time.monotonic() - started,
        }
    )
    return result, value


def statistics(values):
    values = np.asarray(values)
    return {
        "count": int(values.size),
        "mean": float(values.mean()),
        "median": float(np.median(values)),
        "minimum": float(values.min()),
        "p10": float(np.quantile(values, 0.1)),
        "maximum": float(values.max()),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--reference-id", default="approved_serena_emotion")
    parser.add_argument("--exclude-cut", type=Path)
    parser.add_argument("--only-ids", help="Comma-separated IDs for matched A/B subset")
    parser.add_argument("--model", type=Path, default=MODEL)
    parser.add_argument(
        "--compare", type=Path, help="Earlier report: matched IDs and reference must agree"
    )
    args = parser.parse_args()
    started = time.monotonic()
    script_sha256 = sha(__file__)
    if args.output.exists():
        raise FileExistsError(f"Refusing overwrite: {args.output}")
    if sha(args.model) != MODEL_SHA:
        raise ValueError("Model hash does not match pinned official ONNX")
    excluded = set()
    if args.exclude_cut:
        excluded = {row["id"] for row in json.loads(args.exclude_cut.read_text())["excluded_cues"]}
    items = load_items(args.input.resolve(), excluded)
    if args.only_ids:
        wanted = set(args.only_ids.split(","))
        items = [item for item in items if item["id"] in wanted]
        if {item["id"] for item in items} != wanted:
            raise ValueError("Requested IDs not all present")
    opts = ort.SessionOptions()
    opts.inter_op_num_threads = 1
    opts.intra_op_num_threads = 2
    session = ort.InferenceSession(
        str(args.model), sess_options=opts, providers=["CPUExecutionProvider"]
    )
    reference, reference_embedding = embed(
        {"id": args.reference_id, "path": str(args.reference.resolve())}, session
    )
    results, vectors = [], []
    for index, item in enumerate(items):
        result, vector = embed(item, session)
        result["cosine_to_reference"] = float(vector @ reference_embedding)
        results.append(result)
        vectors.append(vector)
        if (index + 1) % 10 == 0:
            print(f"Embedded {index + 1}/{len(items)}", flush=True)
    matrix = np.stack(vectors)
    pairwise = matrix @ matrix.T
    centroid = matrix.mean(axis=0)
    centroid /= np.linalg.norm(centroid)
    for index, result in enumerate(results):
        result["cosine_to_centroid"] = float(matrix[index] @ centroid)
        result["cosine_to_previous"] = None if index == 0 else float(pairwise[index, index - 1])
    comparisons = {}
    if args.compare:
        previous = json.loads(args.compare.read_text())
        if (
            previous["reference"]["sha256"] != reference["sha256"]
            or previous["model"]["sha256"] != MODEL_SHA
        ):
            raise ValueError("Compared report must use same reference and model")
        if previous["feature_parameters"] != FEATURE_PARAMETERS:
            raise ValueError("Compared preprocessing must match")
        old = {row["id"]: row for row in previous["items"]}
        matched = [row for row in results if row["id"] in old]
        mismatched_text = [
            row["id"] for row in matched if row.get("text") != old[row["id"]].get("text")
        ]
        if mismatched_text:
            raise ValueError(f"Matched-ID text differs: {mismatched_text}")
        if matched:
            old_mat = np.array([old[row["id"]]["embedding"] for row in matched])
            new_mat = np.array([row["embedding"] for row in matched])
            tri = np.triu_indices(len(matched), 1)
            comparisons = {
                "path": str(args.compare.resolve()),
                "sha256": sha(args.compare),
                "matched_ids": [row["id"] for row in matched],
                "old_reference": statistics(
                    [old[row["id"]]["cosine_to_reference"] for row in matched]
                ),
                "new_reference": statistics([row["cosine_to_reference"] for row in matched]),
                "old_pairwise": statistics((old_mat @ old_mat.T)[tri])
                if len(matched) > 1
                else None,
                "new_pairwise": statistics((new_mat @ new_mat.T)[tri])
                if len(matched) > 1
                else None,
            }
    tri = np.triu_indices(len(items), 1)
    report = {
        "schema_version": 1,
        "status": "PROXY_ANALYSIS_COMPLETE_NOT_HUMAN_LISTENING",
        "input": {"path": str(args.input.resolve()), "sha256": sha(args.input)},
        "exclusion_cut": {"path": str(args.exclude_cut.resolve()), "sha256": sha(args.exclude_cut)}
        if args.exclude_cut
        else None,
        "model": {
            "repository": "Wespeaker/wespeaker-voxceleb-resnet34-LM",
            "revision": REVISION,
            "path": str(args.model.resolve()),
            "sha256": MODEL_SHA,
            "license": "CC-BY-4.0",
        },
        "feature_parameters": FEATURE_PARAMETERS,
        "limitations": LIMITATIONS,
        "runtime": {
            name: importlib.metadata.version(name)
            for name in ["onnxruntime", "kaldi-native-fbank", "numpy", "scipy", "soundfile"]
        },
        "platform": platform.platform(),
        "script_sha256": script_sha256,
        "reference": reference,
        "summary": {
            "items": len(items),
            "reference": statistics([r["cosine_to_reference"] for r in results]),
            "pairwise": statistics(pairwise[tri]) if len(items) > 1 else None,
            "adjacent": statistics(np.diag(pairwise, 1)) if len(items) > 1 else None,
            "lowest_reference_ids": [
                r["id"] for r in sorted(results, key=lambda r: r["cosine_to_reference"])[:12]
            ],
            "lowest_adjacent_ids": [
                r["id"] for r in sorted(results[1:], key=lambda r: r["cosine_to_previous"])[:12]
            ],
        },
        "comparison": comparisons,
        "items": results,
        "pairwise_cosine": pairwise.tolist(),
        "elapsed_seconds": time.monotonic() - started,
        "audio_uploaded": False,
        "onnxruntime_telemetry_disabled": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "summary": report["summary"],
                "elapsed_seconds": report["elapsed_seconds"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

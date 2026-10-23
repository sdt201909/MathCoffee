"""Offline official Qwen forced alignment; timestamps never trim source audio.

The model conditions on the supplied transcript. Alignment is not an ASR,
pronunciation, completeness, or prosody test.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
import resource
import time
from pathlib import Path

REPO = "Qwen/Qwen3-ForcedAligner-0.6B"
REVISION = "c7cbfc2048c462b0d63a45797104fc9db3ad62b7"
WEIGHT_SHA256 = "47831d0e82f96b20e9034dba01a075ee06436654719f6a68289e49f1b65ce0e7"
IMPLEMENTATION_SHA256 = "0656ef055e14526cd67673db2246c2579bdffe80da7a1c0b139133858ff05b22"
RESOLUTION_SECONDS = 0.08


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_block_text(block: dict) -> None:
    """Require an explicit mapping to the exact normalized synthesis input."""
    cues = block.get("cues", [])
    if not cues or not isinstance(block.get("spoken_text"), str):
        raise ValueError("block needs cues and its actual synthesized spoken_text")
    seen = set()
    for cue in cues:
        if not cue.get("id") or cue["id"] in seen:
            raise ValueError("missing or duplicate cue id")
        seen.add(cue["id"])
        if not isinstance(cue.get("text"), str) or not cue["text"].strip():
            raise ValueError("each cue needs its original subtitle text")
        if not isinstance(cue.get("spoken_text"), str) or not cue["spoken_text"].strip():
            raise ValueError("each cue needs its actual normalized spoken_text")
    if "".join(cue["spoken_text"] for cue in cues) != block["spoken_text"]:
        raise ValueError("cue spoken_text concatenation differs from synthesis input")


class OfflineQwenAligner:
    def __init__(self, model_dir: Path):
        started = time.monotonic()
        model_dir = model_dir.resolve()
        os.environ.update(
            HF_HOME=str(model_dir / ".offline_home"),
            HF_HUB_OFFLINE="1",
            TRANSFORMERS_OFFLINE="1",
            HF_HUB_DISABLE_IMPLICIT_TOKEN="1",
            HF_HUB_DISABLE_TELEMETRY="1",
            DO_NOT_TRACK="1",
        )
        manifest_path = model_dir / "official_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("repo") != REPO or manifest.get("revision") != REVISION:
            raise ValueError("forced aligner manifest is not the pinned official snapshot")
        for row in manifest["files"]:
            path = model_dir / row["path"]
            if path.is_symlink() or not path.resolve().is_relative_to(model_dir):
                raise ValueError("unsafe model file path")
            if path.stat().st_size != row["bytes"] or sha256(path) != row["sha256"]:
                raise ValueError(f"model checksum mismatch: {row['path']}")
        weight_row = next(r for r in manifest["files"] if r["path"] == "model.safetensors")
        if weight_row["sha256"] != WEIGHT_SHA256:
            raise ValueError("model weight differs from pinned official SHA-256")

        import mlx.core as mx
        from mlx.utils import tree_flatten
        from mlx_audio.stt.models.qwen3_asr import qwen3_forced_aligner as impl
        from transformers import AutoTokenizer, WhisperFeatureExtractor

        implementation_path = Path(impl.__file__)
        if sha256(implementation_path) != IMPLEMENTATION_SHA256:
            raise ValueError("installed forced aligner implementation changed; review required")

        class RecordingProcessor(impl.ForceAlignProcessor):
            def parse_timestamp(self, word_list, timestamp):
                self.raw_ms = timestamp.tolist()
                self.fixed_ms = self.fix_timestamp(timestamp)
                return super().parse_timestamp(word_list, timestamp)

        mx.reset_peak_memory()
        config = impl.ForcedAlignerConfig.from_dict(
            json.loads((model_dir / "config.json").read_text())
        )
        model = impl.ForcedAlignerModel(config)
        weights = model.sanitize(mx.load(str(model_dir / "model.safetensors")))
        model.load_weights(list(weights.items()), strict=True)
        mx.eval(model.parameters())
        model.eval()
        # Upstream post_load_hook hard-codes trust_remote_code=True. Bypass it.
        model._tokenizer = AutoTokenizer.from_pretrained(
            str(model_dir), local_files_only=True, trust_remote_code=False, token=False
        )
        model._feature_extractor = WhisperFeatureExtractor.from_pretrained(
            str(model_dir), local_files_only=True, token=False
        )
        model.aligner_processor = RecordingProcessor()
        if config.timestamp_segment_time != 80:
            raise ValueError("unexpected timestamp grid")
        self.mx, self.model = mx, model
        self.runtime = {
            "repo": REPO, "revision": REVISION, "license": "Apache-2.0",
            "model_dir": str(model_dir), "manifest_sha256": sha256(manifest_path),
            "weights_sha256": WEIGHT_SHA256,
            "implementation_path": str(implementation_path),
            "implementation_sha256": IMPLEMENTATION_SHA256,
            "adapter_sha256": sha256(Path(__file__)),
            "versions": {p: importlib.metadata.version(p) for p in (
                "mlx-audio", "mlx", "transformers", "numpy", "soundfile"
            )},
            "model_class": type(model).__name__, "strict_weight_loading": True,
            "parameter_count": sum(int(v.size) for _, v in tree_flatten(model.parameters())),
            "parameter_dtypes": sorted({str(v.dtype) for _, v in tree_flatten(model.parameters())}),
            "load_seconds": time.monotonic() - started,
            "network_at_inference": False, "remote_code": False,
            "timestamp_resolution_seconds": RESOLUTION_SECONDS,
            "device": str(mx.default_device()),
        }

    def align_block(self, block: dict) -> dict:
        validate_block_text(block)
        import numpy as np
        import soundfile as sf
        from mlx_audio.utils import resample_audio

        path = Path(block["wav"]).resolve()
        before_sha = sha256(path)
        if block.get("wav_sha256") != before_sha:
            raise ValueError(f"WAV checksum mismatch or missing: {block['id']}")
        audio, sample_rate = sf.read(path, dtype="float32", always_2d=True)
        duration = len(audio) / sample_rate
        if not 0 < duration <= 300 or not np.isfinite(audio).all():
            raise ValueError("audio must be finite and between 0 and 300 seconds")
        processor = self.model.aligner_processor
        full_tokens, _ = processor.encode_timestamp(block["spoken_text"], "Chinese")
        cue_tokens = [processor.encode_timestamp(c["spoken_text"], "Chinese")[0]
                      for c in block["cues"]]
        if not all(cue_tokens) or [t for ts in cue_tokens for t in ts] != full_tokens:
            raise ValueError("cue token sequence differs from whole-block tokenization")
        mono = audio.mean(axis=1)
        analysis_audio = resample_audio(mono, sample_rate, 16000)
        start = time.monotonic()
        aligned = self.model.generate(
            audio=analysis_audio, text=block["spoken_text"], language="Chinese"
        )
        elapsed = time.monotonic() - start
        if [t.text for t in aligned.items] != full_tokens:
            raise ValueError("model output token sequence differs from supplied text")
        warnings, tokens, previous = [], [], 0.0
        clamped = 0
        for item in aligned.items:
            a, b = item.start_time, item.end_time
            if not all(math.isfinite(v) for v in (a, b)) or not 0 <= a <= b:
                raise ValueError("invalid token interval")
            if a < previous - 1e-9 or a >= duration or b > duration + RESOLUTION_SECONDS:
                raise ValueError("nonmonotonic or out-of-audio token interval")
            end = min(b, duration)
            clamped += int(b > duration)
            tokens.append({"text": item.text, "start": a, "end": end,
                           "predicted_end": b})
            previous = b
        repairs = sum(a != b for a, b in zip(processor.raw_ms, processor.fixed_ms, strict=True))
        zeros = sum(t["start"] == t["end"] for t in tokens)
        if repairs:
            warnings.append(f"{repairs} timestamp boundaries repaired by upstream LIS")
        if zeros:
            warnings.append(f"{zeros} tokens have zero duration at the 80 ms grid")
        if clamped:
            warnings.append(f"{clamped} ends clipped by <=80 ms to the source WAV boundary")
        cues, offset = [], 0
        for cue, expected in zip(block["cues"], cue_tokens, strict=True):
            selected = tokens[offset:offset + len(expected)]
            if selected[-1]["end"] <= selected[0]["start"]:
                raise ValueError("cue has no positive aligned duration")
            cues.append({"id": cue["id"], "text": cue["text"],
                         "spoken_text": cue["spoken_text"],
                         "start": selected[0]["start"], "end": selected[-1]["end"],
                         "token_start_index": offset, "token_end_index": offset + len(expected),
                         "tokens": selected})
            offset += len(expected)
        if any(a["end"] > b["start"] for a, b in zip(cues, cues[1:], strict=False)):
            raise ValueError("overlapping cue intervals")
        if sha256(path) != before_sha:
            raise ValueError("source WAV changed during alignment")
        return {
            "id": block["id"], "scene_id": block["scene_id"], "wav": str(path),
            "wav_sha256": before_sha, "sample_rate": sample_rate,
            "samples": len(audio), "channels": audio.shape[1], "duration": duration,
            "spoken_text": block["spoken_text"], "cues": cues,
            "raw_timestamp_bins": [v // 80 for v in processor.raw_ms],
            "raw_timestamp_ms": processor.raw_ms, "repaired_timestamp_ms": processor.fixed_ms,
            "monotonic_repair_count": repairs, "zero_duration_token_count": zeros,
            "boundary_clip_count": clamped,
            "first_token_start": tokens[0]["start"], "last_token_end": tokens[-1]["end"],
            "tail_after_last_token_seconds": duration - tokens[-1]["end"],
            "alignment_seconds": elapsed, "rtf": elapsed / duration,
            "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "mlx_peak_memory_bytes": self.mx.get_peak_memory(),
            "validation": {"status": (
                               "PASS_STRUCTURE_WITH_WARNINGS" if warnings else "PASS_STRUCTURE"
                           ),
                           "warnings": warnings, "input_text_exact": True,
                           "token_sequence_exact": True, "nonoverlapping_cues": True,
                           "source_wav_unchanged": True},
            "listening_status": "not_assessed",
            "completeness_status": "not_assessed_by_forced_alignment",
        }

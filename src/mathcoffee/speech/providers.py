"""Local adapters; never fetch a model, clone a voice, or call a remote API."""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import inspect
import json
import os
import re
import time
from copy import deepcopy
from pathlib import Path

from .planning import PronunciationError, patch_kokoro_phonemes

KOKORO_REPO = "hexgrad/Kokoro-82M-v1.1-zh"
KOKORO_REVISION = "01e7505bd6a7a2ac4975463114c3a7650a9f7218"
MODEL_SUFFIXES = {".json", ".safetensors", ".txt", ".model", ".tiktoken", ".pt", ".pth"}
QWEN_SOURCE_MANIFEST = Path(__file__).resolve().parents[3] / "toolchains/speech/model_files.json"
CAPABILITIES = {
    "kokoro": {
        "hard_phonemes": "v1.1-zh only, after strict character alignment",
        "style_instructions": False, "native_mixed_language": False,
        "explicit_language_splices": True, "voice_cloning": False,
        "rate_control": True, "network_at_synthesis": False,
    },
    "qwen_mlx": {
        "hard_phonemes": False, "style_instructions": "1.7B CustomVoice only",
        "native_mixed_language": True, "explicit_language_splices": False,
        "voice_cloning": False, "rate_control": False, "network_at_synthesis": False,
    },
}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def runtime_versions(names):
    return {name: importlib.metadata.version(name) for name in names}


def offline():
    # Deliberately override an ambient opt-in to network; models are staged separately.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"


def local_model_manifest(path):
    path = Path(path).resolve(strict=True)
    if not path.is_dir():
        raise ValueError("model path must be an existing local directory")
    files = []
    for directory, subdirectories, names in os.walk(path):
        # Do not descend into download caches or agent/tool bookkeeping directories.
        subdirectories[:] = sorted(d for d in subdirectories if not d.startswith("."))
        files.extend(
            Path(directory) / name for name in names
            if not name.startswith(".") and Path(name).suffix in MODEL_SUFFIXES
        )
    entries = [
        {"path": str(p.relative_to(path)), "bytes": p.stat().st_size, "sha256": sha256(p)}
        for p in sorted(files) if p.is_file()
    ]
    if not entries:
        raise ValueError("no local model files")
    identity = hashlib.sha256(
        json.dumps(entries, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    return {"directory": str(path), "files": entries, "content_sha256": identity}


def pinned_model_source(model_manifest, source_path=QWEN_SOURCE_MANIFEST):
    """Attribute a local snapshot only after matching the pinned public file tree.

    LFS OIDs are SHA256 of file bytes; ordinary Git OIDs hash the blob header plus
    bytes. Comparing a generic SHA256 to a Git OID would silently fail provenance.
    Hidden files and documentation do not affect the synthesis model identity.
    """
    source_path = Path(source_path)
    source = json.loads(source_path.read_text())
    if not re.fullmatch(r"[0-9a-f]{40}", source.get("revision", "")):
        raise ValueError("model source manifest needs an immutable Git revision")
    expected = {}
    for entry in source["files"]:
        relative = Path(entry["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("unsafe model source manifest path")
        if any(part.startswith(".") for part in relative.parts):
            continue
        if relative.suffix in MODEL_SUFFIXES:
            expected[str(relative)] = entry
    actual = {entry["path"]: entry for entry in model_manifest["files"]}
    reference = {"manifest_path": str(source_path.resolve()),
                 "manifest_sha256": sha256(source_path)}
    if not expected or actual.keys() != expected.keys():
        return {**reference, "status": "unverified_local", "reason": "model file set differs"}
    for name, entry in actual.items():
        official = expected[name]
        if entry["bytes"] != official["size"]:
            return {**reference, "status": "unverified_local", "reason": f"size differs: {name}"}
        if "lfs" in official:
            matches = entry["sha256"] == official["lfs"]["oid"]
        else:
            digest = hashlib.sha1(f"blob {entry['bytes']}\0".encode(), usedforsecurity=False)
            with (Path(model_manifest["directory"]) / name).open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            matches = digest.hexdigest() == official["oid"]
        if not matches:
            return {**reference, "status": "unverified_local", "reason": f"hash differs: {name}"}
    return {
        **reference, "status": "matched_pinned_source", "repo": source["repo"],
        "revision": source["revision"], "verified_files": len(actual),
    }


class KokoroProvider:
    name = "kokoro"
    sample_rate = 24_000

    def __init__(self, profile, plans, lexicon, model_path=None):
        offline()
        if any(s["language"] == "en" for p in plans for s in p["spans"]):
            # Misaki downloads this automatically unless checked before construction.
            if importlib.util.find_spec("en_core_web_sm") is None:
                raise RuntimeError(
                    "English Kokoro spans need the separately pinned en_core_web_sm package; "
                    "it is absent. No download was attempted. Use Qwen or stage this dependency."
                )
        import torch
        from huggingface_hub import hf_hub_download
        from kokoro import KModel, KPipeline

        filenames = {
            "model": "kokoro-v1_1-zh.pth", "config": "config.json",
            "voice_zh": f"voices/{profile['voice_zh']}.pt",
            "voice_en": f"voices/{profile['voice_en']}.pt",
        }
        self.paths = {
            key: (
                Path(model_path) / filename if model_path else Path(hf_hub_download(
                    KOKORO_REPO, filename, revision=KOKORO_REVISION,
                    local_files_only=True, token=False,
                ))
            ).resolve(strict=True)
            for key, filename in filenames.items()
        }
        self.model = KModel(
            repo_id=KOKORO_REPO, config=str(self.paths["config"]), model=str(self.paths["model"])
        ).eval()
        self.pipelines = {}
        for language in {s["language"] for p in plans for s in p["spans"]}:
            pipeline = KPipeline(
                lang_code="z" if language == "zh" else "a", repo_id=KOKORO_REPO,
                model=self.model, device="cpu",
            )
            path = str(self.paths[f"voice_{language}"])
            pipeline.voices[path] = torch.load(path, weights_only=True)
            self.pipelines[language] = pipeline
        self.profile, self.lexicon = profile, lexicon
        self.metadata = {
            "capabilities": CAPABILITIES[self.name],
            "versions": runtime_versions(["kokoro", "misaki", "torch", "numpy", "soundfile"]),
            "model_repo": KOKORO_REPO, "cache_revision": KOKORO_REVISION,
            "model_files": {k: {"path": str(p), "sha256": sha256(p)}
                            for k, p in self.paths.items()},
            "parameters": profile,
            "voice_note": "Explicit language spans may alter prosody, even with one embedding.",
        }

    def synthesize(self, plan, seed):
        import numpy as np
        import torch

        torch.manual_seed(seed)
        waves, details = [], []
        started, cursor = time.perf_counter(), 0
        for index, span in enumerate(plan["spans"]):
            language, text = span["language"], span["spoken"]
            pipeline = self.pipelines[language]
            original, tokens = pipeline.g2p(text)
            if language == "zh":
                phonemes, corrections = patch_kokoro_phonemes(
                    text, original, self.lexicon["pronunciations"]
                )
            else:
                if any(re.search(r"[A-Za-z0-9]", t.text) and not t.phonemes for t in tokens):
                    raise PronunciationError("English G2P omitted a word; explicit review required")
                phonemes, corrections = original, []
            if not phonemes or len(phonemes) > 510 or set(phonemes) - set(self.model.vocab):
                raise PronunciationError("empty, overlong or unsupported Kokoro phonemes")
            voice = str(self.paths[f"voice_{language}"])
            chunks = []
            for result in pipeline.generate_from_tokens(
                phonemes, voice=voice, speed=self.profile["speed"]
            ):
                if result.phonemes != phonemes:
                    raise PronunciationError("Kokoro altered/truncated the requested phonemes")
                if result.audio is not None:
                    chunks.append(result.audio.detach().cpu().numpy().astype(np.float32))
            if not chunks:
                raise RuntimeError("Kokoro returned no waveform")
            wave = np.concatenate(chunks)
            details.append({
                **span, "phonemes_original": original, "phonemes_used": phonemes,
                "context_overrides": corrections, "voice": self.profile[f"voice_{language}"],
                "start_sample": cursor, "end_sample": cursor + len(wave),
            })
            waves.append(wave)
            cursor += len(wave)
            if index < len(plan["spans"]) - 1:
                gap = np.zeros(round(self.profile["span_gap_seconds"] * self.sample_rate))
                waves.append(gap)
                cursor += len(gap)
        return np.concatenate(waves).astype(np.float32), {
            "spans": details, "seed": seed, "generation_seconds": time.perf_counter() - started,
        }


class QwenMLXProvider:
    name = "qwen_mlx"

    def __init__(self, profile, plans, lexicon, model_path=None):
        del plans, lexicon
        profile = deepcopy(profile)
        offline()
        if not model_path or not Path(model_path).is_dir():
            raise ValueError("Qwen needs --model-path to a fully staged local model directory")
        config = json.loads((Path(model_path) / "config.json").read_text())
        if config.get("tts_model_type") != "custom_voice":
            raise ValueError("only CustomVoice presets are allowed; no reference-audio cloning")
        if profile.get("instruct") and config.get("tts_model_size") != "1b7":
            raise ValueError("style instructions require the approved 1.7B CustomVoice variant")
        if "speed" in profile:
            raise ValueError("Qwen MLX custom_voice has no supported speed control")
        if "text" in profile:
            raise ValueError("text belongs to the normalized cue, not the voice profile")
        if profile.get("stream", False) is not False:
            raise ValueError("verified Qwen codec-length handling requires stream=False")
        self.model_identity = local_model_manifest(model_path)
        provenance = pinned_model_source(self.model_identity)
        if provenance["status"] != "matched_pinned_source":
            raise ValueError(
                f"local Qwen model does not match pinned source: {provenance['reason']}"
            )
        self.model_identity["source"] = provenance
        import mlx.core as mx
        from mlx_audio.tts.utils import load_model

        started = time.perf_counter()
        self.model = load_model(str(Path(model_path).resolve()), trust_remote_code=False)
        self.load_seconds = time.perf_counter() - started
        if self.model.tokenizer is None or self.model.speech_tokenizer is None:
            raise RuntimeError("Qwen tokenizer resources did not load from the local directory")
        if profile["speaker"].lower() not in {
            v.lower() for v in self.model.get_supported_speakers()
        }:
            raise ValueError("requested preset speaker is not in this model")
        if profile["language"].lower() not in {
            v.lower() for v in self.model.get_supported_languages()
        }:
            raise ValueError("unsupported Qwen language")
        self.profile, self.sample_rate = profile, self.model.sample_rate
        # Text conditioning and waveform streaming are independent.  The legacy
        # MLX path streams text even when stream=False.  Never pass an ignored
        # non_streaming_mode through generic **kwargs and claim full context.
        from .qwen_context import configure_custom_voice_context

        self.context_receipt = configure_custom_voice_context(
            self.model, profile.get("text_conditioning", "legacy_streaming_text")
        )
        self.generation_parameters = {
            key: value for key, value in profile.items() if key != "text_conditioning"
        }
        supported = inspect.signature(self.model.generate_custom_voice).parameters
        unknown = self.generation_parameters.keys() - supported.keys()
        if unknown:
            raise ValueError(f"unsupported CustomVoice parameters: {sorted(unknown)}")
        from .qwen_codec_length import configure_codec_length

        self.codec_receipt = configure_codec_length(
            self.model, stream=profile.get("stream", False)
        )
        self.metadata = {
            "capabilities": CAPABILITIES[self.name],
            "versions": runtime_versions(["mlx-audio", "mlx", "numpy", "soundfile"]),
            "model": self.model_identity, "parameters": profile,
            "model_repo": provenance["repo"], "model_revision": provenance["revision"],
            "load_seconds": self.load_seconds, "device": str(mx.default_device()),
            "text_conditioning": self.context_receipt,
            "codec_length": self.codec_receipt,
            "effective_generation_parameters": self.generation_parameters,
            "context_scope": "one request; no cross-request acoustic conditioning",
            "reproducibility_note": "Seed/parameters are recorded; cross-runtime bit identity "
                                    "is not guaranteed by MLX or this adapter.",
        }

    def synthesize(self, plan, seed):
        import mlx.core as mx
        import numpy as np

        from .qwen_codec_length import begin_codec_request, codec_request_records

        if self.generation_parameters.get("stream", False) is not False:
            raise ValueError("verified Qwen synthesis requires a complete non-streaming waveform")
        begin_codec_request(self.model)
        mx.random.seed(seed)
        started, chunks, results = time.perf_counter(), [], []
        # The same Serena request contains both languages: no voice-splice fallback.
        for result in self.model.generate_custom_voice(
            text=plan["spoken_text"], **self.generation_parameters
        ):
            if int(result.token_count) >= self.profile["max_tokens"]:
                raise RuntimeError("Qwen reached the token ceiling; cue may be truncated")
            mx.eval(result.audio)
            wave = np.asarray(result.audio, dtype=np.float32)
            expected_samples = (
                int(result.token_count) * self.codec_receipt["samples_per_codec_frame"]
            )
            if (wave.ndim != 1 or len(wave) != int(result.samples)
                    or len(wave) != expected_samples):
                raise RuntimeError("Qwen complete output lost samples relative to generated codecs")
            chunks.append(wave)
            results.append({
                "samples": int(result.samples), "token_count": int(result.token_count),
                "expected_samples_from_codecs": expected_samples,
                "complete_codec_clock_verified": True,
                "peak_memory_gb": float(result.peak_memory_usage),
            })
        if not chunks:
            raise RuntimeError("Qwen returned no waveform")
        codec_calls = codec_request_records(self.model)
        if (len(chunks) != 1 or len(codec_calls) != 1
                or codec_calls[0]["explicit_padding_frames"] != 0
                or codec_calls[0]["valid_samples"] != len(chunks[0])
                or codec_calls[0]["codec_frames"] != results[0]["token_count"]):
            raise RuntimeError("Qwen request did not yield one verified unpadded codec sequence")
        return np.concatenate(chunks), {
            "seed": seed, "generation_seconds": time.perf_counter() - started,
            "peak_mlx_bytes": int(mx.get_peak_memory()), "results": results,
            "phoneme_control": False, "language": self.profile["language"],
            "instruct": self.profile["instruct"], "speaker": self.profile["speaker"],
            "text_conditioning": self.context_receipt,
            "codec_length": self.codec_receipt, "codec_decode_calls": codec_calls,
            "effective_generation_parameters": self.generation_parameters,
            "context_scope": "one request; no cross-request acoustic conditioning",
        }


PROVIDERS = {"kokoro": KokoroProvider, "qwen_mlx": QwenMLXProvider}

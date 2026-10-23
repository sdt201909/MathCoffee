"""Preserve valid codec-zero frames in pinned, non-streaming CustomVoice.

MLX-Audio 0.5.7 counts ``code > 0`` to determine waveform length. Zero is a
valid generated code, so that mask can truncate the *end* of an utterance.
Official Qwen uses ``code > -1`` and clamps explicit -1 padding before decode:
https://github.com/QwenLM/Qwen3-TTS/blob/main/qwen_tts/core/tokenizer_12hz/modeling_qwen3_tts_tokenizer_v2.py
(decode, accessed 2026-10-02). This instance-local adapter preserves the exact
decoder and waveform, correcting only valid-length metadata. No installed code,
model weights, voice identity, or sampling parameters are changed.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import inspect
from copy import deepcopy
from pathlib import Path
from types import MethodType

ADAPTER_REVISION = "custom-voice-valid-code-zero-v1"
SUPPORTED_MLX_AUDIO = "0.5.7"
UPSTREAM_TOKENIZER_SHA256 = "b7ba5f695e9f6e8d8e235d6b78488eec085ad0582c1e6111614739f1de56f3b9"
_STATE_ATTRIBUTE = "_mathcoffee_codec_length"
_MODULE = "mlx_audio.tts.models.qwen3_tts.speech_tokenizer"


def valid_codec_lengths(codes, upsample_rate, array_module):
    """Count all nonnegative codes; accept only complete -1 suffix padding.

    NumPy is supported for fixtures. Production uses MLX arrays. This helper
    handles padded batches; the installed CustomVoice adapter is batch-one.
    """
    xp = array_module
    if len(codes.shape) != 3 or any(size < 1 for size in codes.shape):
        raise ValueError("codec array must have nonempty batch/time/codebook axes")
    if isinstance(upsample_rate, bool) or not isinstance(upsample_rate, int) or upsample_rate <= 0:
        raise ValueError("codec upsample rate must be a positive integer")
    if not xp.issubdtype(codes.dtype, xp.integer):
        raise ValueError("codec IDs must be integers")
    # MLX sampling may return uint32. Comparing it with -1 raises an overflow;
    # unsigned arrays have no explicit negative padding and all frames are valid.
    if xp.issubdtype(codes.dtype, xp.unsignedinteger):
        return xp.full((codes.shape[0],), codes.shape[1] * upsample_rate, dtype=xp.int32)
    valid = codes[..., 0] >= 0
    if bool(xp.any(codes < -1)):
        raise ValueError("only -1 is permitted as explicit codec padding")
    if bool(xp.any(xp.any(codes < 0, axis=-1) & valid)):
        raise ValueError("valid codec frames cannot contain negative codebook values")
    if bool(xp.any(xp.any(codes != -1, axis=-1) & ~valid)):
        raise ValueError("padding frames must be -1 in every codebook")
    if codes.shape[1] > 1 and bool(xp.any((~valid[:, :-1]) & valid[:, 1:])):
        raise ValueError("explicit codec padding must be a right suffix")
    lengths = xp.sum(valid, axis=1) * upsample_rate
    if bool(xp.any(lengths == 0)):
        raise ValueError("each codec sequence needs at least one valid frame")
    return lengths


def _validate_runtime(tokenizer):
    version = importlib.metadata.version("mlx-audio")
    if version != SUPPORTED_MLX_AUDIO:
        raise RuntimeError(f"codec-length adapter requires mlx-audio {SUPPORTED_MLX_AUDIO}")
    cls = type(tokenizer)
    if cls.__module__ != _MODULE or cls.__name__ != "Qwen3TTSSpeechTokenizer":
        raise RuntimeError("codec-length adapter requires the pinned Qwen speech tokenizer")
    source = Path(inspect.getfile(cls)).resolve()
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != UPSTREAM_TOKENIZER_SHA256:
        raise RuntimeError("Qwen tokenizer source hash changed; review codec-length adapter")
    if tuple(inspect.signature(cls.decode).parameters) != ("self", "audio_codes"):
        raise RuntimeError("Qwen tokenizer decode API changed")
    if tokenizer.decode_upsample_rate != 1920:
        raise RuntimeError("Qwen tokenizer codec clock changed")
    return {"mlx_audio_version": version, "tokenizer_source_path": str(source),
            "tokenizer_source_sha256": digest, "upstream_api_verified": True}


def _decode_with_valid_zero(self, audio_codes):
    state = getattr(self, _STATE_ATTRIBUTE)
    xp = state["array_module"]
    if len(audio_codes.shape) != 3 or audio_codes.shape[0] != 1:
        raise ValueError("CustomVoice codec-length adapter requires batch-one rank-three codes")
    if audio_codes.shape[2] != state["code_groups"]:
        raise ValueError("CustomVoice codec codebook count changed")
    lengths = valid_codec_lengths(audio_codes, self.decode_upsample_rate, xp)
    if bool(xp.any(audio_codes >= state["code_limit"])):
        raise ValueError("CustomVoice generated a reserved or out-of-range codec ID")
    # No valid sample/code changes. Only explicit -1 padding becomes safe 0 input.
    wav, legacy_lengths = state["original"](xp.maximum(audio_codes, 0))
    expected = audio_codes.shape[1] * self.decode_upsample_rate
    if len(wav.shape) != 2 or wav.shape != (1, expected):
        raise RuntimeError("complete Qwen decoder waveform does not match its codec clock")
    state["calls"].append({
        "codec_frames": audio_codes.shape[1], "complete_decoder_samples": expected,
        "valid_samples": int(lengths[0]), "legacy_mask_samples": int(legacy_lengths[0]),
        "valid_first_code_zero_frames": int(xp.sum(audio_codes[..., 0] == 0)),
        "explicit_padding_frames": (
            0 if xp.issubdtype(audio_codes.dtype, xp.unsignedinteger)
            else int(xp.sum(audio_codes[..., 0] == -1))
        ),
    })
    return wav, lengths


def configure_codec_length(model, *, stream=False):
    """Install once on the model instance; return deterministic cache metadata."""
    if stream is not False:
        raise ValueError("codec-length adapter supports stream=False only")
    if model.config.tts_model_type != "custom_voice":
        raise ValueError("codec-length adapter supports CustomVoice presets only")
    tokenizer = model.speech_tokenizer
    runtime = _validate_runtime(tokenizer)
    state = getattr(tokenizer, _STATE_ATTRIBUTE, None)
    if state is None:
        import mlx.core as mx

        original = tokenizer.decode
        if original.__func__ is not type(tokenizer).decode:
            raise RuntimeError("Qwen tokenizer decode already patched by an unknown adapter")
        config = model.config.talker_config
        if config.num_code_groups != 16 or config.vocab_size - 1024 != 2048:
            raise RuntimeError("CustomVoice codec codebook contract changed")
        state = {"original": original, "array_module": mx, "calls": [],
                 "code_groups": config.num_code_groups, "code_limit": 2048}
        setattr(tokenizer, _STATE_ATTRIBUTE, state)
        tokenizer.decode = MethodType(_decode_with_valid_zero, tokenizer)
    elif tokenizer.decode.__func__ is not _decode_with_valid_zero:
        raise RuntimeError("Qwen codec-length adapter was replaced externally")
    receipt = {
        "adapter_revision": ADAPTER_REVISION, "valid_first_code_predicate": ">=0",
        "explicit_padding_code": -1, "samples_per_codec_frame": 1920,
        "scope": "batch-one, non-streaming CustomVoice; no reference conditioning",
        "waveform_postprocessing": "none; correct valid-length metadata only",
        **runtime,
    }
    state["receipt"] = receipt
    return dict(receipt)


def begin_codec_request(model):
    """Reset only diagnostic records, not model conditioning or signal state."""
    state = getattr(model.speech_tokenizer, _STATE_ATTRIBUTE)
    state["calls"].clear()


def codec_request_records(model):
    return deepcopy(getattr(model.speech_tokenizer, _STATE_ATTRIBUTE)["calls"])

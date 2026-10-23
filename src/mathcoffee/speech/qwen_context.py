"""Explicit full-text prefill for the pinned MLX CustomVoice implementation.

MLX-Audio 0.5.7's ``stream=False`` controls waveform delivery, not text
conditioning. Its CustomVoice path still introduces one text token per codec
step. Qwen's official CustomVoice API defaults to ``non_streaming_mode=True``.
This instance-local adapter follows that input layout without changing model
weights, the preset speaker, generation sampling, or installed dependencies.

Official reference (accessed 2026-10-01):
https://github.com/QwenLM/Qwen3-TTS/blob/main/qwen_tts/core/models/modeling_qwen3_tts.py
``Qwen3TTSForConditionalGeneration.generate``, non-ICL non_streaming_mode branch.
This is a conditioning correction, not proof of audible speaker consistency.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import inspect
from pathlib import Path
from types import MethodType

ADAPTER_REVISION = "custom-voice-full-text-v1"
SUPPORTED_MLX_AUDIO = "0.5.7"
UPSTREAM_SHA256 = "0d9437e4f08680d7bf8cb7bf3b44c8e3de37ad9edf025f50dba37dface2e6902"
MODES = ("legacy_streaming_text", "full_text")
_STATE_ATTRIBUTE = "_mathcoffee_custom_voice_context"
_PREPARE_PARAMETERS = (
    "self", "text", "language", "speaker", "ref_audio", "ref_text", "instruct",
)
_GENERATE_PARAMETERS = (
    "self", "text", "speaker", "language", "instruct", "temperature", "max_tokens",
    "top_k", "top_p", "repetition_penalty", "verbose", "stream", "streaming_interval",
)


def _validate_runtime(model):
    """Fail closed rather than applying a private-API adapter to unknown code."""
    version = importlib.metadata.version("mlx-audio")
    if version != SUPPORTED_MLX_AUDIO:
        raise RuntimeError(f"Qwen text-context adapter requires mlx-audio {SUPPORTED_MLX_AUDIO}")
    model_type = type(model)
    if model_type.__module__ != "mlx_audio.tts.models.qwen3_tts.qwen3_tts":
        raise RuntimeError("Qwen text-context adapter requires the pinned MLX Qwen Model class")
    source_path = Path(inspect.getfile(model_type)).resolve()
    source_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
    if source_sha256 != UPSTREAM_SHA256:
        raise RuntimeError("MLX Qwen source hash changed; review the text-context adapter first")
    for method, expected in (
        ("_prepare_generation_inputs", _PREPARE_PARAMETERS),
        ("generate_custom_voice", _GENERATE_PARAMETERS),
    ):
        actual = tuple(inspect.signature(getattr(model_type, method)).parameters)
        if actual != expected:
            raise RuntimeError(f"MLX Qwen API changed: {method}")
    return {
        "mlx_audio_version": version,
        "upstream_source_path": str(source_path),
        "upstream_source_sha256": source_sha256,
        "upstream_api_verified": True,
    }


def full_text_prefill(*, prefix, text_embeddings, eos_embedding, text_pad,
                      codec_pad, codec_bos, array_module):
    """Assemble the official non-streaming, non-ICL layout.

    ``prefix`` already contains instruction, role, language and speaker.
    Fresh uncombined text embeddings avoid subtracting a rounded codec+text
    sum (not reversible in bfloat16). Only text-conditioning layout changes.
    ``array_module`` is MLX in production; NumPy supports independent fixtures.
    """
    values = (prefix, text_embeddings, eos_embedding, text_pad, codec_pad, codec_bos)
    if any(len(value.shape) != 3 or value.shape[0] != 1 for value in values):
        raise ValueError("CustomVoice full-text prefill requires batch-one rank-three arrays")
    width = prefix.shape[2]
    if any(value.shape[2] != width for value in values):
        raise ValueError("CustomVoice embedding widths disagree")
    if not prefix.shape[1] or not text_embeddings.shape[1]:
        raise ValueError("CustomVoice full-text prefill requires nonempty prefix and text")
    if any(value.shape[1] != 1 for value in values[2:]):
        raise ValueError("CustomVoice special-token embeddings must have length one")
    complete_text = array_module.concatenate([text_embeddings, eos_embedding], axis=1)
    inputs = array_module.concatenate([
        prefix, complete_text + codec_pad, text_pad + codec_bos,
    ], axis=1)
    return inputs, text_pad, text_pad


def _full_text_inputs(self, text, language="auto", speaker=None, ref_audio=None,
                      ref_text=None, instruct=None):
    if ref_audio is not None or ref_text is not None:
        raise ValueError("CustomVoice full-text adapter does not accept reference audio/text")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("CustomVoice full-text adapter requires nonempty text")
    if self.config.tts_model_type != "custom_voice":
        raise ValueError("CustomVoice full-text adapter cannot be used by Base/VoiceDesign")
    state = getattr(self, _STATE_ATTRIBUTE)
    mx = state["array_module"]
    # Preserve the upstream instruction/role/codec/speaker construction exactly.
    legacy_inputs, legacy_trailing, text_pad = state["original"](
        text=text, language=language, speaker=speaker, instruct=instruct,
    )
    chat = f"<|im_start|>assistant\n{text}<|im_end|>\n<|im_start|>assistant\n"
    ids = mx.array(self.tokenizer.encode(chat))[None, :]
    text_embeddings = self.talker.text_projection(
        self.talker.get_text_embeddings()(ids[:, 3:-5])
    )
    cfg = self.config.talker_config
    codec_tokens = self.talker.get_input_embeddings()(
        mx.array([[cfg.codec_pad_id, cfg.codec_bos_id]])
    )
    return full_text_prefill(
        prefix=legacy_inputs[:, :-1, :],
        text_embeddings=text_embeddings,
        eos_embedding=legacy_trailing[:, -1:, :],
        text_pad=text_pad,
        codec_pad=codec_tokens[:, 0:1, :],
        codec_bos=codec_tokens[:, 1:2, :],
        array_module=mx,
    )


def configure_custom_voice_context(model, mode="legacy_streaming_text"):
    """Select explicit text conditioning and return cacheable effective metadata.

    Call after loading a model, before generation. This mutates that instance's
    input preparation only; concurrent requests/mode changes are not supported.
    Restoring legacy mode reinstates the exact original bound method. Repeated
    application is idempotent and never nests wrappers.
    """
    if mode not in MODES:
        raise ValueError(f"unsupported Qwen text context {mode!r}; expected {MODES}")
    if model.config.tts_model_type != "custom_voice":
        raise ValueError("text-context adapter supports only CustomVoice preset models")
    runtime = _validate_runtime(model)
    state = getattr(model, _STATE_ATTRIBUTE, None)
    if state is None:
        import mlx.core as mx

        original = model._prepare_generation_inputs
        if original.__func__ is not type(model)._prepare_generation_inputs:
            raise RuntimeError("Qwen input preparation already patched by an unknown adapter")
        state = {"original": original, "array_module": mx}
        setattr(model, _STATE_ATTRIBUTE, state)
    if mode == "full_text":
        model._prepare_generation_inputs = MethodType(_full_text_inputs, model)
    else:
        model._prepare_generation_inputs = state["original"]
    receipt = {
        "adapter_revision": ADAPTER_REVISION,
        "effective_text_context": mode,
        "full_text_prefill": mode == "full_text",
        "reference_conditioning": False,
        "preset_speaker_changed": False,
        **runtime,
    }
    state["receipt"] = receipt
    return dict(receipt)

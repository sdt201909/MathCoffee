"""Offline seeded Serena smoke sample; no cloning, transcription, or quality claims."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import resource
import time
import wave
from pathlib import Path

os.environ.update(
    HF_HUB_OFFLINE="1",
    HF_HUB_DISABLE_IMPLICIT_TOKEN="1",
    TRANSFORMERS_OFFLINE="1",
    TOKENIZERS_PARALLELISM="false",
)


def main() -> None:
    import mlx.core as mx
    import numpy as np
    from mlx_audio.tts.utils import load_model

    root = Path(__file__).resolve().parents[2]
    folder = root / "media/reports/agent_upgrade/speech_runtime"
    manifest = json.loads((folder / "model_manifest.json").read_text())
    path = root / "media/models/Qwen3-TTS-12Hz-1.7B-CustomVoice"
    seed = 20260930
    mx.random.seed(seed)
    params = {
        "text": "别着急，我们慢慢来。你刚才这一步已经很接近了。",
        "speaker": "Serena",
        "language": "Chinese",
        "instruct": "用温柔、放松而自然的语气，像安静地陪朋友聊天，语句清晰，节奏舒缓但不要拖长。",
        "temperature": 0.7,
        "max_tokens": 256,
        "stream": False,
    }
    start = time.monotonic()
    model = load_model(path, strict=True)
    load_seconds = time.monotonic() - start
    if model.tokenizer is None or model.speech_tokenizer is None:
        raise RuntimeError("Model tokenizer did not load")
    start = time.monotonic()
    results = list(model.generate_custom_voice(**params))
    mx.synchronize()
    generate_seconds = time.monotonic() - start
    audio = np.concatenate(
        [np.asarray(item.audio, dtype=np.float32).reshape(-1) for item in results]
    )
    rates = {item.sample_rate for item in results}
    assert len(rates) == 1 and len(audio) and np.isfinite(audio).all()
    sample_rate = rates.pop()
    rms = float(np.sqrt(np.mean(np.square(audio))))
    assert rms > 1e-4, f"Silent output RMS={rms}"
    output = folder / "serena_smoke.wav"
    with wave.open(str(output), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes((np.clip(audio, -1, 1) * 32767).round().astype("<i2").tobytes())
    report = {
        "model_repo": manifest["repo"],
        "model_revision": manifest["revision"],
        "model_path": str(path),
        "runtime": {x: importlib.metadata.version(x) for x in ["mlx-audio", "mlx", "transformers"]},
        "seed": seed,
        "parameters": params,
        "weights": "original official BF16; runtime sanitize; no quantization or saved conversion",
        "load_seconds": load_seconds,
        "generate_seconds": generate_seconds,
        "audio_seconds": len(audio) / sample_rate,
        "rtf_generation_only": generate_seconds / (len(audio) / sample_rate),
        "sample_rate": sample_rate,
        "samples": len(audio),
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "mlx_peak_memory_bytes": mx.get_peak_memory(),
        "peak_amplitude": float(np.abs(audio).max()),
        "rms": rms,
        "clipped_samples": int(np.count_nonzero(np.abs(audio) >= 1)),
        "output": str(output),
        "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "checks": {
            "finite": True,
            "non_silent": True,
            "human_listened": False,
            "pronunciation_verified": False,
            "style_preference_verified": False,
        },
        "device": mx.device_info(),
    }
    (folder / "smoke.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()

"""Model-free voice planning and isolated local synthesis/import of measured PCM."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import wave
from pathlib import Path

from mathcoffee.environment import runtime_for
from mathcoffee.resources import data_path
from mathcoffee.synthesis import plan_case
from mathcoffee.workspace import workspace_path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.json")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def _worker_bootstrap() -> tuple[str, str]:
    package = Path(__file__).parent
    binding = "import importlib.util,sys; p=sys.argv.pop(1); s=importlib.util.spec_from_file_location('mathcoffee',p+'/__init__.py',submodule_search_locations=[p]); m=importlib.util.module_from_spec(s); sys.modules['mathcoffee']=m; s.loader.exec_module(m); "
    return str(package), binding


def _generation_identity(runtime: dict, provider: str) -> dict:
    python = runtime.get("speech_python")
    if not python or (provider == "qwen_mlx" and not runtime.get("model_path")):
        raise RuntimeError("speech runtime/model not configured; run explicit setup or select imported/silent voice")
    package, binding = _worker_bootstrap()
    probe = binding + "import json,importlib.metadata as v,hashlib; from pathlib import Path; from mathcoffee.speech.providers import local_model_manifest,pinned_model_source; names=['numpy','soundfile']+(['mlx-audio','mlx'] if sys.argv[1]=='qwen_mlx' else ['kokoro','misaki','torch']); result={'python':sys.version,'executable':str(Path(sys.executable).resolve()),'versions':{n:v.version(n) for n in names}}; model=local_model_manifest(Path(sys.argv[2])) if sys.argv[2] else None; result['model']=model; result['source']=pinned_model_source(model) if model and sys.argv[1]=='qwen_mlx' else None; print(json.dumps(result,sort_keys=True))"
    child = os.environ.copy()
    child.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_IMPLICIT_TOKEN="1", PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run([str(python), "-I", "-c", probe, package, provider, str(runtime.get("model_path") or "")], capture_output=True, text=True, check=True, env=child)
    identity = json.loads(result.stdout)
    if provider == "qwen_mlx":
        source_probe = binding + "import json,importlib.metadata as v,hashlib; from pathlib import Path; d=v.distribution('mlx-audio'); names=['mlx_audio/tts/models/qwen3_tts/qwen3_tts.py','mlx_audio/tts/models/qwen3_tts/speech_tokenizer.py']; print(json.dumps({n:hashlib.sha256(Path(d.locate_file(n)).read_bytes()).hexdigest() for n in names},sort_keys=True))"
        probe_result = subprocess.run([str(python), "-I", "-c", source_probe, package], capture_output=True, text=True, check=True, env=child)
        identity["upstream_sources"] = json.loads(probe_result.stdout)
        from mathcoffee.speech.qwen_context import UPSTREAM_SHA256
        from mathcoffee.speech.qwen_codec_length import UPSTREAM_TOKENIZER_SHA256
        expected = [UPSTREAM_SHA256, UPSTREAM_TOKENIZER_SHA256]
        if list(identity["upstream_sources"].values()) != expected:
            # JSON sort order places qwen3_tts.py before speech_tokenizer.py.
            raise ValueError("installed speech implementation differs from fixed upstream sources")
    if identity.get("source") and identity["source"]["status"] != "matched_pinned_source":
        raise ValueError("current model does not match the fixed public source")
    return identity


def _measure(path: Path) -> dict:
    """Measure integer PCM using stdlib; no synthesis environment is needed to import."""
    with wave.open(str(path), "rb") as stream:
        rate, count, channels, width = stream.getframerate(), stream.getnframes(), stream.getnchannels(), stream.getsampwidth()
        pcm = stream.readframes(count)
    if channels != 1 or width not in {2, 3, 4} or not count or rate <= 0:
        raise ValueError("voice cues must be nonempty mono PCM16/24/32 WAV files")
    if len(pcm) != count * channels * width:
        raise ValueError("voice PCM is truncated or differs from its declared sample count")
    scale = float(2 ** (8 * width - 1))
    samples = [int.from_bytes(pcm[i:i + width], "little", signed=True) / scale for i in range(0, len(pcm), width)]
    peak = max(abs(x) for x in samples)
    if peak < 1e-5 or peak >= 1:
        raise ValueError("voice PCM is silent or clipped")
    hop = max(1, round(rate * .01))
    active = [i for i in range(0, count, hop) if (sum(x*x for x in samples[i:i+hop]) / len(samples[i:i+hop])) ** .5 > max(peak * .012, .0006)]
    if not active:
        raise ValueError("no active PCM was measured")
    return {"sample_rate": rate, "samples": count, "channels": channels, "active_start_sample": max(0, active[0] - round(rate * .04)), "active_end_sample": min(count, active[-1] + hop + round(rate * .06))}


def _imported(root: Path, plan: dict) -> dict:
    index = plan["project"]["voice"].get("index")
    if not index:
        raise ValueError("voice.mode imported requires a workspace-relative voice.index")
    source = workspace_path(root, index)
    value = json.loads(source.read_text())
    items = value.get("cues", [])
    expected = plan["voice_request"]["cases"]
    if [x.get("id") for x in items] != [x["id"] for x in expected]:
        raise ValueError("imported cue IDs/order must exactly match canonical authoring")
    cues = []
    for item, case in zip(items, expected, strict=True):
        if item.get("text") != case["text"]:
            raise ValueError("imported audio transcript differs from canonical text")
        path = workspace_path(root, item["path"])
        digest = _sha(path)
        if item.get("sha256") != digest:
            raise ValueError("imported WAV SHA-256 differs")
        cues.append({"id": case["id"], "text": case["text"], "path": str(path), "sha256": digest, **_measure(path)})
    return {"schema_version": 1, "status": "imported_measured", "mode": "imported", "cues": cues, "source_sha256": _sha(source), "review_status": "pending_human_listening"}


def prepare_voice(workspace: Path, plan: dict, generate: bool = False) -> dict:
    root = Path(workspace).resolve(strict=True)
    if plan.get("status") != "plan_ready":
        raise ValueError("complete the authoring plan before preparing voice")
    mode = plan["project"]["voice"]["mode"]
    if mode == "silent":
        return {"schema_version": 1, "status": "explicit_silent", "mode": "silent", "cues": [], "review_status": "not_applicable_silent"}
    if mode == "imported":
        return _imported(root, plan)
    provider_name = plan["project"]["voice"]["provider"]
    if provider_name not in {"qwen_mlx", "kokoro"}:
        raise ValueError("unsupported local voice provider")
    requested = plan["style"]["voice"]
    profile_name = requested["profile"]
    profiles = json.loads(data_path("speech/voice_profiles.json").read_text())
    if provider_name == "qwen_mlx":
        parameters = {k: v for k, v in requested.items() if k not in {"provider", "profile", "seed"}}
    else:
        parameters = profiles["profiles"][profile_name]["kokoro"]
    profiles["profiles"][profile_name][provider_name] = parameters
    lexicon = json.loads(data_path("speech/lexicon.json").read_text())
    cases = plan["voice_request"]["cases"]
    normalized = [plan_case(case, provider_name, lexicon) for case in cases]
    sources = {str(p.relative_to(Path(__file__).parent)): _sha(p) for p in [Path(__file__), Path(__file__).with_name("synthesis.py"), *sorted(Path(__file__).with_name("speech").glob("*.py"))]}
    request = {"schema_version": 1, "provider": provider_name, "profile": profile_name, "parameters": parameters, "seed": requested["seed"], "cases": cases, "normalization": normalized, "lexicon_sha256": _sha(data_path("speech/lexicon.json")), "source_sha256": plan["source_sha256"], "implementation": sources, "review_status": "pending_human_listening"}
    runtime = runtime_for(plan["project"])
    if generate:
        request["generation_runtime"] = _generation_identity(runtime, provider_name)
    identity = hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    directory = workspace_path(root, f"build/voice/{identity[:16]}")
    path = directory / "request.json"
    if path.exists() and json.loads(path.read_text()) != request:
        raise ValueError("voice request collision; existing evidence retained")
    _write(path, request)
    _write(directory / "cases.json", {"schema_version": 1, "cases": cases})
    _write(directory / "profiles.json", profiles)
    if not generate:
        return {"schema_version": 1, "status": "voice_planned", "request": str(path), "request_sha256": _sha(path), "cues": [], "normalized": normalized, "model_required": False, "review_status": "pending_human_listening"}
    python = runtime.get("speech_python")
    model = runtime.get("model_path")
    if not python or (provider_name == "qwen_mlx" and not model):
        raise RuntimeError("speech runtime/model not configured; run explicit setup or select imported/silent voice")
    generated = directory / "generated"
    manifest_path = generated / "manifest.json"
    if not manifest_path.exists():
        # Bind only the pure-Python package, without importing the core environment's
        # Python-3.13 binary dependencies into the isolated Python-3.12 voice worker.
        package, binding = _worker_bootstrap()
        args = [str(python), "-I", "-c", binding + "from mathcoffee.synthesis import main; main()", package, "--provider", provider_name, "--profile", profile_name, "--cases", str(directory / "cases.json"), "--profiles", str(directory / "profiles.json"), "--lexicon", str(data_path("speech/lexicon.json")), "--all", "--seed", str(requested["seed"]), "--output-dir", str(generated)]
        if model:
            args.extend(["--model-path", str(model)])
        env = os.environ.copy()
        env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_IMPLICIT_TOKEN="1", PYTHONDONTWRITEBYTECODE="1")
        subprocess.run(args, env=env, check=True, stdout=sys.stderr)
        if _generation_identity(runtime, provider_name) != request["generation_runtime"]:
            raise ValueError("model/runtime changed during synthesis; retained output is not accepted")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("status") != "generated_signal_checked":
        raise ValueError("incomplete voice generation retained; choose a new request or inspect its manifest")
    if manifest.get("parameters") != parameters or manifest.get("seed") != requested["seed"]:
        raise ValueError("voice manifest parameters differ from frozen request")
    if [c["id"] for c in manifest["cases"]] != [c["id"] for c in cases]:
        raise ValueError("voice generation cue sequence differs")
    cues = []
    for item, case in zip(manifest["cases"], cases, strict=True):
        audio = Path(item["audio"]["path"]).resolve(strict=True)
        if not audio.is_relative_to(directory) or item["subtitle_text"] != case["text"] or _sha(audio) != item["audio"]["sha256"]:
            raise ValueError("stale or escaped generated voice cue")
        measured = _measure(audio)
        cues.append({"id": case["id"], "text": case["text"], "path": str(audio), "sha256": _sha(audio), **measured})
    result = {"schema_version": 1, "status": "generated_measured", "identity": identity, "mode": "synthesize", "cues": cues, "request_sha256": _sha(path), "manifest_sha256": _sha(manifest_path), "runtime": manifest["runtime"], "review_status": "pending_human_listening"}
    _write(directory / "index.json", result)
    return result

"""Local, resumable Manim → Remotion production from a single authoring source.

All generated code, PCM, clips and receipts live in the explicitly selected
workspace. A cache entry is reusable only with matching input and output hashes.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                      separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def file_hash(path: str | Path) -> str:
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def read(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".new")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def workspace_file(workspace: Path, value: str | Path, *, exists=True) -> Path:
    path = Path(value)
    path = (workspace / path if not path.is_absolute() else path).resolve(strict=exists)
    if not path.is_relative_to(workspace):
        raise ValueError("project inputs and outputs must remain inside the user workspace")
    if exists and not path.is_file():
        raise ValueError("project input must be a regular file")
    return path


def implementation_sources() -> dict[str, str]:
    package = Path(__file__).parent
    return {str(path.relative_to(package)): file_hash(path) for path in sorted(package.rglob("*.py"))}


def resolve_visual(cue: dict, states: dict) -> dict:
    """One pure-data interpretation for scheduling and mathematical renderers."""
    visual = cue.get("visual") or {}
    if isinstance(visual, str):
        visual = {"kind": visual}
    if not isinstance(visual, dict):
        raise ValueError("visual must be an object")
    result = dict(visual)
    reference = result.get("state_ref", cue.get("state_ref"))
    if reference is not None:
        if reference not in states or not isinstance(states[reference], dict):
            raise ValueError("visual state_ref must identify an object in math_states")
        result = {**states[reference], **result}
    result.setdefault("kind", "formula" if cue.get("formula") else "text")
    if "text" not in result:
        result["text"] = cue.get("formula") or cue.get("screen_text", "")
    return result


def source_identity(plan: dict, voice_index: dict) -> str:
    """The full build changes on authoring/style/PCM/code changes, never on time."""
    code = implementation_sources()
    voice = [{key: cue.get(key) for key in ("id", "sha256", "sample_rate", "samples",
                                          "active_start_sample", "active_end_sample")}
             for cue in voice_index.get("cues", [])]
    custom = {}
    for scene in plan["authoring"]["scenes"]:
        value = scene.get("scene_module", plan["project"].get("scene_module"))
        if value:
            root = Path(plan["workspace"]).resolve(strict=True)
            path = workspace_file(root, value)
            custom[str(path)] = file_hash(path)
    return digest({"authoring": plan["authoring"], "style": plan["style"],
                   "sources": plan.get("source_sha256", {}), "voice": voice,
                   "voice_mode": voice_index.get("mode", plan["project"].get("voice", {}).get("mode")),
                   "voice_identity": voice_index.get("identity", voice_index.get("synthesis_identity_sha256")),
                   "music": plan["project"].get("music", {}), "code": code,
                   "runtime": plan.get("runtime_fingerprint", {}), "custom_sources": custom})


def runtime_fingerprint(project: dict) -> dict:
    runtime = project.get("runtime", {})
    engine = runtime.get("remotion_root")
    sources = {}
    if engine:
        directory = Path(engine).resolve(strict=True)
        files = [directory / name for name in ("package.json", "package-lock.json", "tsconfig.json")]
        files += list(directory.glob("render*.mjs"))
        files += list((directory / "src").glob("*.ts")) + list((directory / "src").glob("*.tsx"))
        sources = {str(path.relative_to(directory)): file_hash(path) for path in sorted(files) if path.is_file()}
    python = str(runtime.get("render_python") or sys.executable)
    command = [python, "-c", "import json,manim,av,platform; print(json.dumps({'python':platform.python_version(),'manim':manim.__version__,'av':av.__version__}))"]
    versions = json.loads(subprocess.run(command, check=True, capture_output=True, text=True).stdout)
    node = runtime.get("node") or shutil.which("node")
    node_version = subprocess.run([str(node), "--version"], check=True, capture_output=True, text=True).stdout.strip() if node else None
    browser = runtime.get("browser_executable")
    return {"render_python": python, "versions": versions, "node": node_version,
            "engine_sources": sources, "browser_sha256": file_hash(browser) if browser else None}


def _positive_number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite positive number")
    return float(value)


def measured_schedule(plan: dict, voice_index: dict, quality="draft") -> dict:
    """Keep full PCM, measure sentence windows, and quantize picture slots only."""
    if quality not in {"draft", "final"}:
        raise ValueError("quality must be draft or final")
    authoring, style = plan["authoring"], plan["style"]
    render = style["render"]["draft"] if quality == "draft" else style["render"]
    fps, width, height = (int(render[name]) for name in ("fps", "width", "height"))
    if 48000 % fps:
        raise ValueError("production fps must divide the 48kHz sample clock exactly")
    all_ids = [cue["id"] for scene in authoring["scenes"] for cue in scene["sentences"]]
    voice_cues = voice_index.get("cues", [])
    ids = [cue["id"] for cue in voice_cues]
    silent = voice_index.get("mode") == "silent" or plan["project"].get("voice", {}).get("mode") == "silent"
    if not silent and ids != all_ids:
        raise ValueError("voice index must preserve the complete authoring cue sequence")
    if len(ids) != len(set(ids)):
        raise ValueError("voice index cue IDs must be unique")
    audio = {cue["id"]: cue for cue in voice_cues}
    scenes, cursor = [], 0
    for scene in authoring["scenes"]:
        sentences, local = [], 0
        for cue in scene["sentences"]:
            duration = float(cue.get("duration_seconds", 0))
            if duration < 0 or not math.isfinite(duration):
                raise ValueError("sentence duration must be finite and nonnegative")
            measured = audio.get(cue["id"])
            if measured:
                rate = _positive_number(measured["sample_rate"], "voice sample rate")
                samples = measured["samples"]
                first, last = measured["active_start_sample"], measured["active_end_sample"]
                if (any(type(v) is not int for v in (samples, first, last))
                        or not 0 <= first < last <= samples):
                    raise ValueError("voice activity must lie inside the complete decoded PCM")
                full_seconds = samples / rate
                duration = max(duration, full_seconds + style["pacing"]["read_hold_seconds"])
            else:
                if not silent:
                    raise ValueError("missing measured audio; no estimated speech timing is allowed")
                duration = max(duration, style["pacing"]["read_hold_seconds"], 1.0)
            visual = resolve_visual(cue, authoring.get("math_states", {}))
            if cue.get("formula") or visual["kind"] == "formula":
                duration = max(duration, style["pacing"]["formula_min_seconds"])
            if visual["kind"] in {"summary", "references"}:
                duration = max(duration, style["pacing"]["conclusion_min_seconds"])
            frames = max(1, math.ceil(duration * fps - 1e-9))
            record = {**copy.deepcopy(cue), "caption": cue["text"],
                      "slot": {"start_frame": local, "duration_frames": frames},
                      "start_frame": cursor + local, "end_frame": cursor + local + frames}
            if measured:
                record["audio"] = dict(measured)
                record["active_start_seconds"] = (cursor + local) / fps + first / rate
                record["active_end_seconds"] = (cursor + local) / fps + last / rate
            sentences.append(record)
            local += frames
        scenes.append({**copy.deepcopy(scene), "sentences": sentences,
                       "start_frame": cursor, "duration_frames": local})
        cursor += local
    if not cursor:
        raise ValueError("cannot render an empty authoring source")
    return {"schema_version": 1, "episode": authoring.get("episode", "project"),
            "width": width, "height": height, "fps": fps, "duration_frames": cursor,
            "scenes": scenes, "audio_timing": "silent picture slots" if silent else "measured complete PCM; activity windows retained in seconds",
            "voice_mode": "silent" if silent else voice_index.get("mode", "synthesize")}


def scene_identity(scene: dict, plan: dict, schedule: dict) -> str:
    local = copy.deepcopy(scene)
    local.pop("start_frame", None)
    for cue in local["sentences"]:
        for field in ("start_frame", "end_frame", "active_start_seconds", "active_end_seconds"):
            cue.pop(field, None)
        if "audio" in cue:
            cue["audio"].pop("path", None)
    refs, action_refs = set(), set()
    for cue in scene["sentences"]:
        visual = cue.get("visual", {})
        ref = visual.get("state_ref", cue.get("state_ref")) if isinstance(visual, dict) else cue.get("state_ref")
        if ref:
            refs.add(ref)
        action_refs.update(cue.get("action_refs", []))
    actions = [item for item in plan["authoring"].get("actions", []) if item["id"] in action_refs]
    refs.update(item["state_ref"] for item in actions if item.get("state_ref"))
    states = plan["authoring"].get("math_states", {})
    state_inputs = {ref: states[ref] for ref in sorted(refs)}
    return digest({"scene": local, "states": state_inputs, "style": plan["style"],
                   "geometry": {key: schedule[key] for key in ("width", "height", "fps")},
                   "components": file_hash(Path(__file__).with_name("components.py")),
                   "pipeline": file_hash(Path(__file__)),
                   "actions": actions,
                   "runtime": plan.get("runtime_fingerprint", {})})


def receipt_valid(receipt: dict, identity: str) -> bool:
    if receipt.get("identity") != identity or receipt.get("status") != "PASS":
        return False
    for output in receipt.get("outputs", []):
        path = Path(output["path"])
        if not path.is_file() or path.is_symlink() or file_hash(path) != output["sha256"]:
            return False
    return bool(receipt.get("outputs"))


def _output(path: Path) -> dict:
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": file_hash(path)}


def _attempt(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for number in range(1, 10000):
        directory = root / f"attempt-{number:04d}"
        try:
            directory.mkdir()
            return directory
        except FileExistsError:
            pass
    raise ValueError("too many retained attempts; choose another workspace")


def _run(command: list[str], directory: Path, name: str, *, env=None) -> dict:
    started = time.monotonic()
    log = directory / f"{name}.log"
    with log.open("w") as stream:
        result = subprocess.run(command, cwd=directory, env=env, stdout=stream,
                                stderr=subprocess.STDOUT, check=False)
    record = {"command": command, "log": str(log), "exit_code": result.returncode,
              "elapsed_seconds": time.monotonic() - started}
    if result.returncode:
        raise RuntimeError(f"{name} failed ({result.returncode}); retained log: {log}")
    return record


def _python_bootstrap() -> str:
    """Bind only this pure-Python package, without adding a different venv's site-packages."""
    package = str(Path(__file__).parent)
    return ("import importlib.util,sys\n"
            f"_pkg={package!r}\n"
            "_spec=importlib.util.spec_from_file_location('mathcoffee',_pkg+'/__init__.py',submodule_search_locations=[_pkg])\n"
            "_module=importlib.util.module_from_spec(_spec)\n"
            "sys.modules['mathcoffee']=_module\n"
            "_spec.loader.exec_module(_module)\n")


def _custom_scene(workspace: Path, scene: dict, project: dict) -> tuple[Path | None, str]:
    value = scene.get("scene_module", project.get("scene_module"))
    if value is None:
        return None, "ProjectScene"
    module = workspace_file(workspace, value)
    if module.suffix != ".py":
        raise ValueError("custom scene_module must be a Python file inside the workspace")
    name = scene.get("scene_class", "ProjectScene")
    if not isinstance(name, str) or not name.isidentifier():
        raise ValueError("custom scene_class must be a Python identifier")
    return module, name


def _render_scene(workspace: Path, scene: dict, plan: dict, schedule: dict,
                  quality: str, resume: bool) -> dict:
    custom, name = _custom_scene(workspace, scene, plan["project"])
    component_before = file_hash(Path(__file__).with_name("components.py"))
    custom_before = file_hash(custom) if custom else None
    identity = digest({"data": scene_identity(scene, plan, schedule),
                       "custom": file_hash(custom) if custom else None,
                       "python": plan["project"].get("runtime", {}).get("render_python") or sys.executable})
    base = workspace / "build" / "stages" / "manim" / identity / quality
    receipt_path = base / "receipt.json"
    if resume and receipt_path.is_file():
        receipt = read(receipt_path)
        if receipt_valid(receipt, identity):
            return {**receipt, "reused": True}
    directory = _attempt(base)
    payload_path, bounds = directory / "scene.json", directory / "display.json"
    payload = {"style": plan["style"], "scene": scene,
               "math_states": plan["authoring"].get("math_states", {}),
               "actions": plan["authoring"].get("actions", []),
               "fps": schedule["fps"], "duration_frames": scene["duration_frames"],
               "receipt": str(bounds)}
    write(payload_path, payload)
    portrait = schedule["height"] > schedule["width"]
    frame_height = 128 / 9 if portrait else 8
    source = _python_bootstrap() + "from manim import config\n"
    source += f"config.frame_height={frame_height!r}\nconfig.frame_width={frame_height * schedule['width'] / schedule['height']!r}\n"
    if custom:
        source += (f"_scene_spec=importlib.util.spec_from_file_location('user_scene',{str(custom)!r})\n"
                   "_scene_module=importlib.util.module_from_spec(_scene_spec)\n"
                   "_scene_spec.loader.exec_module(_scene_module)\n"
                   f"_Scene=getattr(_scene_module,{name!r})\n")
    else:
        source += "from mathcoffee.components import ProjectScene as _Scene\n"
    source += "class MathCoffeeScene(_Scene):\n    pass\n"
    generated = directory / "scene.py"
    generated.write_text(source)
    config_path = directory / "manim.cfg"
    config_path.write_text("[CLI]\nrenderer = cairo\ndisable_caching = True\nprogress_bar = none\n")
    python = plan["project"].get("runtime", {}).get("render_python") or sys.executable
    command = [str(python), "-m", "manim", "--config_file", str(config_path),
               "--media_dir", str(directory / "media"), "--format", "mp4",
               "-r", f"{schedule['width']},{schedule['height']}",
               "--fps", str(schedule["fps"]), "-o", "scene.mp4", str(generated), "MathCoffeeScene"]
    environment = os.environ.copy()
    environment.update(MATHCOFFEE_SCENE_INPUT=str(payload_path), PYTHONDONTWRITEBYTECODE="1")
    execution = _run(command, directory, "manim", env=environment)
    if file_hash(Path(__file__).with_name("components.py")) != component_before or (custom and file_hash(custom) != custom_before):
        raise ValueError("scene implementation changed during rendering")
    candidates = list((directory / "media" / "videos").rglob("scene.mp4"))
    if len(candidates) != 1 or not bounds.is_file():
        raise RuntimeError("Manim did not produce one clip and a measured display receipt")
    clip = candidates[0]
    from .renderer_contract import probe_media
    media = probe_media(clip)
    video = next(stream for stream in media["streams"] if stream["codec_type"] == "video")
    expected = (schedule["width"], schedule["height"], f"{schedule['fps']}/1", scene["duration_frames"])
    actual = (video["width"], video["height"], video["avg_frame_rate"], int(video["nb_frames"]))
    if actual != expected:
        raise ValueError(f"Manim clip differs from measured schedule: expected {expected}, got {actual}")
    receipt = {"schema_version": 1, "status": "PASS", "identity": identity,
               "stage": "manim", "scene_id": scene["id"], "reused": False,
               "clip": str(clip), "display_receipt": str(bounds),
               "renderer_source": {"path": str(generated), "sha256": file_hash(generated)},
               "custom_source": {"path": str(custom), "sha256": custom_before} if custom else None,
               "execution": execution, "outputs": [_output(clip), _output(bounds)],
               "media": media}
    write(receipt_path, receipt)
    return receipt


def _decode_pcm(path: Path) -> tuple:
    import numpy as np
    command = ["ffmpeg", "-v", "error", "-nostdin", "-i", str(path),
               "-map", "0:a:0", "-ar", "48000", "-ac", "2", "-f", "f32le", "pipe:1"]
    result = subprocess.run(command, check=True, capture_output=True)
    wave = np.frombuffer(result.stdout, dtype="<f4").reshape(-1, 2).copy()
    if not len(wave) or not np.isfinite(wave).all():
        raise ValueError("decoded audio must be finite and nonempty")
    return wave, command


def _mix(workspace: Path, plan: dict, schedule: dict, directory: Path) -> tuple[dict | None, dict]:
    import numpy as np
    from .music_library import generate_track, load_catalog, mix_narration, select_track
    from .resources import data_path
    samples_per_frame = 48000 // schedule["fps"]
    samples = schedule["duration_frames"] * samples_per_frame
    voice = np.zeros((samples, 2), dtype=np.float32)
    activities, inputs = [], []
    for scene in schedule["scenes"]:
        for cue in scene["sentences"]:
            if "audio" not in cue:
                continue
            record = cue["audio"]
            path = workspace_file(workspace, record["path"])
            if file_hash(path) != record["sha256"]:
                raise ValueError(f"voice source changed before mixing: {cue['id']}")
            wave, command = _decode_pcm(path)
            expected = round(record["samples"] * 48000 / record["sample_rate"])
            if abs(len(wave) - expected) > 1:
                raise ValueError("explicit resampling changed complete PCM duration")
            start = cue["start_frame"] * samples_per_frame
            if start + len(wave) > samples:
                raise ValueError("full narration does not fit the measured picture schedule")
            voice[start:start + len(wave)] += wave
            activities.append((cue["active_start_seconds"], cue["active_end_seconds"]))
            inputs.append({"id": cue["id"], "path": str(path), "sha256": record["sha256"],
                           "sample_start": start, "normalized_samples": len(wave), "command": command})
    music_config = {**plan["style"].get("music", {}), **plan["project"].get("music", {})}
    music = np.zeros_like(voice)
    selection = None
    if music_config.get("enabled", False):
        catalog = load_catalog(data_path("audio/music_catalog.json"))
        selection = select_track(catalog, music_config.get("theme", "exploration"),
                                 music_config.get("mood", "curious"),
                                 int(music_config.get("seed", 42)),
                                 section=music_config.get("section"))
        music = generate_track(selection, samples / 48000, seed=int(music_config.get("seed", 42)))
    if not inputs and selection is None:
        return None, {"mode": "explicit_silent", "samples": samples, "inputs": []}
    mixed, report = mix_narration(music, voice, 48000, activity_intervals=activities,
                                  duck_db=music_config.get("duck_db", 14),
                                  music_gain_db=music_config.get("gain_db", 0),
                                  peak_ceiling_dbfs=-1.5)
    pcm = directory / "premix.f32"
    with pcm.open("xb") as stream:
        stream.write(np.asarray(mixed, dtype="<f4").tobytes())
    wav = directory / "premix.wav"
    command = ["ffmpeg", "-v", "error", "-nostdin", "-n", "-f", "f32le", "-ar", "48000",
               "-ac", "2", "-i", str(pcm), "-c:a", "pcm_s24le", str(wav)]
    _run(command, directory, "premix")
    report.update(inputs=inputs, selection=selection, command=command,
                  policy="full PCM preserved; explicit sample-rate conversion; no retiming")
    return {"path": str(wav), "sha256": file_hash(wav), "sample_rate": 48000,
            "samples": samples}, report


def _caption_pages(cue: dict, fps: int, portrait: bool, style: dict | None = None) -> list[dict]:
    if "active_start_seconds" not in cue:
        return []
    text = cue["text"]
    if style:
        rectangle = style["layout"]["caption_rect"]
        size = style["layout"]["font_sizes"]["caption"]
        per_line = math.floor(rectangle[2] / size)
        lines = math.floor(rectangle[3] / (size * 1.25))
        if min(per_line, lines) < 1:
            raise ValueError("caption rectangle cannot fit one configured text line")
        limit = per_line * lines
    else:
        per_line, limit = (18, 36) if portrait else (39, 78)
    pages = [text[i:i + limit] for i in range(0, len(text), limit)]
    first = math.floor(cue["active_start_seconds"] * fps)
    last = math.ceil(cue["active_end_seconds"] * fps)
    if last - first < len(pages):
        raise ValueError("caption content exceeds the available measured activity window")
    result = []
    consumed = 0
    for number, page in enumerate(pages):
        start = first + round((last - first) * consumed / len(text))
        consumed += len(page)
        end = first + round((last - first) * consumed / len(text))
        page = "\n".join(page[i:i + per_line] for i in range(0, len(page), per_line))
        result.append({"id": f"{cue['id']}_caption_{number + 1}", "text": page,
                       "start_frame": start, "end_frame": end})
    return result


def _renderer_props(plan: dict, schedule: dict, clips: list[dict], premix: dict | None,
                    public: Path) -> dict:
    public.mkdir()
    timeline = {key: schedule[key] for key in ("schema_version", "width", "height", "fps", "duration_frames")}
    timeline.update(clips=[], captions=[], audio=None, qa={"anchor_frames": []}, style=plan["style"])
    for scene, clip in zip(schedule["scenes"], clips, strict=True):
        name = f"{scene['id']}.mp4"
        shutil.copyfile(clip["clip"], public / name)
        timeline["clips"].append({"id": scene["id"], "renderer": "manim", "file": name,
                                   "sha256": file_hash(public / name), "start_frame": scene["start_frame"],
                                   "source_in_frame": 0, "duration_frames": scene["duration_frames"]})
    if premix:
        shutil.copyfile(premix["path"], public / "premix.wav")
        timeline["audio"] = {key: premix[key] for key in ("sha256", "sample_rate", "samples")}
        timeline["audio"]["file"] = "premix.wav"
    portrait = schedule["height"] > schedule["width"]
    if plan["style"]["layout"]["caption_enabled"]:
        for scene in schedule["scenes"]:
            for cue in scene["sentences"]:
                timeline["captions"].extend(_caption_pages(cue, schedule["fps"], portrait, plan["style"]))
    if portrait:
        # Compatibility metadata only. Styled layouts use the complete supplied brand.
        brand = str(plan["project"].get("brand") or "")
        timeline["shorts"] = {"episode": "000", "brand": brand, "series": "",
                              "show_captions": plan["style"]["layout"]["caption_enabled"],
                              "scene_headers": [{"id": scene["id"], "title": scene["title"],
                                                  "start_frame": scene["start_frame"],
                                                  "end_frame": scene["start_frame"] + scene["duration_frames"]}
                                                 for scene in schedule["scenes"]]}
    # Full title text is not truncated for the configurable renderer.
    if not portrait:
        timeline["headers"] = [{"id": scene["id"], "title": scene["title"],
                                 "start_frame": scene["start_frame"],
                                 "end_frame": scene["start_frame"] + scene["duration_frames"]}
                                for scene in schedule["scenes"]]
    return timeline


def _render_composition(plan: dict, schedule: dict, props: Path, public: Path, directory: Path) -> dict:
    from .resources import data_path
    runtime = plan["project"].get("runtime", {})
    engine = Path(runtime.get("remotion_root") or data_path("engines/remotion")).resolve()
    # Rendering may write bundler caches: the installed package must remain read-only.
    package = Path(__file__).parent.resolve()
    if engine.is_relative_to(package):
        raise ValueError("Remotion must be prepared in the user runtime cache with mathcoffee setup")
    script = engine / ("render-shorts.mjs" if schedule["height"] > schedule["width"] else "render.mjs")
    node = runtime.get("node") or shutil.which("node")
    if not node or not script.is_file():
        raise ValueError("Remotion runtime is unavailable; run explicit setup first")
    output = directory / "film.mp4"
    command = [str(node), str(script), "--props", str(props), "--public-dir", str(public),
               "--output", str(output)]
    browser = runtime.get("browser_executable")
    if not browser or not Path(browser).is_file():
        raise ValueError("a prepared local browser_executable is required; rendering never downloads one")
    command += ["--browser-executable", str(browser)]
    if read(props)["audio"] is None:
        command.append("--no-audio")
    execution = _run(command, directory, "remotion")
    if not output.is_file() or not output.with_suffix(".mp4.render.json").is_file():
        raise RuntimeError("Remotion did not produce a film and render receipt")
    return {"path": str(output), "sha256": file_hash(output), "bytes": output.stat().st_size,
            "execution": execution, "render_receipt": str(output.with_suffix(".mp4.render.json"))}


def _pending_reviews(plan: dict) -> dict:
    return {name: "pending" for name in ("mathematics", "narrative", "listening", "style", "audience_understanding")}


def _final_gate(workspace: Path, identity: str) -> None:
    draft_path = workspace / "build" / identity[:16] / "draft" / "manifest.json"
    if not draft_path.is_file():
        raise ValueError("render a complete draft before the final master")
    draft = read(draft_path)
    if draft.get("identity") != identity or draft.get("technical_status") != "PASS":
        raise ValueError("the matching complete draft has not passed technical validation")
    review = workspace / "build" / identity[:16] / "reviews.json"
    if not review.is_file():
        raise ValueError(f"draft visual review is pending: record approved in {review}")
    record = read(review)
    if record.get("identity") != identity or record.get("draft_visual") != "approved":
        raise ValueError("final rendering requires an explicit visual review of this exact draft")
    if not record.get("reviewer") or not record.get("reviewed_output_sha256") == draft["output"]["sha256"]:
        raise ValueError("draft approval must identify the reviewer and the exact reviewed film")
    output = Path(draft["output"]["path"])
    if not output.is_file() or file_hash(output) != draft["output"]["sha256"]:
        raise ValueError("the reviewed draft film changed or is missing")


def build(workspace: str | Path, quality="draft", resume=False,
          voice_index: dict | None = None, plan: dict | None = None) -> dict:
    from .authoring import plan_project
    from .environment import runtime_for
    workspace = Path(workspace).resolve(strict=True)
    plan = plan_project(workspace) if plan is None else plan
    if plan.get("status") == "incomplete":
        raise ValueError("authoring is incomplete; finish the brief and visual content before rendering")
    plan = copy.deepcopy(plan)
    plan["project"]["runtime"] = runtime_for(plan["project"])
    plan["runtime_fingerprint"] = runtime_fingerprint(plan["project"])
    if voice_index is None:
        from .voice import prepare_voice
        voice_index = prepare_voice(workspace, plan, generate=True)
    schedule = measured_schedule(plan, voice_index, quality)
    identity = source_identity(plan, voice_index)
    root = workspace / "build" / identity[:16]
    if quality == "final":
        _final_gate(workspace, identity)
    destination = root / quality
    manifest_path = destination / "manifest.json"
    if resume and manifest_path.is_file():
        manifest = read(manifest_path)
        if receipt_valid(manifest, identity) and manifest.get("technical_status") == "PASS":
            return {**manifest, "reused": True}
    destination.mkdir(parents=True, exist_ok=True)
    directory = _attempt(destination)
    manifest = {"schema_version": 1, "identity": identity, "quality": quality,
                "status": "RUNNING", "technical_status": "pending", "workspace": str(workspace),
                "directory": str(directory), "plan": plan, "reviews": _pending_reviews(plan),
                "implementation_sources": implementation_sources(),
                "voice_index": copy.deepcopy(voice_index),
                "stages": [], "outputs": [], "reused": False}
    write(manifest_path, manifest)
    write(workspace / "build" / "latest.json", {"identity": identity, "quality": quality,
                                                 "manifest": str(manifest_path)})
    write(directory / "schedule.json", schedule)
    try:
        clips = []
        for scene in schedule["scenes"]:
            clips.append(_render_scene(workspace, scene, plan, schedule, quality, resume))
            manifest["stages"] = clips
            write(manifest_path, manifest)
        premix, mix_receipt = _mix(workspace, plan, schedule, directory)
        write(directory / "mix.json", mix_receipt)
        props = _renderer_props(plan, schedule, clips, premix, directory / "public")
        write(directory / "timeline.json", props)
        display = []
        sources = [{"path": str(Path(__file__).with_name("components.py")),
                    "sha256": file_hash(Path(__file__).with_name("components.py"))}]
        for scene, receipt in zip(schedule["scenes"], clips, strict=True):
            display += read(receipt["display_receipt"])["entries"]
            display.append({"id": f"{scene['id']}.heading", "scene_id": scene["id"], "kind": "heading",
                            "text": scene["title"], "cue_ids": [cue["id"] for cue in scene["sentences"]]})
            sources.append(receipt["renderer_source"])
            if receipt.get("custom_source"):
                sources.append(receipt["custom_source"])
            if plan["style"].get("brand", "").strip():
                display.append({"id": f"{scene['id']}.brand", "scene_id": scene["id"], "kind": "brand",
                                "text": plan["style"]["brand"], "cue_ids": []})
        engine = Path(plan["project"]["runtime"]["remotion_root"])
        for relative, source_hash in plan["runtime_fingerprint"]["engine_sources"].items():
            sources.append({"path": str(engine / relative), "sha256": source_hash})
        display_manifest = {"schema_version": 1, "episode": plan["authoring"].get("episode", "project"),
                            "coverage": {"scene_ids": [s["id"] for s in schedule["scenes"]], "declared_complete": True},
                            "authoring_sha256": plan["source_sha256"]["authoring"],
                            "entries": display, "renderer_sources": sources}
        write(directory / "audience_display_manifest.json", display_manifest)
        output = _render_composition(plan, schedule, directory / "timeline.json", directory / "public", directory)
        manifest.update(output=output, schedule=str(directory / "schedule.json"),
                        timeline=str(directory / "timeline.json"),
                        display_manifest=str(directory / "audience_display_manifest.json"),
                        premix=premix, mix=str(directory / "mix.json"), status="BUILT")
        # Re-read original source files after rendering, preventing stale-input success.
        current = plan_project(workspace)
        current["runtime_fingerprint"] = runtime_fingerprint(plan["project"])
        if source_identity(current, voice_index) != identity:
            raise ValueError("project inputs changed during rendering; this output is retained but stale")
        manifest["outputs"] = [_output(Path(output["path"])), _output(directory / "schedule.json"),
                               _output(directory / "timeline.json"), _output(directory / "audience_display_manifest.json")]
        manifest["outputs"] += [_output(path) for path in sorted((directory / "public").iterdir()) if path.is_file()]
        for clip in clips:
            manifest["outputs"] += clip["outputs"]
        manifest["outputs"].append(_output(directory / "mix.json"))
        manifest["outputs"].append(_output(Path(output["render_receipt"])))
        if premix:
            manifest["outputs"].extend([_output(Path(premix["path"])), _output(directory / "premix.f32")])
        write(manifest_path, manifest)
        from .verification import verify_build
        verification = verify_build(workspace, quality=quality, manifest_path=manifest_path)
        manifest.update(status="PASS", technical_status=verification["technical_status"],
                        verification=verification)
        write(manifest_path, manifest)
        if quality == "draft" and not (root / "reviews.json").exists():
            write(root / "reviews.json", {"identity": identity, "draft_visual": "pending",
                                           "reviewer": "", "reviewed_output_sha256": output["sha256"],
                                           "scope": "Record a real visual review before final rendering; automated checks cannot approve it."})
        return manifest
    except Exception as exc:
        manifest.update(status="FAILED", technical_status="FAIL", error={"type": type(exc).__name__, "message": str(exc)})
        write(manifest_path, manifest)
        raise


def status(workspace: str | Path) -> dict:
    workspace = Path(workspace).resolve(strict=True)
    latest = workspace / "build" / "latest.json"
    if not latest.is_file():
        return {"status": "not_built", "workspace": str(workspace)}
    pointer = read(latest)
    path = workspace_file(workspace, pointer["manifest"])
    manifest = read(path)
    freshness = source_freshness(workspace, manifest)
    return {"status": manifest["status"] if freshness["status"] == "fresh" else "STALE",
            "artifact_status": manifest["status"], "technical_status": manifest["technical_status"],
            "source_freshness": freshness,
            "quality": manifest["quality"], "identity": manifest["identity"],
            "manifest": str(path), "output": manifest.get("output"),
            "reviews": manifest.get("reviews"), "error": manifest.get("error")}


def source_freshness(workspace: str | Path, manifest: dict) -> dict:
    """Read small source/config snapshots only; do not scan model weights or rerender."""
    from .environment import runtime_for
    from .style import resolve_style
    workspace = Path(workspace).resolve(strict=True)
    changed, unknown = [], []
    try:
        project_path = workspace_file(workspace, "mathcoffee.json")
        project = read(project_path)
        expected = manifest["plan"]["source_sha256"]
        if file_hash(project_path) != expected.get("project"):
            changed.append("project_configuration")
        authoring = workspace_file(workspace, project["authoring"])
        if file_hash(authoring) != expected.get("authoring"):
            changed.append("authoring")
        style = resolve_style(project["preset"], project["style"], project["brand"])
        if style["provenance"]["style_sha256"] != expected.get("style"):
            changed.append("resolved_style")
        saved_sources = manifest.get("implementation_sources")
        if not isinstance(saved_sources, dict) or not saved_sources:
            unknown.append("implementation_snapshot_missing")
        elif implementation_sources() != saved_sources:
            changed.append("package_implementation")
        fingerprint = manifest["plan"].get("runtime_fingerprint", {})
        if "engine_sources" not in fingerprint:
            unknown.append("renderer_snapshot_missing")
        else:
            runtime = runtime_for(project)
            engine = runtime.get("remotion_root")
            saved_engine = fingerprint["engine_sources"]
            if saved_engine and not engine:
                changed.append("renderer_runtime_missing")
            elif engine:
                root = Path(engine).resolve(strict=True)
                for relative, expected_hash in saved_engine.items():
                    source = (root / relative).resolve(strict=True)
                    if not source.is_relative_to(root) or file_hash(source) != expected_hash:
                        changed.append("renderer_source:" + relative)
    except (OSError, ValueError, KeyError, TypeError) as error:
        changed.append("unreadable_source:" + type(error).__name__)
    return {"status": "stale" if changed else "unknown" if unknown else "fresh",
            "changed": changed, "unknown": unknown,
            "model_integrity": "not_rechecked_by_status", "voice_pcm_integrity": "not_rechecked_by_status",
            "scope": "project, authoring, resolved preset, package code and registered renderer sources"}

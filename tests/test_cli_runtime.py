"""CLI, managed setup and real PCM import boundaries without installing or synthesizing."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import math
import os
import struct
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mathcoffee import __version__, cli, environment, voice
from mathcoffee.authoring import plan_project
from mathcoffee.workspace import init_workspace, load_project


def save(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pcm(path: Path, *, rate=24000, channels=1, silent=False) -> None:
    """Independent PCM16 fixture with measurable leading/trailing silence."""
    path.parent.mkdir(parents=True, exist_ok=True)
    values = [0] * 240
    values += [
        0 if silent else round(9000 * math.sin(2 * math.pi * 440 * i / rate)) for i in range(2400)
    ]
    values += [0] * 480
    with wave.open(str(path), "wb") as stream:
        stream.setframerate(rate)
        stream.setnchannels(channels)
        stream.setsampwidth(2)
        stream.writeframes(b"".join(struct.pack("<h", x) * channels for x in values))


def authored() -> dict:
    return {
        "schema_version": 1,
        "episode": "geometry",
        "title": "两段长度怎样比较？",
        "math_states": {},
        "actions": [],
        "scenes": [
            {
                "id": "opening",
                "title": "先看两段长度",
                "sentences": [
                    {
                        "id": "opening_01",
                        "text": "第一段长二。",
                        "visual": {"kind": "text", "text": "2"},
                    },
                    {
                        "id": "opening_02",
                        "text": "第二段也长二。",
                        "visual": {"kind": "text", "text": "2"},
                    },
                ],
            }
        ],
    }


class RuntimeCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name).resolve()
        self.workspace = self.directory / "own project with spaces"
        self.data = self.directory / "managed-data"
        self.cache = self.directory / "managed-cache"
        settings = patch.dict(
            os.environ,
            {
                "MATHCOFFEE_DATA_HOME": str(self.data),
                "MATHCOFFEE_CACHE_HOME": str(self.cache),
            },
        )
        settings.start()
        self.addCleanup(settings.stop)
        init_workspace(self.workspace, title="两段长度怎样比较？")

    def plan(self):
        save(self.workspace / "authoring.json", authored())
        return plan_project(self.workspace)

    def configure_voice(self, mode, index=None):
        project = load_project(self.workspace)
        project["voice"].update(mode=mode, index=index)
        save(self.workspace / "mathcoffee.json", project)
        return plan_project(self.workspace)

    def invoke(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = cli.main(list(args))
        return code, json.loads(output.getvalue())


class PlanningAndCLITests(RuntimeCase):
    def test_empty_authoring_is_incomplete_with_distinct_cli_exit_code(self):
        code, result = self.invoke("plan", "--workspace", str(self.workspace), "--json")
        self.assertEqual(code, 3)
        self.assertEqual(result["status"], "incomplete")
        self.assertTrue(result["pending"])
        self.assertFalse(self.data.exists())
        self.assertFalse(self.cache.exists())

    def test_plan_and_voice_request_need_no_model_probe_or_worker(self):
        plan = self.plan()
        with (
            patch.object(voice, "_generation_identity", side_effect=AssertionError("model probe")),
            patch.object(
                voice.subprocess,
                "run",
                side_effect=AssertionError("worker invocation"),
            ),
            patch.dict("sys.modules", {"mlx": None, "mlx_audio": None, "manim": None}),
        ):
            prepared = voice.prepare_voice(self.workspace, plan, generate=False)
        self.assertEqual(prepared["status"], "voice_planned")
        self.assertFalse(prepared["model_required"])
        request = json.loads(Path(prepared["request"]).read_text())
        self.assertNotIn("generation_runtime", request)
        self.assertEqual([x["text"] for x in request["cases"]], ["第一段长二。", "第二段也长二。"])
        self.assertEqual(prepared["review_status"], "pending_human_listening")
        self.assertFalse(self.data.exists())
        self.assertFalse(self.cache.exists())

    def test_cli_voice_does_not_generate_without_explicit_option(self):
        self.plan()
        with patch.object(voice, "_generation_identity", side_effect=AssertionError("model probe")):
            code, result = self.invoke("voice", "--workspace", str(self.workspace))
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "voice_planned")

    def test_invalid_command_inputs_have_structured_failure(self):
        code, result = self.invoke("plan")
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("--workspace", result["message"])

    def test_final_cli_propagates_review_gate_and_has_no_force_switch(self):
        from mathcoffee import pipeline

        self.plan()
        with patch.object(
            pipeline, "build", side_effect=ValueError("draft visual review is pending")
        ) as build:
            with self.assertRaisesRegex(ValueError, "pending"):
                cli._render_local("render", str(self.workspace), "final")
        self.assertEqual(build.call_args.kwargs, {"quality": "final", "resume": False})
        with patch.object(
            cli, "_render_worker", side_effect=ValueError("draft visual review is pending")
        ):
            code, result = self.invoke("render", "--workspace", str(self.workspace))
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("pending", result["message"])
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            cli.main(["render", "--workspace", str(self.workspace), "--force"])
        self.assertEqual(raised.exception.code, 2)

    def test_actual_final_gate_binds_identity_reviewer_and_exact_draft_hash(self):
        from mathcoffee.pipeline import _final_gate

        identity = "a" * 64
        root = self.workspace / "build" / identity[:16]
        with self.assertRaisesRegex(ValueError, "complete draft"):
            _final_gate(self.workspace, identity)
        film = root / "draft/picture.mp4"
        film.parent.mkdir(parents=True)
        film.write_bytes(b"draft identity fixture; media decoding is tested separately")
        digest = sha(film)
        draft = {
            "identity": identity,
            "technical_status": "PASS",
            "output": {"path": str(film), "sha256": digest},
        }
        save(root / "draft/manifest.json", draft)
        with self.assertRaisesRegex(ValueError, "visual review"):
            _final_gate(self.workspace, identity)
        review = {
            "identity": identity,
            "draft_visual": "approved",
            "reviewer": "",
            "reviewed_output_sha256": digest,
        }
        save(root / "reviews.json", review)
        with self.assertRaisesRegex(ValueError, "reviewer"):
            _final_gate(self.workspace, identity)
        review.update(reviewer="fixture reviewer", reviewed_output_sha256="c" * 64)
        save(root / "reviews.json", review)
        with self.assertRaisesRegex(ValueError, "exact reviewed"):
            _final_gate(self.workspace, identity)
        review["reviewed_output_sha256"] = digest
        save(root / "reviews.json", review)
        _final_gate(self.workspace, identity)
        film.write_bytes(b"changed draft fixture")
        with self.assertRaisesRegex(ValueError, "changed or is missing"):
            _final_gate(self.workspace, identity)


class ImportedPCMSafetyTests(RuntimeCase):
    def imported(self, channels=1, silent=False):
        self.plan()
        cues = []
        for cue in authored()["scenes"][0]["sentences"]:
            file = self.workspace / "recordings" / f"{cue['id']}.wav"
            pcm(file, channels=channels, silent=silent)
            cues.append(
                {
                    "id": cue["id"],
                    "text": cue["text"],
                    "path": str(file.relative_to(self.workspace)),
                    "sha256": sha(file),
                }
            )
        save(self.workspace / "recordings/index.json", {"cues": cues})
        return self.configure_voice("imported", "recordings/index.json"), cues

    def test_mono_pcm_is_actually_measured_and_never_grants_listening_acceptance(self):
        plan, _ = self.imported()
        with patch.object(voice, "_generation_identity", side_effect=AssertionError("model")):
            result = voice.prepare_voice(self.workspace, plan)
        self.assertEqual(result["status"], "imported_measured")
        self.assertEqual(result["review_status"], "pending_human_listening")
        for cue in result["cues"]:
            self.assertEqual(
                (cue["sample_rate"], cue["samples"], cue["channels"]), (24000, 3120, 1)
            )
            self.assertLess(cue["active_start_sample"], cue["active_end_sample"])
            self.assertLessEqual(cue["active_end_sample"], 3120)
            self.assertEqual(cue["sha256"], sha(Path(cue["path"])))

    def test_ids_order_transcript_and_wav_hash_cannot_be_redeclared(self):
        plan, cues = self.imported()
        mutations = [
            list(reversed(cues)),
            [cues[0], cues[0]],
            [{**cues[0], "id": "unknown"}, cues[1]],
            [{**cues[0], "text": "少字。"}, cues[1]],
            [{**cues[0], "sha256": "0" * 64}, cues[1]],
        ]
        for candidate in mutations:
            save(self.workspace / "recordings/index.json", {"cues": candidate})
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                voice.prepare_voice(self.workspace, plan)

    def test_stereo_and_silent_inputs_are_rejected_after_actual_decode(self):
        for channels, silent in ((2, False), (1, True)):
            plan, _ = self.imported(channels=channels, silent=silent)
            with self.subTest(channels=channels, silent=silent), self.assertRaises(ValueError):
                voice.prepare_voice(self.workspace, plan)

    def test_truncated_pcm_header_is_rejected_as_invalid_input(self):
        file = self.workspace / "truncated.wav"
        pcm(file)
        file.write_bytes(file.read_bytes()[:-2000])
        with self.assertRaisesRegex(ValueError, "PCM|truncat|sample"):
            voice._measure(file)

    def test_imported_wav_path_cannot_escape_workspace_even_with_correct_hash(self):
        plan, cues = self.imported()
        outside = self.directory / "outside.wav"
        pcm(outside)
        cues[0].update(path="../outside.wav", sha256=sha(outside))
        save(self.workspace / "recordings/index.json", {"cues": cues})
        with self.assertRaisesRegex(ValueError, "relative"):
            voice.prepare_voice(self.workspace, plan)


class GenerationIdentityTests(RuntimeCase):
    def fake_worker(self, calls):
        def execute(command, **kwargs):
            self.assertIn("-I", command)
            self.assertEqual(kwargs["env"]["HF_HUB_OFFLINE"], "1")
            directory = Path(command[command.index("--output-dir") + 1])
            directory.mkdir()
            cases = json.loads(Path(command[command.index("--cases") + 1]).read_text())["cases"]
            profiles = json.loads(Path(command[command.index("--profiles") + 1]).read_text())
            profile = command[command.index("--profile") + 1]
            provider = command[command.index("--provider") + 1]
            cues = []
            for item in cases:
                file = directory / f"{item['id']}.wav"
                pcm(file)
                cues.append(
                    {
                        "id": item["id"],
                        "subtitle_text": item["text"],
                        "audio": {"path": str(file), "sha256": sha(file)},
                    }
                )
            save(
                directory / "manifest.json",
                {
                    "status": "generated_signal_checked",
                    "parameters": profiles["profiles"][profile][provider],
                    "seed": 42,
                    "cases": cues,
                    "runtime": {"versions": {"fixture": "1"}},
                },
            )
            calls.append(directory)
            return SimpleNamespace(returncode=0)

        return execute

    def test_runtime_change_creates_new_request_and_does_not_reuse_old_pcm(self):
        plan = self.plan()
        runtime = {"speech_python": "/fake/speech/python", "model_path": "/fake/model"}
        calls = []
        first_runtime = {"versions": {"mlx-audio": "0.5.7"}, "model": {"content_sha256": "a" * 64}}
        second_runtime = {"versions": {"mlx-audio": "0.5.8"}, "model": {"content_sha256": "a" * 64}}
        with (
            patch.object(voice, "runtime_for", return_value=runtime),
            patch.object(
                voice.subprocess,
                "run",
                side_effect=self.fake_worker(calls),
            ),
        ):
            with patch.object(voice, "_generation_identity", return_value=first_runtime):
                first = voice.prepare_voice(self.workspace, plan, generate=True)
                reused = voice.prepare_voice(self.workspace, plan, generate=True)
            with patch.object(voice, "_generation_identity", return_value=second_runtime):
                second = voice.prepare_voice(self.workspace, plan, generate=True)
        self.assertEqual(len(calls), 2)
        self.assertEqual(first["cues"][0]["path"], reused["cues"][0]["path"])
        self.assertNotEqual(first["cues"][0]["path"], second["cues"][0]["path"])
        self.assertNotEqual(first["request_sha256"], second["request_sha256"])

    def test_runtime_mutation_during_worker_retains_output_without_accepting_index(self):
        plan = self.plan()
        calls = []
        with (
            patch.object(
                voice,
                "runtime_for",
                return_value={"speech_python": "/fake/python", "model_path": "/fake/model"},
            ),
            patch.object(
                voice,
                "_generation_identity",
                side_effect=[{"version": "a"}, {"version": "b"}],
            ),
            patch.object(voice.subprocess, "run", side_effect=self.fake_worker(calls)),
        ):
            with self.assertRaisesRegex(ValueError, "changed during synthesis"):
                voice.prepare_voice(self.workspace, plan, generate=True)
        self.assertEqual(len(calls), 1)
        self.assertTrue((calls[0] / "manifest.json").is_file())
        self.assertFalse((calls[0].parent / "index.json").exists())


class DoctorAndSetupTests(RuntimeCase):
    def resources(self):
        root = self.directory / "bundled"
        engine = root / "engines/remotion"
        save(engine / "package.json", {"name": "fixture"})
        for name in ("toolchains/render/requirements.lock", "toolchains/speech/requirements.lock"):
            file = root / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text("# fixture lock\n")
        save(
            root / "speech/model_files.json", {"repo": "fixture", "revision": "a" * 40, "files": []}
        )
        return lambda relative: root / relative

    def test_setup_without_execute_has_no_managed_directories_or_subprocesses(self):
        with (
            patch.object(environment, "data_path", side_effect=self.resources()),
            patch.object(
                environment.subprocess,
                "run",
                side_effect=AssertionError("installation"),
            ),
        ):
            for component in ("render", "speech", "model"):
                result = environment.setup(component)
                self.assertEqual(result["status"], "setup_plan")
                self.assertFalse(result["executed"])
        self.assertFalse(self.data.exists())
        self.assertFalse(self.cache.exists())

    def test_doctor_rejects_wrong_manim_node_speech_and_remotion_versions(self):
        engine = self.directory / "engine"
        model = self.directory / "model"
        save(model / "config.json", {})
        browser = self.directory / "browser cache/chrome"
        browser.parent.mkdir()
        browser.write_text("browser fixture")
        browser.chmod(0o755)
        tex = {}
        for name in ("standalone.cls", "unicode-math.sty", "latinmodern-math.otf"):
            tex[name] = self.directory / name
            tex[name].write_text("TeX lookup fixture")
        runtime = {
            "render_python": "/fake/render/python",
            "speech_python": "/fake/speech/python",
            "remotion_root": str(engine),
            "model_path": str(model),
            "browser_executable": str(browser),
        }
        for mismatch in (None, "manim", "node", "speech", "remotion"):
            save(
                engine / "node_modules/remotion/package.json",
                {"version": "4.0.532" if mismatch == "remotion" else "4.0.531"},
            )

            def probe(command, mismatch=mismatch, **_kwargs):
                code = " ".join(command)
                if "list_fonts" in code:
                    detail = json.dumps(["Heiti SC"])
                elif command[-1] in tex:
                    detail = str(tex[command[-1]])
                elif "mlx-audio" in code:
                    detail = "0.6.0" if mismatch == "speech" else "0.5.7"
                elif "manim" in code:
                    detail = "0.20.2" if mismatch == "manim" else "0.20.1"
                else:
                    detail = "v25.0.0" if mismatch == "node" else "v24.21.0"
                return {"available": True, "detail": detail, "returncode": 0}

            with (
                self.subTest(mismatch=mismatch),
                patch.object(environment, "runtime_for", return_value=runtime),
                patch.object(
                    environment,
                    "_probe",
                    side_effect=probe,
                ),
                patch.object(
                    environment.shutil, "which", side_effect=lambda name, **_kwargs: f"/fake/bin/{name}"
                ),
                patch.object(
                    environment.platform,
                    "system",
                    return_value="Darwin",
                ),
                patch.object(environment.platform, "machine", return_value="arm64"),
            ):
                result = environment.doctor()
                if mismatch is None:
                    self.assertEqual(result["status"], "ready")
                else:
                    self.assertEqual(result["status"], "setup_required")
                    self.assertFalse(result["checks"][mismatch]["available"])
        self.assertFalse(self.data.exists())
        self.assertFalse(self.cache.exists())

    def test_doctor_reports_missing_browser_as_setup_required(self):
        with (
            patch.object(environment, "runtime_for", return_value={}),
            patch.object(
                environment,
                "_probe",
                return_value={"available": False, "detail": "fixture unavailable"},
            ),
            patch.object(environment.shutil, "which", return_value=None),
        ):
            result = environment.doctor()
        self.assertEqual(result["status"], "setup_required")
        self.assertFalse(result["checks"]["browser"]["available"])
        self.assertIsNone(result["checks"]["browser"]["executable"])
        self.assertTrue(result["planning_available"])
        self.assertFalse(self.data.exists())
        self.assertFalse(self.cache.exists())

    def test_core_profile_reports_missing_components_without_requiring_them(self):
        with (
            patch.object(environment, "runtime_for", return_value={}),
            patch.object(environment, "_probe", return_value={"available": False, "detail": "not installed"}),
            patch.object(environment.shutil, "which", return_value=None),
            patch.object(environment.platform, "system", return_value="Darwin"),
            patch.object(environment.platform, "machine", return_value="arm64"),
        ):
            code, result = self.invoke("doctor", "--profile", "core")
        self.assertEqual(code, 0)
        self.assertEqual(result["profile"], "core")
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["required_checks"], ["core", "platform"])
        self.assertEqual(result["missing_required"], [])
        self.assertFalse(result["checks"]["manim"]["available"])
        self.assertFalse(result["checks"]["model"]["available"])
        self.assertTrue(result["planning_available"])
        self.assertFalse(self.data.exists())
        self.assertFalse(self.cache.exists())

    def test_render_profile_accepts_imported_voice_without_speech_or_model(self):
        runtime = {"render_python": "/fake/render/python"}
        engine = self.directory / "engine"
        save(engine / "node_modules/remotion/package.json", {"version": "4.0.531"})
        runtime["remotion_root"] = str(engine)
        browser = self.directory / "browser"
        browser.write_text("browser fixture")
        runtime["browser_executable"] = str(browser)
        tex = {}
        for name in ("standalone.cls", "unicode-math.sty", "latinmodern-math.otf"):
            tex[name] = self.directory / name
            tex[name].write_text("TeX resource fixture")

        def probe(command, **_kwargs):
            if "list_fonts" in " ".join(command):
                detail = json.dumps(["PingFang SC"])
            elif command[-1] in tex:
                detail = str(tex[command[-1]])
            elif command[-1] == "--version":
                detail = "v24.21.0"
            else:
                detail = "0.20.1"
            return {"available": True, "detail": detail}

        with (
            patch.object(environment, "runtime_for", return_value=runtime),
            patch.object(environment, "_probe", side_effect=probe),
            patch.object(environment.shutil, "which", side_effect=lambda name, **_kwargs: f"/fake/bin/{name}"),
            patch.object(environment.platform, "system", return_value="Darwin"),
            patch.object(environment.platform, "machine", return_value="arm64"),
        ):
            result = environment.doctor(profile="render")
            full = environment.doctor()
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["checks"]["fonts"]["resolved"], "PingFang SC")
        self.assertTrue(result["checks"]["fonts"]["fallback_used"])
        self.assertTrue(result["checks"]["tex_resources"]["available"])
        self.assertNotIn("speech", result["required_checks"])
        self.assertEqual(full["status"], "setup_required")
        self.assertEqual(full["missing_required"], ["speech", "model"])

    def test_font_and_tex_resource_checks_fail_missing_defaults_without_compilation(self):
        from mathcoffee.style import resolve_style

        style = resolve_style("mathcoffee-shorts@1")
        child = environment.runtime_environment({})
        with patch.object(environment, "_probe", return_value={"available": True, "detail": "[]"}):
            fonts = environment._font_check("/fake/python", style, child)
        self.assertFalse(fonts["available"])
        self.assertIsNone(fonts["resolved"])
        calls = []

        def lookup(command, **_kwargs):
            calls.append(command)
            return {"available": True, "detail": str(self.directory / command[-1])}

        with patch.object(environment, "_probe", side_effect=lookup):
            tex = environment._tex_check("/fake/kpsewhich", style, child)
        self.assertFalse(tex["available"])
        self.assertEqual([c[1] for c in calls], ["standalone.cls", "unicode-math.sty", "latinmodern-math.otf"])
        self.assertTrue(all(c[0] == "/fake/kpsewhich" for c in calls))
        style["font"]["formula"] = "Custom Math Face"
        with patch.object(environment, "_probe", side_effect=lookup):
            custom = environment._tex_check("/fake/kpsewhich", style, child)
        self.assertEqual(custom["formula_font"]["status"], "not_verified")
        self.assertIn("custom math fonts", custom["formula_font"]["scope"])

    def test_render_worker_uses_registered_node_without_editing_the_shell_path(self):
        binary = self.directory / "node24 bin/node"
        binary.parent.mkdir()
        binary.write_text("node fixture")
        runtime = {"render_python": "/fake/render/python", "node": str(binary)}
        ambient = "/usr/bin:/bin"
        with (
            patch.dict(os.environ, {"PATH": ambient}),
            patch.object(environment, "runtime_for", return_value=runtime),
            patch.object(cli.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout='{"status":"PASS"}', stderr="")) as run,
        ):
            result = cli._render_worker(SimpleNamespace(command="preview", workspace=self.workspace))
            self.assertEqual(os.environ["PATH"], ambient)
        self.assertEqual(result["status"], "PASS")
        child_path = run.call_args.kwargs["env"]["PATH"].split(os.pathsep)
        self.assertEqual(child_path[0], str(binary.parent))
        for name in ("/Library/TeX/texbin", "/opt/homebrew/bin"):
            if Path(name).is_dir():
                self.assertIn(name, child_path)
        self.assertEqual(len(child_path), len(set(child_path)))

    def test_failed_managed_install_resumes_only_unfinished_commands(self):
        calls = []
        failed = False
        browser = self.cache / __version__ / "remotion/.remotion/chrome-headless-shell"
        node = self.directory / "registered node24/bin/node"
        node.parent.mkdir(parents=True)
        node.write_text("registered Node.js fixture")
        node.chmod(0o755)
        save(self.data / "runtime.json", {"node": str(node)})

        def execute(command, **kwargs):
            nonlocal failed
            calls.append(command)
            if command[1] == "--version":
                self.assertEqual(command[0], str(node))
                return SimpleNamespace(returncode=0, stdout="v24.21.0", stderr="")
            if command[1] == "venv":
                interpreter = Path(command[-1]) / "bin/python"
                interpreter.parent.mkdir(parents=True)
                interpreter.write_text("managed fixture interpreter")
            elif command[1:3] == ["pip", "sync"] and not failed:
                failed = True
                raise subprocess.CalledProcessError(1, command)
            elif Path(command[0]).name == "node" and command[1] == "-e":
                self.assertEqual(command[0], str(node))
                self.assertEqual(kwargs["env"]["PATH"].split(os.pathsep)[0], str(node.parent))
                self.assertIn("ensureBrowser", command[2])
                browser.parent.mkdir(parents=True)
                browser.write_text("prepared browser fixture")
                browser.chmod(0o755)
                return SimpleNamespace(returncode=0, stdout=json.dumps({"path": str(browser)}))
            return SimpleNamespace(returncode=0)

        with (
            patch.object(environment, "data_path", side_effect=self.resources()),
            patch.object(
                environment.subprocess,
                "run",
                side_effect=execute,
            ),
        ):
            with self.assertRaises(subprocess.CalledProcessError):
                environment.setup("render", execute=True)
            receipt_path = self.data / "runtimes" / __version__ / "render.setup.json"
            retained = json.loads(receipt_path.read_text())
            self.assertEqual(retained["completed_commands"], [0])
            self.assertIn(retained["status"], {"preparing", "failed"})
            result = environment.setup("render", execute=True)
        self.assertEqual(result["status"], "prepared")
        self.assertEqual(sum(command[1] == "venv" for command in calls), 1)
        self.assertEqual(sum(command[1:3] == ["pip", "sync"] for command in calls), 2)
        self.assertEqual(json.loads(receipt_path.read_text())["status"], "prepared")
        self.assertEqual(
            json.loads((self.data / "runtime.json").read_text())["render_python"],
            str(self.data / "runtimes" / __version__ / "render/bin/python"),
        )
        self.assertEqual(result["runtime"]["browser_executable"], str(browser))
        self.assertEqual(result["runtime"]["node"], result["selected_node"])
        self.assertTrue(Path(result["runtime"]["browser_executable"]).is_file())
        self.assertEqual(
            json.loads((self.data / "runtime.json").read_text())["browser_executable"], str(browser)
        )

    def test_render_setup_rejects_wrong_node_major_before_installing_dependencies(self):
        with (
            patch.object(environment, "data_path", side_effect=self.resources()),
            patch.object(environment, "_probe", return_value={"available": True, "detail": "v25.0.0"}),
            patch.object(environment.subprocess, "run", side_effect=AssertionError("unexpected dependency installation")),
        ):
            with self.assertRaisesRegex(RuntimeError, "Node.js 24 is required"):
                environment.setup("render", execute=True)
        self.assertFalse((self.data / "runtimes" / __version__ / "render/bin/python").exists())

    def test_retained_receipt_does_not_authorize_a_replaced_environment_symlink(self):
        managed = self.data / "runtimes" / __version__ / "speech"

        def fail_sync(command, **_kwargs):
            if command[1] == "venv":
                (managed / "bin").mkdir(parents=True)
                (managed / "bin/python").write_text("managed fixture")
                return SimpleNamespace(returncode=0)
            raise subprocess.CalledProcessError(1, command)

        with (
            patch.object(environment, "data_path", side_effect=self.resources()),
            patch.object(
                environment.subprocess,
                "run",
                side_effect=fail_sync,
            ),
        ):
            with self.assertRaises(subprocess.CalledProcessError):
                environment.setup("speech", execute=True)
        managed.rename(managed.with_name("retained-original-speech"))
        outside = self.directory / "user-environment"
        (outside / "bin").mkdir(parents=True)
        (outside / "bin/python").write_text("user interpreter retained")
        managed.symlink_to(outside, target_is_directory=True)
        with (
            patch.object(environment, "data_path", side_effect=self.resources()),
            patch.object(
                environment.subprocess,
                "run",
                side_effect=AssertionError("external environment mutation"),
            ),
        ):
            with self.assertRaises((ValueError, FileExistsError)):
                environment.setup("speech", execute=True)
        self.assertEqual((outside / "bin/python").read_text(), "user interpreter retained")

    def test_unmanaged_environment_and_cache_are_retained_untouched(self):
        fixtures = [
            self.data / "runtimes" / __version__ / "render/bin/python",
            self.cache / __version__ / "remotion/user-file.txt",
        ]
        for file in fixtures:
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(b"user owned fixture")
        with (
            patch.object(environment, "data_path", side_effect=self.resources()),
            patch.object(
                environment.subprocess,
                "run",
                side_effect=AssertionError("unmanaged install"),
            ),
        ):
            with self.assertRaisesRegex(FileExistsError, "not owned"):
                environment.setup("render", execute=True)
        for file in fixtures:
            self.assertEqual(file.read_bytes(), b"user owned fixture")
        self.assertFalse((self.data / "runtime.json").exists())


if __name__ == "__main__":
    unittest.main()

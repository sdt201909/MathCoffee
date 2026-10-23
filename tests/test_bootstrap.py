"""Fresh-machine setup plans, ownership, and resume without real installations."""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("mathcoffee_bootstrap", ROOT / "bin/bootstrap.py")
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)


def content_hashes(root):
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
    }


class FakeMachine:
    def __init__(self, test):
        self.test = test
        self.calls = []
        self.installed = {"uv"}
        self.versions = {}
        self.fail_component = None
        self.fail_cask = False
        self.clt_available = True
        self.brew_prefix = str(test.brew)
        self.command_line_tools = test.directory / "Command Line Tools"
        self.command_line_tools.mkdir()

    def run(self, command, *, env, capture=False):
        self.calls.append({"command": command, "env": env.copy(), "capture": capture})
        stdout, stderr, code = "", "", 0
        if command[1:] == ["--prefix"]:
            stdout = self.brew_prefix
        elif command[:2] == ["xcode-select", "-p"]:
            stdout = str(self.command_line_tools)
            code = 0 if self.clt_available else 1
        elif command[1:4] == ["list", "--formula", "--versions"]:
            name = command[-1]
            stdout = name + " 1.0" if name in self.installed else ""
            code = 0 if stdout else 1
        elif command[1:3] == ["install", "--formula"]:
            self.installed.update(command[3:])
        elif command[1:3] == ["install", "--cask"]:
            code = 1 if self.fail_cask else 0
        elif command[1] == "venv":
            core = Path(command[-1])
            (core / "bin").mkdir(parents=True)
            (core / "bin/python").write_text("fixture interpreter")
        elif command[1:3] == ["pip", "install"]:
            core = Path(command[command.index("--python") + 1]).parents[1]
            wheel = Path(command[-1])
            info = bootstrap.wheel_info(wheel)
            self.versions[str(core)] = info["version"]
            site = core / "lib/python3.13/site-packages"
            with zipfile.ZipFile(wheel) as archive:
                for name in archive.namelist():
                    if name.startswith("mathcoffee/"):
                        target = site / name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(archive.read(name))
            (core / "bin/mathcoffee").write_text("fixture console script")
        elif "-c" in command:
            core = Path(command[0]).parents[1]
            stdout = json.dumps(
                {
                    "version": self.versions[str(core)],
                    "python": [3, 13],
                    "package": str(core / "lib/python3.13/site-packages/mathcoffee"),
                }
            )
        elif "setup" in command:
            component = command[command.index("--component") + 1]
            code = 1 if component == self.fail_component else 0
            stdout = json.dumps({"status": "prepared" if not code else "blocked"})
        elif "doctor" in command:
            stdout = json.dumps({"status": "ready", "profile": command[-1]})
        else:
            raise AssertionError(command)
        return subprocess.CompletedProcess(command, code, stdout, stderr)

    def commands(self):
        return [call["command"] for call in self.calls]


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mathcoffee fresh mac ")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name).resolve()
        self.distribution = self.directory / "read only release"
        self.distribution.mkdir()
        self.data = self.directory / "external data"
        self.cache = self.directory / "external cache"
        self.brew = self.directory / "Homebrew"
        self.wheel = self.write_wheel()
        self.version = bootstrap.wheel_info(self.wheel)["version"]
        self.machine = FakeMachine(self)
        environment = {
            "MATHCOFFEE_DATA_HOME": str(self.data),
            "MATHCOFFEE_CACHE_HOME": str(self.cache),
        }
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, environment).start()
        patch.object(bootstrap, "BREW_PREFIX", self.brew).start()
        patch.object(bootstrap.platform, "system", return_value="Darwin").start()
        patch.object(bootstrap.platform, "machine", return_value="arm64").start()
        patch.object(
            bootstrap.shutil,
            "which",
            side_effect=lambda name: str(self.brew / "bin/brew") if name == "brew" else None,
        ).start()
        patch.object(bootstrap, "tex_available", return_value=False).start()
        patch.object(bootstrap, "run", side_effect=self.machine.run).start()

    def write_wheel(self, version="0.2.0a2", suffix=""):
        path = self.distribution / "wheels" / f"mathcoffee-{version}-py3-none-any.whl"
        path.parent.mkdir(exist_ok=True)
        with zipfile.ZipFile(path, "w") as archive:
            prefix = f"mathcoffee-{version}.dist-info/"
            archive.writestr(
                prefix + "METADATA",
                f"Metadata-Version: 2.3\nName: MathCoffee\nVersion: {version}\n",
            )
            archive.writestr(
                prefix + "entry_points.txt", "[console_scripts]\nmathcoffee = mathcoffee.cli:main\n"
            )
            archive.writestr("mathcoffee/__init__.py", f"__version__ = '{version}'\n{suffix}")
            archive.writestr("mathcoffee/__main__.py", "# CLI fixture\n")
        return path

    def options(self, *arguments):
        return bootstrap.parser().parse_args(arguments)

    def execute(self, *arguments):
        return bootstrap.execute(self.options(*arguments, "--execute"), self.distribution)

    def test_default_plan_is_read_only_on_mac_and_linux(self):
        original = content_hashes(self.distribution)
        for system, architecture in [("Darwin", "arm64"), ("Linux", "x86_64")]:
            with (
                patch.object(bootstrap.platform, "system", return_value=system),
                patch.object(bootstrap.platform, "machine", return_value=architecture),
            ):
                plan = bootstrap.execute(self.options(), self.distribution)
            self.assertFalse(plan["executed"])
            self.assertEqual(plan["required_formulae"], ["uv", "python@3.13"])
            self.assertFalse(any("setup" in cmd for cmd in plan["commands"]))
        self.assertFalse(self.data.exists())
        self.assertFalse(self.cache.exists())
        self.assertFalse(self.machine.calls)
        self.assertEqual(content_hashes(self.distribution), original)

    def test_profiles_and_explicit_model_tex_flags(self):
        plain = bootstrap.create_plan(self.options("--profile", "full"), self.distribution)
        selected = [
            cmd[cmd.index("--component") + 1] for cmd in plain["commands"] if "--component" in cmd
        ]
        self.assertEqual(selected, ["render", "speech"])
        self.assertNotIn("mactex-no-gui", str(plain["commands"]))
        with_model = bootstrap.create_plan(
            self.options("--profile", "full", "--with-model", "--with-tex"), self.distribution
        )
        self.assertEqual(
            [
                cmd[cmd.index("--component") + 1]
                for cmd in with_model["commands"]
                if "--component" in cmd
            ],
            ["render", "speech", "model"],
        )
        self.assertIn("mactex-no-gui", str(with_model["commands"]))
        for args in [("--with-model",), ("--profile", "render", "--with-model"), ("--with-tex",)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                bootstrap.create_plan(self.options(*args), self.distribution)

    def test_source_checkout_requires_a_release_wheel(self):
        source = self.directory / "source checkout"
        source.mkdir()
        plan = bootstrap.create_plan(self.options(), source)
        self.assertIsNone(plan["wheel"])
        self.assertIn("uv build --wheel", plan["next_step"])
        with self.assertRaisesRegex(ValueError, "complete release"):
            bootstrap.execute(self.options("--execute"), source)
        self.assertFalse(self.machine.calls)
        self.assertFalse(self.data.exists())

    def test_execution_requires_native_mac_homebrew_and_clt_before_writes(self):
        with patch.object(bootstrap.platform, "system", return_value="Linux"):
            with self.assertRaisesRegex(RuntimeError, "Apple Silicon"):
                self.execute()
        self.assertFalse(self.machine.calls)
        self.machine.brew_prefix = "/usr/local"
        with self.assertRaisesRegex(RuntimeError, "native"):
            self.execute()
        self.machine.brew_prefix = str(self.brew)
        self.machine.clt_available = False
        with self.assertRaisesRegex(RuntimeError, "Command Line Tools"):
            self.execute()
        self.assertFalse(self.data.exists())
        self.assertFalse(any("install" in c for c in self.machine.commands()))

    def test_core_installs_only_missing_formula_and_offline_wheel_and_preserves_config(self):
        self.data.mkdir()
        config = self.data / "runtime.json"
        config.write_text(
            json.dumps({"custom": {"keep": True}, "render_python": "/existing/render"})
        )
        before = content_hashes(self.distribution)
        result = self.execute()
        self.assertTrue(result["ready"])
        commands = self.machine.commands()
        formula = [cmd for cmd in commands if cmd[1:3] == ["install", "--formula"]]
        self.assertEqual(
            formula, [[str(self.brew / "bin/brew"), "install", "--formula", "python@3.13"]]
        )
        pip = next(cmd for cmd in commands if cmd[1:3] == ["pip", "install"])
        self.assertIn("--offline", pip)
        self.assertIn("--no-deps", pip)
        self.assertIn("external data", pip[pip.index("--python") + 1])
        registered = json.loads(config.read_text())
        self.assertEqual(registered["custom"], {"keep": True})
        self.assertEqual(registered["render_python"], "/existing/render")
        self.assertEqual(registered["core_python"], str(Path(result["core"]) / "bin/python"))
        self.assertEqual(content_hashes(self.distribution), before)
        self.assertFalse(self.cache.exists())
        self.assertFalse(any("upgrade" in cmd for cmd in commands))
        self.assertTrue(
            all(call["env"]["UV_PYTHON_DOWNLOADS"] == "never" for call in self.machine.calls)
        )

    def test_full_without_model_prepares_render_and_voice_and_uses_render_diagnostic(self):
        with patch.object(bootstrap, "tex_available", return_value=True):
            result = self.execute("--profile", "full", "--with-tex")
        commands = self.machine.commands()
        setup = [cmd for cmd in commands if "--component" in cmd]
        self.assertEqual([cmd[cmd.index("--component") + 1] for cmd in setup], ["render", "speech"])
        self.assertFalse(any("mactex-no-gui" in cmd for cmd in commands))
        self.assertEqual(result["doctor"]["profile"], "render")
        self.assertTrue(result["voice"]["runtime_prepared"])
        self.assertIn("not_requested", result["voice"]["model_status"])
        self.assertEqual(
            json.loads((self.data / "runtime.json").read_text())["node"],
            str(self.brew / "opt/node@24/bin/node"),
        )
        setup_env = next(call["env"] for call in self.machine.calls if "setup" in call["command"])
        self.assertIn(str(self.brew / "opt/node@24/bin"), setup_env["PATH"])
        self.assertIn("/Library/TeX/texbin", setup_env["PATH"])

    def test_model_is_downloaded_only_when_explicitly_selected(self):
        result = self.execute("--profile", "full", "--with-model")
        setup = [cmd for cmd in self.machine.commands() if "--component" in cmd]
        self.assertEqual(
            [cmd[cmd.index("--component") + 1] for cmd in setup], ["render", "speech", "model"]
        )
        self.assertEqual(result["doctor"]["profile"], "full")
        self.assertEqual(result["voice"]["model_status"], "prepared")

    def test_repeated_execution_reuses_owned_core_and_profiles_can_advance(self):
        first = self.execute()
        core = Path(first["core"])
        before = content_hashes(core)
        self.machine.calls.clear()
        self.execute("--profile", "render")
        self.assertEqual(content_hashes(core), before)
        self.assertFalse(
            any(
                cmd[1] == "venv" or cmd[1:3] == ["pip", "install"]
                for cmd in self.machine.commands()
            )
        )
        self.assertEqual(
            [
                cmd[cmd.index("--component") + 1]
                for cmd in self.machine.commands()
                if "--component" in cmd
            ],
            ["render"],
        )

    def test_interrupted_components_resume_without_replacing_core_or_completed_render(self):
        self.machine.fail_component = "speech"
        with self.assertRaisesRegex(RuntimeError, "command failed"):
            self.execute("--profile", "full")
        receipt = self.data / "runtimes" / self.version / "core.bootstrap.json"
        value = json.loads(receipt.read_text())
        self.assertEqual(value["status"], "interrupted")
        self.assertIn("render", value["completed"])
        self.assertNotIn("speech", value["completed"])
        self.machine.fail_component = None
        self.machine.calls.clear()
        self.execute("--profile", "full")
        self.assertEqual(
            [
                cmd[cmd.index("--component") + 1]
                for cmd in self.machine.commands()
                if "--component" in cmd
            ],
            ["speech"],
        )
        self.assertFalse(any(cmd[1] == "venv" for cmd in self.machine.commands()))

    def test_unowned_core_and_different_wheel_same_version_are_retained(self):
        core = self.data / "runtimes" / self.version / "core"
        core.mkdir(parents=True)
        (core / "user.txt").write_text("retain")
        before = content_hashes(self.data)
        with self.assertRaises(FileExistsError):
            self.execute()
        self.assertEqual(content_hashes(self.data), before)
        self.assertFalse(self.machine.calls)
        (core / "user.txt").unlink()
        core.rmdir()
        self.execute()
        before = content_hashes(self.data)
        self.machine.calls.clear()
        self.write_wheel(suffix="# different source\n")
        with self.assertRaisesRegex(ValueError, "different wheel"):
            self.execute()
        self.assertEqual(content_hashes(self.data), before)
        self.assertFalse(self.machine.calls)

    def test_new_release_gets_a_separate_core_and_retains_old_release(self):
        first = self.execute()
        old = Path(first["core"])
        before = content_hashes(old)
        new_wheel = self.write_wheel(version="0.2.0a3")
        result = self.execute("--wheel", str(new_wheel))
        self.assertNotEqual(result["core"], str(old))
        self.assertEqual(content_hashes(old), before)
        self.assertIn(
            "0.2.0a3", json.loads((self.data / "runtime.json").read_text())["core_python"]
        )

    def test_tampered_core_package_is_not_overwritten(self):
        first = self.execute()
        core = Path(first["core"])
        package = core / "lib/python3.13/site-packages/mathcoffee/__init__.py"
        package.write_text("# user changed\n")
        with self.assertRaisesRegex(ValueError, "differs from its wheel"):
            self.execute()
        self.assertEqual(package.read_text(), "# user changed\n")

    def test_symlinked_roots_core_and_runtime_json_are_rejected(self):
        actual = self.directory / "actual"
        actual.mkdir()
        self.data.symlink_to(actual, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlinked"):
            bootstrap.create_plan(self.options(), self.distribution)
        self.data.unlink()
        self.data.mkdir()
        (self.data / "runtime.json").symlink_to(actual / "runtime.json")
        with self.assertRaisesRegex(ValueError, "symlinked"):
            self.execute()
        (self.data / "runtime.json").unlink()
        core = self.data / "runtimes" / self.version / "core"
        core.parent.mkdir(parents=True)
        core.symlink_to(actual, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlinked"):
            self.execute()
        self.assertEqual(list(actual.iterdir()), [])

    def test_installation_inside_the_plugin_is_rejected(self):
        with patch.dict(os.environ, {"MATHCOFFEE_DATA_HOME": str(self.distribution / "runtime")}):
            with self.assertRaisesRegex(ValueError, "outside the distribution"):
                bootstrap.create_plan(self.options(), self.distribution)
        self.assertFalse((self.distribution / "runtime").exists())

    def test_opted_in_tex_failure_has_manual_recovery_and_retains_receipt(self):
        self.machine.fail_cask = True
        with contextlib.redirect_stderr(io.StringIO()) as messages:
            with self.assertRaisesRegex(RuntimeError, "administrator dialog"):
                self.execute("--profile", "render", "--with-tex")
        self.assertIn("administrator approval", messages.getvalue())
        receipt = self.data / "runtimes" / self.version / "core.bootstrap.json"
        self.assertEqual(json.loads(receipt.read_text())["status"], "interrupted")
        self.assertFalse(any(cmd[1] == "venv" for cmd in self.machine.commands()))

    def test_known_native_homebrew_is_found_when_fresh_shell_path_omits_it(self):
        executable = self.brew / "bin/brew"
        executable.parent.mkdir(parents=True)
        executable.write_text("#!/bin/sh\nexit 99\n")
        executable.chmod(0o755)
        with patch.object(bootstrap.shutil, "which", return_value=None):
            self.assertEqual(bootstrap.find_brew(), str(executable))
            result = self.execute()
        self.assertTrue(result["ready"])
        self.assertEqual(result["homebrew"], str(executable))
        self.assertTrue(any(cmd[0] == str(executable) for cmd in self.machine.commands()))

    def test_shell_frontend_dry_run_and_invalid_flags_do_not_write(self):
        env = os.environ.copy()
        env["PATH"] = "/usr/bin:/bin"
        result = subprocess.run(
            ["/bin/sh", str(ROOT / "bin/setup-macos"), "--wheel", str(self.wheel)],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["executed"], False)
        bad = subprocess.run(
            ["/bin/sh", str(ROOT / "bin/setup-macos"), "--execute", "--unexpected"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(bad.returncode, 2)
        self.assertFalse(self.data.exists())
        self.assertFalse(self.cache.exists())

    def test_malicious_wheel_paths_and_versions_are_rejected_without_writes(self):
        with zipfile.ZipFile(self.wheel, "a") as archive:
            archive.writestr("../outside.py", "bad")
        with self.assertRaisesRegex(ValueError, "escaping"):
            bootstrap.create_plan(self.options(), self.distribution)
        self.assertFalse(self.data.exists())


if __name__ == "__main__":
    unittest.main()

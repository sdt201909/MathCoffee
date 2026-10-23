"""Host package boundaries and launcher behavior; no host install or downloads."""

import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from mathcoffee import plugin_bundle as bundle

ROOT = Path(__file__).resolve().parents[1]


class PluginBundleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mathcoffee bundle ")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.wheel = self.directory / "mathcoffee-0.2.0a1-py3-none-any.whl"
        self.write_wheel()

    def write_wheel(self, *, name="MathCoffee", version="0.2.0a1", cli=True, extra=None):
        with zipfile.ZipFile(self.wheel, "w") as archive:
            archive.writestr("mathcoffee-0.2.0a1.dist-info/METADATA",
                             f"Metadata-Version: 2.3\nName: {name}\nVersion: {version}\n")
            if cli:
                archive.writestr("mathcoffee-0.2.0a1.dist-info/entry_points.txt",
                                 "[console_scripts]\nmathcoffee = mathcoffee.cli:main\n")
            archive.writestr("mathcoffee/__main__.py", "# fixture entry point\n")
            archive.writestr("mathcoffee/data/presets/shorts.json", "{}")
            if extra:
                archive.writestr(*extra)

    def test_codex_and_claude_packages_are_complete_and_contained(self):
        for host in ("codex", "claude"):
            with self.subTest(host=host):
                output = self.directory / f"{host} package.zip"
                report = bundle.build_bundle(output, host, self.wheel)
                self.assertEqual(report["sha256"], hashlib.sha256(output.read_bytes()).hexdigest())
                self.assertEqual(bundle.validate_bundle(output)["status"], "PASS")
                with zipfile.ZipFile(output) as archive:
                    names = archive.namelist()
                    self.assertIn(bundle.HOST_MANIFESTS[host], names)
                    self.assertIn(bundle.HOST_MARKETPLACES[host], names)
                    other = "claude" if host == "codex" else "codex"
                    self.assertNotIn(bundle.HOST_MANIFESTS[other], names)
                    self.assertIn("engines/remotion/package-lock.json", names)
                    self.assertIn("toolchains/speech/requirements.lock", names)
                    self.assertIn(f"wheels/{self.wheel.name}", names)
                    mode = archive.getinfo("bin/mathcoffee").external_attr >> 16
                    self.assertEqual(stat.S_IMODE(mode), 0o755)
                    self.assertFalse(any(
                        "node_modules" in n or n.startswith("media/") for n in names
                    ))
                self.assertTrue(Path(report["receipt"]).is_file())

    def test_relocated_extracted_catalog_points_at_the_wheel_containing_plugin_root(self):
        for host in ("codex", "claude"):
            with self.subTest(host=host):
                archive_path = self.directory / f"relocated-{host}.zip"
                bundle.build_bundle(archive_path, host, self.wheel)
                extracted = self.directory / "new parent with spaces" / host
                with zipfile.ZipFile(archive_path) as archive:
                    archive.extractall(extracted)
                catalog_path = extracted / bundle.HOST_MARKETPLACES[host]
                catalog = json.loads(catalog_path.read_text())
                source = catalog["plugins"][0]["source"]
                relative = source["path"] if isinstance(source, dict) else source
                plugin_root = (extracted / relative).resolve()
                self.assertEqual(plugin_root, extracted.resolve())
                self.assertTrue((plugin_root / bundle.HOST_MANIFESTS[host]).is_file())
                self.assertEqual(len(list((plugin_root / "wheels").glob("*.whl"))), 1)
                self.assertTrue((plugin_root / "skills/create/SKILL.md").is_file())
                self.assertNotIn(str(ROOT), catalog_path.read_text())

    def test_no_wheel_is_not_misrepresented_as_an_installable_bundle(self):
        with self.assertRaisesRegex(ValueError, "explicit"):
            bundle.build_bundle(self.directory / "missing.zip")
        self.assertFalse((self.directory / "missing.zip").exists())

    def test_invalid_host_suffix_or_version_fail_before_writing(self):
        for output, host in (("payload.zip", "other"), ("directory", "codex")):
            with self.subTest(output=output, host=host), self.assertRaises(ValueError):
                bundle.build_bundle(self.directory / output, host, self.wheel)
        self.write_wheel(version="0.9.0")
        with self.assertRaisesRegex(ValueError, "versions differ"):
            bundle.build_bundle(self.directory / "version.zip", wheel_path=self.wheel)

    def test_legacy_or_unrelated_wheel_is_rejected(self):
        cases = (({"cli": False}, "entry point"), ({"name": "Other"}, "distribution"))
        for options, reason in cases:
            self.write_wheel(**options)
            with self.subTest(options=options), self.assertRaisesRegex(ValueError, reason):
                bundle.build_bundle(self.directory / "legacy.zip", wheel_path=self.wheel)

    def test_media_or_traversal_in_wheel_is_rejected(self):
        for extra in (("../outside.py", "bad"), ("mathcoffee/master.mp4", "media")):
            self.write_wheel(extra=extra)
            with self.subTest(extra=extra[0]), self.assertRaises(ValueError):
                bundle.build_bundle(self.directory / "unsafe.zip", wheel_path=self.wheel)

    def test_existing_archive_receipt_and_dangling_link_are_protected(self):
        output = self.directory / "existing.zip"
        output.write_bytes(b"keep")
        with self.assertRaises(FileExistsError):
            bundle.build_bundle(output, wheel_path=self.wheel)
        self.assertEqual(output.read_bytes(), b"keep")
        other = self.directory / "receipt.zip"
        other.with_suffix(".zip.manifest.json").write_text("keep receipt")
        with self.assertRaises(FileExistsError):
            bundle.build_bundle(other, wheel_path=self.wheel)
        link = self.directory / "dangling.zip"
        link.symlink_to(self.directory / "absent")
        with self.assertRaises(FileExistsError):
            bundle.build_bundle(link, wheel_path=self.wheel)

    def test_symlinked_source_resource_is_not_followed(self):
        root = self.directory / "resources"
        root.mkdir()
        (root / "link").symlink_to(ROOT / "bin/mathcoffee")
        with self.assertRaisesRegex(ValueError, "symlink"):
            bundle._read_regular(root, "link")

    def test_receipt_detects_changed_bytes(self):
        original = self.directory / "original.zip"
        bundle.build_bundle(original, wheel_path=self.wheel)
        tampered = self.directory / "tampered.zip"
        with zipfile.ZipFile(original) as source, zipfile.ZipFile(tampered, "w") as destination:
            for entry in source.infolist():
                data = (b"modified" if entry.filename == "bin/mathcoffee"
                        else source.read(entry.filename))
                destination.writestr(entry, data)
        with self.assertRaisesRegex(ValueError, "hash differs"):
            bundle.validate_bundle(tampered)


class LauncherTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mathcoffee launch ")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.plugin = self.directory / "read only plugin"
        (self.plugin / "bin").mkdir(parents=True)
        self.launcher = self.plugin / "bin/mathcoffee"
        shutil.copy2(ROOT / "bin/mathcoffee", self.launcher)
        self.environment = {**os.environ, "HOME": str(self.directory / "home"),
                            "MATHCOFFEE_DATA_HOME": str(self.directory / "external runtime"),
                            "MATHCOFFEE_RUNTIME_DIR": str(self.directory / "external runtime")}
        self.environment.pop("MATHCOFFEE_PYTHON", None)

    def launch(self, *args):
        return subprocess.run([str(self.launcher), *args], env=self.environment,
                              capture_output=True, text=True, check=False)

    def fake_python(self):
        executable = self.directory / "core runtime" / "python with spaces"
        executable.parent.mkdir(exist_ok=True)
        executable.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n")
        executable.chmod(0o755)
        return executable

    def test_first_use_reports_setup_without_modifying_plugin_or_creating_runtime(self):
        before = {str(p.relative_to(self.plugin)): p.read_bytes()
                  for p in self.plugin.rglob("*") if p.is_file()}
        self.plugin.chmod(0o555)
        result = self.launch("--help")
        self.assertEqual(result.returncode, 3)
        self.assertEqual(json.loads(result.stderr)["status"], "setup_required")
        self.assertFalse(Path(self.environment["MATHCOFFEE_RUNTIME_DIR"]).exists())
        after = {str(p.relative_to(self.plugin)): p.read_bytes()
                 for p in self.plugin.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.plugin.chmod(0o755)

    def test_explicit_runtime_preserves_argument_boundaries(self):
        self.environment["MATHCOFFEE_PYTHON"] = str(self.fake_python())
        result = self.launch("plan", "--workspace", "project with spaces", "--json")
        self.assertEqual(result.returncode, 0)
        expected = ["-I", "-B", "-m", "mathcoffee", "plan", "--workspace", "project with spaces", "--json"]
        self.assertEqual(result.stdout.splitlines(), expected)

    def test_dedicated_runtime_json_can_select_external_interpreter(self):
        runtime = Path(self.environment["MATHCOFFEE_RUNTIME_DIR"])
        runtime.mkdir()
        (runtime / "runtime.json").write_text(json.dumps({"core_python": str(self.fake_python())}))
        result = self.launch("doctor")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.splitlines(), ["-I", "-B", "-m", "mathcoffee", "doctor"])

    def test_setup_runtime_json_without_core_override_preserves_default_core(self):
        runtime = Path(self.environment["MATHCOFFEE_DATA_HOME"])
        executable = runtime / "core/bin/python"
        executable.parent.mkdir(parents=True)
        shutil.copy2(self.fake_python(), executable)
        # Explicit component setup registers its own paths, not core_python.
        (runtime / "runtime.json").write_text(json.dumps({
            "render_python": str(runtime / "runtimes/0.2.0a1/render/bin/python"),
            "remotion_root": str(runtime / "remotion"),
            "browser_executable": str(runtime / "browser"),
        }))
        result = self.launch("doctor", "--workspace", "own project")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.splitlines(),
                         ["-I", "-B", "-m", "mathcoffee", "doctor", "--workspace", "own project"])

    def test_explicit_invalid_core_override_does_not_fall_back(self):
        runtime = Path(self.environment["MATHCOFFEE_DATA_HOME"])
        executable = runtime / "core/bin/python"
        executable.parent.mkdir(parents=True)
        shutil.copy2(self.fake_python(), executable)
        for value in (None, "", "path\ncommand", 7):
            with self.subTest(value=value):
                (runtime / "runtime.json").write_text(json.dumps({"core_python": value}))
                result = self.launch("doctor")
                self.assertEqual(result.returncode, 3)
                self.assertIn("Invalid MathCoffee runtime.json core_python",
                              json.loads(result.stderr)["reason"])

    def test_invalid_runtime_configuration_is_actionable(self):
        self.environment["MATHCOFFEE_PYTHON"] = str(self.directory / "absent")
        result = self.launch("plan")
        self.assertEqual(result.returncode, 3)
        self.assertIn("not executable", json.loads(result.stderr)["reason"])


if __name__ == "__main__":
    unittest.main()

"""Regression coverage for the upload boundary; never print candidate secrets."""

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "repository_guard", Path(__file__).resolve().parents[1] / "scripts/repository_guard.py",
)
GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)


class RepositoryGuardTests(unittest.TestCase):
    def test_forced_staging_or_allowlisting_does_not_permit_production_assets(self):
        for path in ("media/master.mp4", "scenes/episode.py", "assets/topic_authoring.json",
                     ".venv-speech/config", "data/model.onnx", ".env.local"):
            with self.subTest(path=path):
                self.assertTrue(GUARD.inspect_file(path, "100644", b"safe text"))

    def test_binary_symlink_size_and_private_key_are_rejected(self):
        key = b"-----BEGIN " + b"PRIVATE KEY-----"
        for mode, data in (("120000", b"target"), ("100644", b"x\0y"),
                           ("100644", b"x" * (GUARD.MAX_BYTES + 1)), ("100644", key)):
            with self.subTest(mode=mode, size=len(data)):
                self.assertTrue(GUARD.inspect_file("src/tool.py", mode, data))
        self.assertFalse(GUARD.inspect_file("src/tool.py", "100644", b"# shared utility\n"))

    def test_scanner_does_not_report_credential_bytes(self):
        token = b"ghp_" + b"a" * 40
        result = GUARD.inspect_file("config.txt", "100644", token)
        self.assertTrue(result)
        self.assertNotIn(token.decode(), " ".join(result))

    def test_manifest_rejects_traversal_duplicates_and_missing_self(self):
        for data in (b"../file\nrepository-files.txt", b"file\nfile\nrepository-files.txt", b"file"):
            with self.subTest(data=data), self.assertRaises(ValueError):
                GUARD.parse_manifest(data)

    def test_index_content_is_checked_even_when_worktree_looks_safe(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "repository-files.txt").write_text("repository-files.txt\nconfig.txt\n")
            (root / "config.txt").write_bytes(b"ghp_" + b"a" * 40)
            subprocess.run(["git", "add", "repository-files.txt", "config.txt"], cwd=root, check=True)
            (root / "config.txt").write_text("safe current file")
            with patch.object(GUARD, "ROOT", root):
                self.assertTrue(any("credential" in x for x in GUARD.check_tree(None)))
                subprocess.run(["git", "add", "config.txt"], cwd=root, check=True)
                self.assertEqual(GUARD.check_tree(None), [])


if __name__ == "__main__":
    unittest.main()

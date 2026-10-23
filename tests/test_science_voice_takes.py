"""Seed-only composition fixtures; .venv-speech, no model inference or downloads."""

import importlib.util
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "compose_science_voice",
    ROOT / "scripts/compose_science_voice.py",
)
COMPOSE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COMPOSE)


class ScienceVoiceTakeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.old, self.new = self.root / "old", self.root / "candidate"
        self.old.mkdir()
        self.new.mkdir()
        (self.root / "assets").mkdir()
        self.ids = ["ch04_05", "ch04_06", "ch04_07", "ch05_01"]
        self.cases = [
            {"id": cue_id, "text": f"这是第{number}句正文。"}
            for number, cue_id in enumerate(self.ids)
        ]
        self.parameters = {
            "speaker": "Serena",
            "language": "auto",
            "instruct": "清晰理性。",
            "temperature": 0.5,
            "text_conditioning": "full_text",
            "stream": False,
        }
        self.lexicon = self.root / "lexicon.json"
        self.profiles = self.root / "profiles.json"
        self.save(self.lexicon, {"schema_version": 1, "pronunciations": [], "aliases": []})
        self.save(self.profiles, {"profiles": {"science_female": {"qwen_mlx": self.parameters}}})
        adapter = self.root / "adapter.py"
        adapter.write_text("# fixture adapter\n")
        upstream = self.root / "upstream.py"
        upstream.write_text("# fixture upstream\n")
        model = self.root / "model"
        model.mkdir()
        (model / "config.json").write_text("{}")
        entries = [
            {"path": "config.json", "bytes": 2, "sha256": COMPOSE.sha256(model / "config.json")}
        ]
        model_source = self.root / "model_source.json"
        self.save(model_source, {"repo": "fixture", "revision": "pinned"})
        self.runtime = {
            "parameters": self.parameters,
            "effective_generation_parameters": {
                k: v for k, v in self.parameters.items() if k != "text_conditioning"
            },
            "text_conditioning": {
                "effective_text_context": "full_text",
                "reference_conditioning": False,
                "upstream_source_path": str(upstream),
                "upstream_source_sha256": COMPOSE.sha256(upstream),
            },
            "context_scope": "one request; no cross-request acoustic conditioning",
            "versions": {"mlx-audio": "fixture"},
            "device": "fixture-cpu",
            "load_seconds": 1,
            "model_repo": "fixture",
            "model_revision": "pinned",
            "model": {
                "directory": str(model),
                "files": entries,
                "content_sha256": COMPOSE.digest_json(entries),
                "source": {
                    "manifest_path": str(model_source),
                    "manifest_sha256": COMPOSE.sha256(model_source),
                    "status": "matched_pinned_source",
                    "repo": "fixture",
                    "revision": "pinned",
                },
            },
        }
        self.original = self.make_manifest(self.old, self.cases, 42)
        self.retake = self.make_manifest(self.new, [self.cases[1]], 43)
        self.retake["runtime"]["load_seconds"] = 9  # Actual load timings legitimately differ.
        self.old_manifest, self.new_manifest = (
            self.old / "manifest.json",
            self.new / "manifest.json",
        )
        self.save(self.old_manifest, self.original)
        self.save(self.new_manifest, self.retake)
        authoring = self.root / "assets/fixture_authoring.json"
        cut = self.root / "assets/fixture_cut.json"
        self.save(authoring, {"chapters": [{"id": "ch04", "cues": self.cases}]})
        self.save(cut, {"source_authoring_sha256": COMPOSE.sha256(authoring), "excluded_cues": []})
        request = {
            "selected_ids": self.ids,
            "parameters": self.parameters,
            "seed": 42,
            "model_content_sha256": self.runtime["model"]["content_sha256"],
            "runtime_versions": self.runtime["versions"],
            "sources": {
                str(p.relative_to(self.root)): COMPOSE.sha256(p)
                for p in (authoring, cut, self.profiles, self.lexicon, adapter)
            },
        }
        self.save(self.old / "request.json", request)
        cues = [
            {
                "id": c["id"],
                "text": c["subtitle_text"],
                "spoken_text": c["spoken_text"],
                "path": c["audio"]["path"],
                "sha256": c["audio"]["sha256"],
                "bytes": c["audio"]["bytes"],
                **c["signal"],
                "synthesis": c["synthesis"],
            }
            for c in self.original["cases"]
        ]
        self.base = self.old / "index.json"
        self.save(
            self.base,
            {
                "schema_version": 1,
                "episode": "fixture",
                "revision": "r04",
                "cues": cues,
                "source_sha256": COMPOSE.sha256(authoring),
                "request_sha256": COMPOSE.sha256(self.old / "request.json"),
                "chapters": [
                    {
                        "id": "ch04",
                        "chapter_id": "ch04",
                        "cues": cues,
                        "runtime": self.runtime,
                        "manifest": str(self.old_manifest),
                        "manifest_sha256": COMPOSE.sha256(self.old_manifest),
                    }
                ],
            },
        )
        self.output = self.root / "r05_science"

    @staticmethod
    def save(path, value):
        path.write_text(json.dumps(value, ensure_ascii=False))

    @staticmethod
    def resign(manifest):
        plans = [
            {k: v for k, v in c.items() if k not in COMPOSE.GENERATED_FIELDS}
            for c in manifest["cases"]
        ]
        manifest["synthesis_identity_sha256"] = COMPOSE.digest_json(
            {
                "provider": manifest["provider"],
                "parameters": manifest["parameters"],
                "seed": manifest["seed"],
                "gap_seconds": manifest["gap_seconds"],
                "plans": plans,
                "inputs": manifest["inputs"],
                "adapter_sources": manifest["adapter_sources"],
                "runtime": COMPOSE.runtime_identity(manifest),
            }
        )

    def make_manifest(self, directory, cases, seed):
        cases_path = directory / "cases.json"
        self.save(cases_path, {"cases": cases})
        manifest = {
            "status": "generated_signal_checked",
            "provider": "qwen_mlx",
            "profile": "science_female",
            "seed": seed,
            "gap_seconds": 0,
            "parameters": deepcopy(self.parameters),
            "runtime": deepcopy(self.runtime),
            "capabilities": {"network_at_synthesis": False},
            "platform": {"system": "fixture"},
            "adapter_sources": {"adapter.py": COMPOSE.sha256(self.root / "adapter.py")},
            "inputs": {
                str(p): COMPOSE.sha256(p) for p in (cases_path, self.profiles, self.lexicon)
            },
            "cases": [],
        }
        for number, case in enumerate(cases):
            cue = COMPOSE.make_plan(case, "qwen_mlx", COMPOSE.read(self.lexicon))
            wav = directory / f"{case['id']}.wav"
            sf.write(
                wav,
                0.15 * np.sin(np.arange(4800 + 240 * (seed - 42)) * (0.02 + number / 100)),
                24000,
                subtype="PCM_24",
            )
            wave, rate = sf.read(wav, dtype="float32")
            cue.update(
                audio={
                    "path": str(wav),
                    "sha256": COMPOSE.sha256(wav),
                    "bytes": wav.stat().st_size,
                },
                signal=COMPOSE.signal_report(wave, rate, 60),
                synthesis={
                    "seed": seed,
                    "speaker": "Serena",
                    "language": "auto",
                    "instruct": self.parameters["instruct"],
                    "text_conditioning": deepcopy(self.runtime["text_conditioning"]),
                    "context_scope": self.runtime["context_scope"],
                    "effective_generation_parameters": deepcopy(
                        self.runtime["effective_generation_parameters"]
                    ),
                },
            )
            manifest["cases"].append(cue)
        self.resign(manifest)
        return manifest

    def compose(self, ids=None):
        return COMPOSE.compose(
            self.base,
            self.new_manifest,
            self.output,
            ["ch04_06"] if ids is None else ids,
            authoring_path=self.root / "assets/fixture_authoring.json",
            cut_path=self.root / "assets/fixture_cut.json",
            expected_count=4,
            project_root=self.root,
        )

    def assert_rejected(self, pattern=None):
        with self.assertRaisesRegex((ValueError, KeyError), pattern or ".*"):
            self.compose()
        self.assertFalse(self.output.exists())

    def test_seed_only_single_take_preserves_order_bytes_and_original_files(self):
        before = {str(p): COMPOSE.sha256(p) for p in self.root.rglob("*") if p.is_file()}
        index = COMPOSE.read(self.compose())
        cues = index["chapters"][0]["cues"]
        self.assertEqual(index["cues"], cues)
        self.assertEqual([c["id"] for c in cues], self.ids)
        for cue in cues:
            replaced = cue["id"] == "ch04_06"
            self.assertEqual(cue["synthesis"]["seed"], 43 if replaced else 42)
            self.assertEqual(
                cue["take_kind"], "explicit_seed_retake" if replaced else "retained_base"
            )
            self.assertEqual(COMPOSE.sha256(cue["path"]), cue["sha256"])
            self.assertEqual(COMPOSE.sha256(cue["source_manifest"]), cue["source_manifest_sha256"])
            self.assertEqual(cue["listening_status"], "pending_user_mac_review")
        receipt = COMPOSE.read(index["retake_receipt"])
        self.assertEqual(receipt["retained_cue_count"], 3)
        self.assertEqual(receipt["retakes"][0]["old_seed"], 42)
        self.assertEqual(receipt["retakes"][0]["new_seed"], 43)
        self.assertEqual(
            COMPOSE.sha256(self.output / "sources/base_index.json"), before[str(self.base)]
        )
        self.assertTrue(all(COMPOSE.sha256(p) == digest for p, digest in before.items()))
        self.assertNotIn("request_sha256", index)
        self.assertNotIn("runtime", index["chapters"][0])

    def test_existing_even_empty_output_is_never_overwritten(self):
        self.output.mkdir()
        with self.assertRaises(FileExistsError):
            self.compose()

    def test_empty_duplicate_unknown_or_unsafe_ids_are_rejected(self):
        for ids in ([], ["ch04_06", "ch04_06"], ["missing"], ["../escape"]):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                self.compose(ids)
        self.assertFalse(self.output.exists())

    def test_missing_retake_id_is_rejected(self):
        self.retake["cases"][0]["id"] = "different"
        self.save(self.new_manifest, self.retake)
        self.assert_rejected("lacks")

    def test_changed_parameters_profile_runtime_model_adapter_are_rejected(self):
        for section, field, value in (
            ("parameters", "temperature", 0.7),
            ("runtime", "device", "different"),
            ("runtime", "model_revision", "different"),
            ("runtime", "versions", {"mlx-audio": "different"}),
            ("adapter_sources", "adapter.py", "different"),
        ):
            candidate = deepcopy(self.retake)
            candidate[section][field] = value
            with self.subTest(section=section, field=field), self.assertRaises(ValueError):
                COMPOSE.validate_retake(
                    self.original["cases"][1], self.original, candidate["cases"][0], candidate
                )
        candidate = deepcopy(self.retake)
        candidate["profile"] = "renamed"
        with self.assertRaisesRegex(ValueError, "profile"):
            COMPOSE.validate_retake(
                self.original["cases"][1], self.original, candidate["cases"][0], candidate
            )

    def test_same_seed_false_per_cue_seed_or_out_of_range_are_rejected(self):
        for seed, cue_seed in ((42, 42), (43, 44), (-1, -1), (2**32, 2**32)):
            candidate = deepcopy(self.retake)
            candidate["seed"] = seed
            candidate["cases"][0]["synthesis"]["seed"] = cue_seed
            with self.subTest(seed=seed), self.assertRaises(ValueError):
                COMPOSE.validate_retake(
                    self.original["cases"][1], self.original, candidate["cases"][0], candidate
                )

    def test_changed_subtitle_spoken_text_or_normalization_are_rejected(self):
        for field, value in (
            ("subtitle_text", "少字。"),
            ("spoken_text", "少字。"),
            ("normalization_changes", [{"invented": "change"}]),
        ):
            cue = deepcopy(self.retake["cases"][0])
            cue[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, field):
                COMPOSE.validate_retake(self.original["cases"][1], self.original, cue, self.retake)

    def test_rewritten_case_source_cannot_mask_omitted_text(self):
        path = self.new / "cases.json"
        cases = {"cases": [{"id": "ch04_06", "text": "少字。"}]}
        self.save(path, cases)
        self.retake["inputs"][str(path)] = COMPOSE.sha256(path)
        replacement = COMPOSE.make_plan(cases["cases"][0], "qwen_mlx", COMPOSE.read(self.lexicon))
        self.retake["cases"][0].update(replacement)
        self.resign(self.retake)
        self.save(self.new_manifest, self.retake)
        self.assert_rejected("subtitle_text changed")

    def test_falsely_declared_spoken_plan_is_rejected(self):
        self.retake["cases"][0]["spoken_text"] = "漏字。"
        self.resign(self.retake)
        self.save(self.new_manifest, self.retake)
        self.assert_rejected("plan differs")

    def test_stale_case_adapter_model_or_upstream_hash_is_rejected(self):
        for path in (
            self.new / "cases.json",
            self.root / "adapter.py",
            self.root / "model/config.json",
            self.root / "upstream.py",
        ):
            original = path.read_bytes()
            with self.subTest(path=path):
                path.write_bytes(original + b" ")
                self.assert_rejected("stale source hash")
                path.write_bytes(original)

    def test_stale_manifest_request_and_index_audio_hashes_are_rejected(self):
        self.old_manifest.write_text(self.old_manifest.read_text() + " ")
        self.assert_rejected("stale source hash")
        self.save(self.old_manifest, self.original)
        index = COMPOSE.read(self.base)
        index["chapters"][0]["cues"][0]["sha256"] = "stale"
        self.save(self.base, index)
        self.assert_rejected("index cue differs")

    def test_forged_cache_identity_and_signal_receipt_are_rejected(self):
        self.retake["synthesis_identity_sha256"] = "stale"
        self.save(self.new_manifest, self.retake)
        self.assert_rejected("synthesis identity")
        self.resign(self.retake)
        self.retake["cases"][0]["signal"]["samples"] += 1
        self.save(self.new_manifest, self.retake)
        self.assert_rejected("decoded source WAV")

    def test_corrupt_wave_and_path_escape_are_rejected(self):
        wav = Path(self.retake["cases"][0]["audio"]["path"])
        original = wav.read_bytes()
        wav.write_bytes(original + b"bad")
        self.assert_rejected("WAV hash/size")
        wav.write_bytes(original)
        outside = self.root / "elsewhere.wav"
        outside.write_bytes(original)
        self.retake["cases"][0]["audio"]["path"] = str(outside)
        self.save(self.new_manifest, self.retake)
        self.assert_rejected("escaped")

    def test_reordered_index_or_authored_text_is_rejected(self):
        index = COMPOSE.read(self.base)
        index["chapters"][0]["cues"].reverse()
        self.save(self.base, index)
        self.assert_rejected("order differs")

    def test_source_mutation_during_copy_prevents_published_index(self):
        from unittest.mock import patch

        copyfile = COMPOSE.shutil.copyfile

        def mutate(source, destination):
            result = copyfile(source, destination)
            if str(destination).endswith("ch04_06.wav"):
                (self.root / "adapter.py").write_text("# source changed mid-composition")
            return result

        with patch.object(COMPOSE.shutil, "copyfile", side_effect=mutate):
            with self.assertRaisesRegex(ValueError, "changed during composition"):
                self.compose()
        self.assertTrue(self.output.exists())
        self.assertFalse((self.output / "index.json").exists())


if __name__ == "__main__":
    unittest.main()

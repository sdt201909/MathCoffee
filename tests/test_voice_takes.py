"""Strict local-take composition tests; run in .venv-speech, with no model load."""

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
    "compose_voice", ROOT / "scripts/compose_temperature_voice.py",
)
COMPOSE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COMPOSE)
RETAKE_IDS = ("cue_one", "cue_two", "cue_three")


class VoiceTakeTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.old = self.root / "old"
        self.new = self.root / "candidate"
        self.old.mkdir()
        self.new.mkdir()
        self.params = {
            "speaker": "Serena", "language": "auto", "instruct": "温柔自然地说。",
            "temperature": 0.7, "text_conditioning": "full_text", "stream": False,
        }
        self.runtime = {
            "parameters": self.params,
            "effective_generation_parameters": {k: v for k, v in self.params.items()
                                                if k != "text_conditioning"},
            "text_conditioning": {"effective_text_context": "full_text",
                                  "reference_conditioning": False},
            "model": {"content_sha256": "same-weights"}, "versions": {"mlx-audio": "fixture"},
            "model_repo": "fixture", "model_revision": "fixed", "context_scope": "one request",
        }
        self.original = self.make_manifest(self.old, self.runtime)
        new_runtime = deepcopy(self.runtime)
        new_runtime["parameters"]["temperature"] = 0.5
        new_runtime["effective_generation_parameters"]["temperature"] = 0.5
        self.retake = self.make_manifest(self.new, new_runtime)
        self.old_manifest = self.old / "manifest.json"
        self.new_manifest = self.new / "manifest.json"
        self.save(self.old_manifest, self.original)
        self.save(self.new_manifest, self.retake)
        index_cues = []
        for cue in self.original["cases"]:
            index_cues.append({
                "id": cue["id"], "text": cue["subtitle_text"], "spoken_text": cue["spoken_text"],
                "path": cue["audio"]["path"], "sha256": cue["audio"]["sha256"],
                "bytes": cue["audio"]["bytes"], **cue["signal"], "synthesis": cue["synthesis"],
            })
        self.base = self.root / "index.json"
        self.save(self.base, {
            "episode": "fixture", "source_sha256": "same-authoring", "revision": "r02",
            "cues": index_cues,
            "request_sha256": "old-request", "chapters": [{
                "id": "fixture", "chapter_id": "fixture", "cues": index_cues,
                "runtime": self.runtime, "manifest": str(self.old_manifest),
                "manifest_sha256": COMPOSE.sha256(self.old_manifest),
            }],
        })

    @staticmethod
    def save(path, value):
        path.write_text(json.dumps(value, ensure_ascii=False))

    def make_manifest(self, directory, runtime):
        cases = []
        for index, cue_id in enumerate((*RETAKE_IDS, "retained")):
            path = directory / f"{cue_id}.wav"
            factor = 0.15 if directory == self.old else 0.18
            sf.write(path, factor * np.sin(np.arange(4800) * (0.02 + index * 0.001)),
                     24000, subtype="PCM_24")
            wave, rate = sf.read(path, dtype="float32")
            synthesis = {
                "seed": 42, "speaker": "Serena", "language": "auto", "instruct": "温柔自然地说。",
                "text_conditioning": deepcopy(runtime["text_conditioning"]),
                "effective_generation_parameters": deepcopy(
                    runtime["effective_generation_parameters"],
                ),
            }
            cases.append({
                "id": cue_id, "subtitle_text": "正文。", "spoken_text": "正文。",
                "synthesis": synthesis, "signal": COMPOSE.signal_report(wave, rate, 60),
                "audio": {"path": str(path), "sha256": COMPOSE.sha256(path),
                          "bytes": path.stat().st_size},
            })
        return {"status": "generated_signal_checked", "provider": "qwen_mlx", "seed": 42,
                "parameters": deepcopy(runtime["parameters"]), "runtime": deepcopy(runtime),
                "adapter_sources": {"provider.py": "same-source"}, "cases": cases}

    def test_three_replacements_keep_originals_and_explicit_per_cue_temperatures(self):
        before = {str(p): COMPOSE.sha256(p) for p in self.root.rglob("*") if p.is_file()}
        out = self.root / "composed"
        result = COMPOSE.read(COMPOSE.compose(
            self.base, self.new_manifest, out, RETAKE_IDS, expected_count=4,
        ))
        chapter = result["chapters"][0]
        self.assertEqual(result["cues"], chapter["cues"])
        self.assertNotIn("runtime", chapter)
        self.assertEqual(chapter["base_runtime"]["parameters"]["temperature"], 0.7)
        for cue in chapter["cues"]:
            self.assertEqual(COMPOSE.sha256(cue["source_manifest"]), cue["source_manifest_sha256"])
            self.assertEqual(COMPOSE.sha256(cue["path"]), cue["sha256"])
            expected = 0.5 if cue["id"] in RETAKE_IDS else 0.7
            self.assertEqual(
                cue["synthesis"]["effective_generation_parameters"]["temperature"], expected,
            )
        retained = next(c for c in chapter["cues"] if c["id"] == "retained")
        self.assertEqual(retained["path"], str(self.old / "retained.wav"))
        self.assertEqual(result["listening_status"], "pending_user_mac_review")
        self.assertEqual(len(list((out / "retakes").glob("*.wav"))), 3)
        self.assertTrue(all(COMPOSE.sha256(p) == digest for p, digest in before.items()))
        with self.assertRaises(FileExistsError):
            COMPOSE.compose(self.base, self.new_manifest, out, RETAKE_IDS, expected_count=4)

    def test_changed_voice_instruction_language_text_or_context_is_rejected(self):
        original = self.original["cases"][0]
        for field in ("speaker", "instruct", "language"):
            candidate = deepcopy(self.retake)
            for parameters in (
                candidate["parameters"], candidate["runtime"]["parameters"],
                candidate["runtime"]["effective_generation_parameters"],
                candidate["cases"][0]["synthesis"]["effective_generation_parameters"],
            ):
                parameters[field] = "changed"
            candidate["cases"][0]["synthesis"][field] = "changed"
            with self.subTest(field=field), self.assertRaises(ValueError):
                COMPOSE.validate_retake(original, self.original, candidate["cases"][0], candidate)
        for field in ("subtitle_text", "spoken_text"):
            cue = deepcopy(self.retake["cases"][0])
            cue[field] = "不同的正文。"
            with self.subTest(field=field), self.assertRaises(ValueError):
                COMPOSE.validate_retake(original, self.original, cue, self.retake)
        candidate = deepcopy(self.retake)
        context = candidate["runtime"]["text_conditioning"]
        context["effective_text_context"] = "legacy_streaming_text"
        with self.assertRaises(ValueError):
            COMPOSE.validate_retake(original, self.original, candidate["cases"][0], candidate)

    def test_changed_model_revision_versions_seed_or_other_sampling_is_rejected(self):
        for field in ("model_revision", "versions", "model"):
            candidate = deepcopy(self.retake)
            candidate["runtime"][field] = (
                {"content_sha256": "different"} if field == "model" else "different"
            )
            with self.subTest(field=field), self.assertRaises(ValueError):
                COMPOSE.validate_retake(self.original["cases"][0], self.original,
                                        candidate["cases"][0], candidate)
        candidate = deepcopy(self.retake)
        candidate["seed"] = 43
        with self.assertRaises(ValueError):
            COMPOSE.validate_retake(self.original["cases"][0], self.original,
                                    candidate["cases"][0], candidate)
        candidate = deepcopy(self.retake)
        for params in (candidate["parameters"], candidate["runtime"]["parameters"],
                       candidate["runtime"]["effective_generation_parameters"],
                       candidate["cases"][0]["synthesis"]["effective_generation_parameters"]):
            params["top_k"] = 3
        with self.assertRaisesRegex(ValueError, "only temperature"):
            COMPOSE.validate_retake(self.original["cases"][0], self.original,
                                    candidate["cases"][0], candidate)

    def test_corrupted_source_waveform_and_false_signal_receipt_fail_before_output(self):
        path = Path(self.retake["cases"][0]["audio"]["path"])
        with path.open("ab") as stream:
            stream.write(b"corruption")
        out = self.root / "corrupt_composition"
        with self.assertRaisesRegex(ValueError, "WAV hash/size"):
            COMPOSE.compose(self.base, self.new_manifest, out, RETAKE_IDS, expected_count=4)
        self.assertFalse(out.exists())
        cue = deepcopy(self.original["cases"][0])
        cue["signal"]["samples"] += 1
        with self.assertRaisesRegex(ValueError, "decoded source WAV"):
            COMPOSE.validate_wave(cue, self.old_manifest)


if __name__ == "__main__":
    unittest.main()

English | [简体中文](README.zh-CN.md)

# Local MLX / Qwen speech runtime

This optional toolchain uses an independent Python 3.12 environment, with a lockfile for macOS
arm64. It does not change the main Manim environment. The model is a pinned official Qwen CustomVoice
snapshot; inference is provided by the independent MLX-Audio project. The repository includes
downloaders, configuration and notices, not model weights or generated audio.

## Installation and inspection

For installed plugins, use the [installation guide](../../docs/installation.md) and the CLI's
external runtime directories:

```sh
mathcoffee setup --component speech
mathcoffee setup --component model
```

These commands show plans. Add `--execute` only for authorized preparation. Model download is a
separate explicit action; planning does not require weights.

The following source-development commands require existing Python 3.12 and uv. Together they
install dependencies over the network and download about 4.52 GB of public model data, so run them
only within the user's authorized scope. `SPEECH_BASE_PYTHON` can select an existing Python 3.12
interpreter.

```sh
sh toolchains/speech/setup.sh
.venv-speech/bin/python toolchains/speech/fetch_model.py
.venv-speech/bin/python toolchains/speech/doctor.py --verify-model
.venv-speech/bin/python toolchains/speech/smoke.py
```

`setup.sh` installs locked packages with `uv pip sync --require-hashes`. The downloader fetches
pinned public files and explicitly disables implicit Hugging Face tokens. The
[model manifest](../../src/mathcoffee/data/speech/model_files.json) records the revision, file sizes
and checksums. Files enter the completion receipt only after full validation; interrupted downloads
retain partial files. `doctor.py` and `smoke.py` run offline. Source-toolchain reports live under
`media/reports/agent_upgrade/speech_runtime/`. The smoke test loads the model and synthesizes a
short sentence; it needs Apple Silicon Metal and sufficient memory.

## Pinned provenance and notices

- MLX-Audio 0.5.7: [PyPI](https://pypi.org/project/mlx-audio/0.5.7/) and
  [upstream project](https://github.com/Blaizzy/mlx-audio). The preserved notice is
  [LICENSE-mlx-audio.txt](LICENSE-mlx-audio.txt).
- Qwen CustomVoice: [pinned model snapshot](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice/tree/0c0e3051f131929182e2c023b9537f8b1c68adfe),
  revision `0c0e3051f131929182e2c023b9537f8b1c68adfe`. Source and license hashes are recorded in
  [licenses.json](licenses.json); the preserved text is [LICENSE-Qwen3-TTS.txt](LICENSE-Qwen3-TTS.txt).

Pinned provenance does not establish compatibility with every platform. Retain model source and
license material after downloading. The tool uses preset speakers; it offers neither cloning of
real voices nor a cloud fallback.

## Acceptance limits

The provider records original text, normalized input, pronunciation-dictionary matches, model
provenance, runtime adaptations and output hashes. Qwen accepts text and style instructions;
Kokoro phoneme replacements are not hard pronunciation controls for Qwen. Finite-value, non-silence
and waveform checks in `smoke.py` do not establish correct pronunciation, voice quality, emotion or
completeness. Record actual listening and synchronization of the final encoded audio separately.
See the [voice pipeline](../../docs/voice_pipeline.md) for production interfaces.

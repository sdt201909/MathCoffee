English | [简体中文](README.zh-CN.md)

# Local voice-consistency proxy

This optional tool uses WeSpeaker embeddings to locate potential voice changes across sentences
and to compare candidates with the same text. It reads local WAV files and writes diagnostic
reports. It does not modify narration or establish a person's identity, correct pronunciation or
acceptable listening quality. The repository contains no weights, recordings or historical reports.

## Provenance and isolation

The [WeSpeaker model](https://huggingface.co/Wespeaker/wespeaker-voxceleb-resnet34-LM) is pinned to
revision `f0c48c298fd835726c27956a5d617bad7115627e`. The ONNX file SHA-256 is
`7bb2f06e9df17cdf1ef14ee8a15ab08ed28e8d0ef5054ee135741560df2ec068`.
The downloader stores source, model card and license material under
`media/models/wespeaker-voxceleb-resnet34-LM/`. The model source declares CC-BY-4.0, with attribution
to the WeSpeaker project; Wang et al., ICASSP 2023. The upstream inference reference is this
[pinned source](https://github.com/wenet-e2e/wespeaker/blob/9fecd6cb4f47475d01761d87c826298dff4ef18c/wespeaker/bin/infer_onnx.py).

Use a separate Python 3.12 environment and the macOS arm64 lockfile. First confirm that uv and
Python 3.12 already exist. `VOICE_QA_BASE_PYTHON` can select the interpreter. Installation and model
download use the network and require authorization.

```sh
sh toolchains/voice_qa/setup.sh
.venv-voice-qa/bin/python toolchains/voice_qa/fetch_model.py
.venv-voice-qa/bin/python scripts/audit_speaker_embeddings.py \
  --input media/voiceover/example/manifest.json \
  --reference media/voiceover/example/reference.wav \
  --output media/reports/example/speaker_metrics.json
.venv-voice-qa/bin/python toolchains/voice_qa/test_metric.py
```

Analysis uses the CPU and disables telemetry before creating the ONNX Runtime session. It does not
upload audio. Preserve runtime warnings, such as device-cache messages, and investigate them in
the actual environment.

## Inputs and checks

Input supports `chapters[].cues[]`, speech `cases[]` or a generic manifest:

```json
{"items":[{"id":"sentence_01","path":"voice.wav","sha256":"optional_expected_sha256","text":"Original input text","active_start_sample":0,"active_end_sample":240000}]}
```

Paths may be absolute or relative to the manifest or project directory. Activity bounds use source
sample units; absent bounds mean the entire WAV. Features use Kaldi-native-fbank, 16 kHz sampling,
80 dimensions, a 25 ms window, a 10 ms hop and per-sentence mean normalization. Audio shorter than
0.5 seconds, nonfinite samples and hash mismatches are rejected.

`--compare` checks the model, anchors, feature settings and text for matching IDs; `--only-ids`
selects a fixed sentence set. Output is protected from overwrite and records input, WAV, model and
script hashes, package versions, embeddings and similarities. Generic tests cover feature-frame
counts, pure-gain invariance, resampling, invalid input, activity bounds and hash rejection.
Similarity has no automatic acceptance threshold; possible anomalies require human listening.

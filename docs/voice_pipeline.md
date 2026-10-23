English | [简体中文](voice_pipeline.zh-CN.md)

# Local voice production and pronunciation review

After independent installation, prepare requests with `mathcoffee voice --workspace <user-project>`;
add `--generate` explicitly to synthesize locally. The command reads unified Authoring v1 and
project configuration; see the [project interface](project_interface.md). A project may instead
import per-sentence recordings or explicitly select silent mode.

The compatibility entry [synthesize_voice.py](../scripts/synthesize_voice.py) supports `kokoro` and
`qwen_mlx`. [create_episode_voiceover.py](../scripts/create_episode_voiceover.py) retains existing
production calls with explicit episode, authoring, and revision arguments. Canonical implementation
lives inside the package; installed users do not need to copy scripts or write work into the plugin
installation.

The Manim Python 3.13 environment is separate from the voice environment. Qwen MLX uses Python 3.12,
MLX-Audio 0.5.7, and a pinned model snapshot. Installation and anonymous public-weight downloads are
explicit operations; see the [runtime guide](../toolchains/speech/README.md). Kokoro is an optional
existing provider. Its complete environment lock is not currently shipped, so it must not be
presented as a backend with a ready one-command installation.

## Original text, configuration, and model input

Preserve original text throughout; subtitles read that original. Dictionaries and spoken-number
expansion produce separate normalized input and match records.
[lexicon.json](../src/mathcoffee/data/speech/lexicon.json) selects the longest matching context first;
it must not perform global single-character substitution. Diagram labels A/B/C retain the same
letter names, including subscript, prime, and case identity.
[figure_label_contract.py](../src/mathcoffee/figure_label_contract.py) checks the label sequence in
the final model input. This proves textual identity correspondence only; actual pronunciation needs
separate listening.

The default `science_female` request in
[voice_profiles.json](../src/mathcoffee/data/speech/voice_profiles.json) uses the preset female
speaker Serena with a clear, rational, natural, even delivery instruction. A profile is a parameter
configuration, not proof of actual timbre, emotion, or naturalness. Kokoro has no equivalent
instruction capability; expected Qwen readings are not hard phoneme constraints. Do not clone real
people or call paid services. Production synthesis uses verified local weights with implicit
downloads and tokens disabled. [model_files.json](../src/mathcoffee/data/speech/model_files.json)
records pinned model-file identity. Before generation, verify its contents and the upstream adapter
source. A `doctor` path check is not a complete model-hash check.

```sh
mathcoffee setup --component speech             # Plan a separate Python 3.12 voice environment
mathcoffee setup --component model              # Plan the pinned-weight download
# Add --execute separately when preparation is authorized; plugin installation does not run it.
mathcoffee voice --workspace '/absolute/path/to/my video'
mathcoffee voice --workspace '/absolute/path/to/my video' --generate
```

The following source-checkout calls remain available. Installed users should prefer the CLI above.

```sh
# Install the optional separate environment only when needed; leave .venv unchanged.
SPEECH_BASE_PYTHON=/absolute/path/to/python3.12 make speech-setup
make speech-model
make speech-doctor

.venv-speech/bin/python scripts/synthesize_voice.py \
  --provider qwen_mlx --all --dry-run --output-dir media/speech_smoke/new-plan
```

Before full synthesis, generate short representative samples of this film's polyphonic characters,
numbers, formulas, English mixing, and diagram labels. Save each new revision in a new directory,
including the request, model identity, input SHA, parameters, PCM, and listening status; do not
overwrite an older revision. The [full-text adapter](../src/mathcoffee/speech/qwen_context.py), which
depends on private APIs, verifies the upstream version and source SHA and refuses mismatches.
`stream: false` does not establish full-text conditioning; the effective context mode after
adaptation is recorded in the manifest.

## Timing and acceptance

Measure activity windows from actual PCM, then derive subtitles, shot anchors, and music ducking.
Do not trim sentence endings or arbitrarily change whole-passage speed to force narration into
estimated windows. Review cross-sentence voice character, speed, pauses, and pronunciation
separately. ASR or forced alignment does not prove correct pronunciation.

Shared tools support explicit seed-based retake assembly, speech-rate and pause measurements, and
acoustic proxy metrics. Optional [voice_qa](../toolchains/voice_qa/README.md) uses a local model to
rank suspected voice drift; it does not replace listening. Record listening as pending if nobody
has listened. Automated success must not be reported as human approval. Separately verify valid
samples, tail padding, and PCM synchronization in the final AAC track: a correct source WAV does
not prove that the encoded track is correct.

# User projects and public interfaces

English | [简体中文](project_interface.zh-CN.md)

`mathcoffee init --workspace <new-directory>` creates `mathcoffee.json`, a blank
`authoring.json`, and project instructions. It refuses to overwrite an existing
directory, even an empty one. Inputs, imported per-sentence audio, and finished
outputs belong to the user's project. Runtimes, model weights, and plugin code
have separate locations; uninstalling the plugin does not remove user projects.

## Project configuration

`mathcoffee.json` uses `schema_version: 1` and the following fields:

| Field | Purpose |
|---|---|
| `title`, `brand` | The user's title and branding; the default brand is empty |
| `preset`, `style` | Preset ID and strict field overrides; `mathcoffee style` shows the resolved configuration and diff |
| `authoring` | Workspace-relative path to the single authoring source |
| `runtime` | Optional explicit `render_python`, `speech_python`, `node`, `browser_executable`, `model_path`, and `remotion_root` |
| `voice` | Synthesis provider: `qwen_mlx` or `kokoro`; mode: `synthesize`, `imported`, or `silent`; `index` is the workspace-relative imported-audio manifest |
| `music.enabled` | Whether to enable procedural background music; track tags, seed, levels, and related settings live in `style.music` |

Installed runtimes default to
`~/Library/Application Support/MathCoffee/runtimes/<version>/`. Browser, engine,
and model caches live under `~/Library/Caches/MathCoffee/`. Tests and managed
deployments can choose dedicated locations with `MATHCOFFEE_DATA_HOME` and
`MATHCOFFEE_CACHE_HOME`. Project `runtime` values override the global
`runtime.json`. The launcher can select an installed core interpreter with
`MATHCOFFEE_PYTHON`.

Without `--execute`, `setup` only returns a plan. Execution uses separate
environments and installation receipts with source identities. A failed attempt
is retained, and the same inputs can resume unfinished steps. An existing
environment not owned by that receipt is not synchronized. Models are downloaded
separately, and production synthesis runs offline. `doctor` checks declared
versions and paths; it does not hash the entire model by default.

## Authoring v1

The canonical structure is
`schema_version / episode / title / brief / math_states / actions / scenes`.
Each scene has a stable `id`, an audience-facing title, and `sentences`. Each
sentence has a stable `id` and one original `text`, with optional `screen_text`,
`formula`, `visual`, `state_ref`, `action_refs`, and `duration_seconds`.
Legacy `chapters/cues` are normalized at the boundary. Mixed structures and silent
changes to IDs or text are rejected.

- `brief` records the audience, main question, assumptions, mathematical scope,
  and authorized external sources.
- `math_states` maps stable IDs to finite JSON states. Diagrams, numbers, and
  formulas should refer to the same mathematical source.
- Standard visuals support text, formulas, vectors, points, polylines,
  comparisons, state readouts, emphasis, summaries, and references. Parameters
  are defined by `components.referenced_visual/build_visual`; unknown types are
  rejected.
- The standard `actions` mode only registers `semantic_anchor` declarations.
  Implement actual movement or deformation in a project-local `scene_module`
  and record action execution in the rendered scene. A planned event is not
  evidence that an action occurred.
- `figure_label_registry` may be declared on the authoring source or a sentence.
  It propagates to normalization and actual TTS requests, preserving letters,
  subscripts, and primes. Text checks do not prove audible pronunciation.

Planning derives `build/plan.json`; voice requests and sentence windows derive
from that same source. Internal caption text matches the original narration;
the style determines whether it is burned into the video. Actual PCM determines
speech activity windows. Picture windows are rounded up to the frame grid while
preserving pauses. Narration that exceeds an estimated budget extends the shot;
it is not truncated or sped up.

An imported-audio manifest has this form:

```json
{"cues":[{"id":"...","text":"original text","path":"voice/cue.wav","sha256":"..."}]}
```

It must cover every sentence in the original order, with paths inside the
workspace. Audio must be mono PCM16/24/32 WAV. The pipeline measures real samples
and activity windows and rejects missing, truncated, silent, hash-mismatched,
or transcript-mismatched recordings. These checks do not establish that the
recording was read correctly.

## Builds, recovery, and review

`preview` produces a low-resolution draft; `render --quality final` produces the
high-resolution version. `resume` only reuses steps whose identities and output
hashes match. Changes to narration, state, style, PCM, dependencies, or
implementation produce a new build identity, while retaining previous outputs.
Each scene depends on its own sentence windows, referenced states/actions, and
actual rendering code, so an unrelated chapter change need not rerender the
entire video.

Each build records the schedule, renderer v1 timeline, display manifest, media,
commands, and source/output hashes. Final-container verification covers complete
video-frame decoding and PTS, the actual audio-track clock, AAC synchronization
against the premix, and declared caption windows. The verification receipt states
its scope. Silent output must explicitly select `silent`; it is never reported
as having passed voice acceptance.

Final rendering reads `reviews.json` for the matching build identity. After a
real visual review, set `draft_visual: approved` and `reviewer`, and retain the
exact `reviewed_output_sha256`. There is no CLI force-bypass option. Mathematical,
narrative, listening, style, and audience-understanding reviews remain separate;
approving draft visuals does not complete those other gates.

The CLI returns JSON by default. Success exits with 0, input/execution blocks
with 2, and incomplete authoring with 3. A `doctor` result of `setup_required` is
a structured diagnosis, and planning remains available. Read JSON `status/checks`
instead of inferring production readiness from the exit code alone.

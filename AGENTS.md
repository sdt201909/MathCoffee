English | [简体中文](AGENTS.zh-CN.md)

# MathCoffee: working agreements for agents

This is the MathCoffee video production framework. Read the [documentation index](docs/README.md)
and [production workflow](docs/production_workflow.md) first, then the current episode's production
plan, mathematical notes, narration and delivery records. Installation and available commands are
in the root [README](README.md). Historical episode documents do not replace global requirements.

## Starting a task

- Check `git status --short`, the relevant scripts and output directories first. A local production
  workspace may contain many untracked episode files; untracked does not mean disposable. Preserve
  existing user changes. Do not reset, overwrite or reorganize unrelated episodes.
- Turn the user's objective into an episode brief: audience, question, mathematical scope, narrative
  requirements, delivery specifications, permitted external services and authorized actions. State
  reasonable assumptions for noncritical missing preferences and continue independent work.
- Do not ask again for production, installation or cleanup already authorized. Report new costs,
  accounts, persistent credentials, external text transfers or explicit legal acceptance first.
  Never read secrets, call paid APIs, clone real people's voices or publish autonomously. Commits,
  pushes and replacement of published masters must also be within the current authorization.
- Give each file or module a single writing agent. Independent reviews and media checks may run
  concurrently. Avoid simultaneous edits to a source file; freeze dependencies during rendering
  and reassess invalidated clips after any change.

## Environments and engines

- A local production checkout may have an existing Python 3.13 / Manim `.venv` managed by `uv.lock`
  and a separate Python 3.12 / Kokoro `.venv-kokoro`. The Qwen speech runtime also uses an independent
  Python 3.12 environment. Installed plugins keep their runtimes outside the installation directory.
  Do not mix environments or upgrade historical dependencies just to run an episode. New speech
  backends need their own environment and a replaceable provider.
- Bare `make` defaults to `help`; it does not install or render. Specify a target for inspection or
  daily production. Prefer verified existing interpreters and episode entry points. Rendering is
  not a free diagnostic check.
- Manim handles computable mathematical state, rigorous geometry and continuous transformations.
  Remotion handles narrative layout, shot arrangement, information display and clip composition.
  Both share authoring data and a timeline; do not maintain separate facts or subtitle text.
- Renderer inputs, outputs, pinned versions and available CLI commands are defined by the
  [dual-engine contract](docs/engine_integration.md). Direct Manim invocations must explicitly select
  the project configuration. Reuse an episode's isolated configuration where present. Do not use a
  new engine as a reason to remake published work.

## Content, voices and assets

- Use one authoring source per episode, with stable scene, sentence and event IDs. Derive narration,
  captions and scene plans from it. Actual speech determines sentence windows; mathematical visuals,
  props and replays read the same state or event records.
- State assumptions, approximations and counterexample boundaries. Model values, geometry and
  formulas must come from shared calculations. Narrative replays must not introduce new key
  actions. Independent review checks derivations and causality, not just wording.
- Finished videos address channel viewers. Review the argument as “question, established result,
  remaining obstacle, why the next tool is needed.” Technical tests do not establish audience
  understanding. Narration, captions and visible copy must not contain project, version, engine,
  generation, debugging, acceptance, path, reproduction or internal workflow details; keep those
  in engineering documents. Endings contain only the conclusion, a return to the opening question,
  viewer-readable academic references and a natural channel sign-off. Do not move internal copy
  into the main content instead. See the [audience contract](docs/audience_contract.md) for declared
  display text, automated checks and the limits of listening evidence.
- Pronunciation corrections retain the original text, normalized text, dictionary version, matched
  context and model input. Spoken diagram names must match visible labels: A/B/C are English
  letters, never substitutes such as 甲/乙/丙. Preserve subscripts, primes and letter case. Captions
  retain the diagram glyphs; TTS may audibly expand a label, such as “A subscript one,” with an
  auditable record. Validate label order before synthesis and review actual pronunciation afterward;
  input text or forced alignment alone does not prove correct pronunciation. Evaluate gentle,
  relaxed or emotional delivery with real samples. Slowing speech does not establish a better
  voice. Test Chinese polyphonic characters and same-voice Chinese/English mixing separately.
  Explicitly record when listening has not occurred; see the [voice pipeline](docs/voice_pipeline.md).
- Record asset authors or sources, licenses, intended uses and versions or hashes. Unknown licensing
  does not imply permission. Select music deterministically from theme, mood, section and rhythm,
  retain the selection rationale and yield to narration. Silence is valid when no suitable licensed
  track exists; do not claim a rich catalog that is not available.

## Acceptance and delivery

- Review a complete low-resolution video before a final high-resolution render. Inspect actual
  encoded intermediate action, occlusion, text and subtitle safe areas, arrow endpoints,
  mathematical state and audiovisual anchors. First and last screenshots are insufficient.
- After narration or visible-copy revisions, first review representative continuous passages across
  chapter boundaries, then the whole video. Check every sentence and visual from the last main
  passage to black against the audience contract, and ensure old endings have not returned through
  voice or caption caches. Record automated text checks, technical acceptance, argument continuity
  review and actual listening separately; none substitutes for another.
- Verify the final container's actual dimensions, frame rate, frame count or timestamps, audio
  tracks, duration, subtitle bounds and audio synchronization. Save source and output hashes,
  commands, dependency versions and test results. A correct source WAV does not prove that the
  encoded audio track is correct.
- Test the actual changes and compatibility boundaries. Do not repeat full-library rendering after
  effective checks pass without a reason. Distinguish automated verification, visual sampling,
  human listening and unrun checks. Do not describe sampling as a second-by-second human review.
- Delivery reports include absolute output paths, specifications, sizes, hashes and limitations.
  Report a Library ID only after a tool confirms a successful save. A local path, Library save,
  chat attachment and platform publication are different outcomes.

## Recoverable cleanup

- `media/` is ignored by Git but contains final videos, voices, timelines and acceptance evidence.
  Never clear the entire directory.
- Clean regenerable intermediates only within the user-authorized episodes and files. First list
  original paths, sizes, hashes, dependencies and retention decisions; then use a supported system
  Trash interface and record the actual recovery location.
- Retain published masters, final covers, delivered previews, source, authoring, captions, necessary
  assets or voices, manifests and validation records. Retain high-resolution chapter sources as
  required by the episode's reproduction plan. Do not clean unrelated episodes or necessary shared
  caches.
- If Trash is unavailable or permissions are insufficient, stop the affected moves and report the
  issue. Do not fall back to permanent deletion with `rm`, empty Trash or delete Library copies.
  Recheck retained files after moving, explain recovery steps and conflict handling, and do not
  imply that moving to Trash immediately frees disk space.

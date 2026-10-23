English | [简体中文](production_workflow.zh-CN.md)

# From a production brief to a verified video

Use this workflow for a new video or an explicitly authorized revision. Published work retains its
own authoring source, dependencies, and acceptance evidence; an engine or voice upgrade does not
automatically authorize a remake. See [AGENTS.md](../AGENTS.md) for operating boundaries.

## 1. Establish the brief

Inspect workspace changes, existing environments, related episodes, and reusable assets first.
Keep the task's constraints in one `docs/<episode>_production_plan.md`; do not maintain several
progress documents containing the same information.

The brief must identify the audience, the question being answered, required prior knowledge,
mathematical and narrative scope, target duration and aspect ratio, deliverables, authorized external
sources, and any publication or remake of older episodes explicitly outside this task. Target
duration controls the argument; repeated explanations must not be added merely to fill it.

Assign stable IDs to chapters, shots, narration sentences, events, and assets. Prefer the episode's
existing authoring structure. For a new structure, validate required fields, unique IDs, complete
references, and nonnegative times before creating derived copies. The README is the entry point,
the episode plan guides creation, machine manifests hold precise data, and acceptance reports record
actual measurements.

## 2. Review the argument and choose the presentation

Complete the narration and scene plan before independent mathematical and narrative review. Record
definitions, assumptions, derivations, approximations, and applicability limits in the mathematical
notes. Cite verifiable primary sources with exact references and access dates. Distinguish invented
teaching values, random simulations, and claims about reality; preserve seeds and parameters for
random processes.

Narrative review checks character motivation, information available at the time, causal order, and
fairly presented evidence. Replays read the original event record; they must not invent a new
action. Displayed numbers, plots, geometric positions, and state relationships come from a shared
model. Visual interpolation must not fabricate a mathematical process.

Follow actual playback order and ask what the audience is solving, what has been established, what
obstacle remains, and why the next concept is needed. Transitions must follow from the preceding
observation or reasoning, rather than merely announce another concept. Remove technical digressions
that do not advance the main question, then supply missing reasoning. Chapter count and duration do
not justify repetition. Record breakpoints, timestamps, revision reasons, and reviews of
representative continuous passages across chapters. Technical tests do not replace this review.
See the [audience contract](audience_contract.md) for viewer-facing content, endings, declared
display text, and automated checks.

Manim handles geometry, mathematical transformations, and computational visualization. Remotion
handles narrative layout, split screens, information layers, and shot sequencing. Choose each
engine according to the passage's needs; do not replace reliable modules merely to use a new tool.
When both engines are needed, verify their interface on a short sample before expanding the film;
see the [engine contract](engine_integration.md).

## 3. Prepare assets, voice, and music

Place resources in the episode's namespace and record dependencies when reusing shared components.
Metadata for each external or generated asset must answer the following questions. Existing
manifest fields may be reused; do not create a second list with synonymous fields.

| Asset information | Evidence to preserve |
|---|---|
| Identity and use | Stable ID, local relative path, version/hash, episode, shot, or passage |
| Source and rights | Author, source link or original generation script, license text/link, acquisition date, attribution requirements, and usage restrictions |
| Rebuild conditions | Generation parameters, seeds, tool/model versions; retain irreplaceable originals |
| Media specifications | Image size/transparency/fonts; audio sample rate/channels/duration; video dimensions/frame rate/audio tracks |

Only authorized owned assets, original project assets, or clearly licensed materials may appear in
the film. Online music with unknown rights is not a publishable placeholder. Code drawing is
appropriate for native vector visuals; do not describe it as generated illustration.

Start voice work with representative short samples covering Chinese polyphonic characters,
numbers, spoken formulas, names, English words, and Chinese/English mixing within one sentence.
Preserve the original Chinese/English text. The provider's preprocessing derives separate numeric
expansions, pronunciation aliases, and context-dictionary substitutions, recording each match.
Pronunciation fixes must not silently change subtitle meaning. Dictionaries need positive,
negative, and ambiguous-context tests. Diagram labels retain their identity across picture,
narration, subtitles, and model input: read letter names as letters, rather than replacing A/B/C
with 甲/乙/丙. Subscripts and primes may have explicit spoken expansions while subtitles preserve
the original glyphs. Label-sequence checks must prevent renaming A, losing subscripts, or duplicating
labels. Actual letter pronunciation still requires listening; see the diagram-label rules in the
voice pipeline.

For every voice generation, record the provider, model source/revision, speaker, style instruction,
seed when supported, normalized input, sample rate, and output hash. Evaluate naturalness, a gentle
or languid style, emotion, and pronunciation separately. Slower delivery changes pacing; it does
not prove a better timbre or expression. Automated phoneme checks also do not replace listening.
See the [voice pipeline](voice_pipeline.md) for actual capabilities, environment isolation, and
examples.

Choose music for each passage's needs; silence is acceptable. In addition to source and license,
track metadata records theme/mood tags, rhythm or BPM, usable sections, looping conditions,
suggested gain, and fades. Deterministic selection records the rule, candidates, selected track,
and seed. Disclose a limited catalog instead of presenting speed variants of one asset as a rich
library. During narration, duck the music and inspect sentence entrances and exits, chapter cuts,
low-frequency masking, loudness, and true peaks. Ducking follows measured sentence windows or
waveforms, rather than estimated character counts. Stylistic suitability and permission to use a
track are separate requirements.

## 4. Freeze the timeline and clip boundaries

Measure sentence activity from real audio, then derive subtitles, visual anchors, and chapter
lengths. Allow adequate pauses, diagram-reading time, and formula holds. If narration exceeds its
window, revise the script or shot; do not silently cut final syllables or arbitrarily accelerate
the whole passage. Subtitle display text and spoken content must retain the same meaning. Internal
TTS phonemes and pronunciation substitutions are not audience text. Production records, versions,
tools, acceptance details, and reproduction instructions belong only in engineering documents.
Export display text from the same source used by the renderer, covering auxiliary labels and end
cards as well as narration. Bind revised narration, subtitles, and display manifests to the new
text so cache reuse cannot bring back an old ending.

Both renderers share one production timeline. Each handoff must state the following; exact fields,
defaults, and validators are defined by the [engine contract](engine_integration.md):

- Clip ID, renderer, input/output paths, source hashes, and reproducible commands.
- Dimensions, rational frame rate, actual frame count, in/out points, and corresponding global
  times; specify whether interval endpoints are inclusive.
- Audio presence and ownership, sample rate, and channels; whether subtitles are separate or burned
  in, preventing duplicate captions or duplicate mixing.
- Scaling/cropping, subtitle safe areas, first/last frames, and transition handles; do not silently
  stretch the aspect ratio or change playback speed.

Production time may be quantized to the project's frame grid, but measured audio activity retains
its precision. Do not concatenate integer frames from different frame rates directly, or treat a
filename containing `1080p60` as proof of media specifications. Freeze inputs during long production
renders. Before reusing clips, verify source and output hashes; changed dependencies invalidate
previous acceptance.

## 5. Review the draft before the final render

Run the episode's applicable mathematical/state, dictionary, contract, and layout checks, then render
the complete intended scope at draft quality. Inspect actual encoded frames, including the start
and end, intermediate stages of key actions, transitions, the longest text, and subtitle boundaries.
Review replays, state resets, arrows, and occlusions separately where relevant. Record scene/frame
positions, source hashes, findings, and fixes. Do not mark unexamined scenes as accepted.

Produce the final version only after the draft picture and audiovisual anchors pass review. Final
quality requires checking layout changes as well as the container with its final burned captions
and mix. Reviewing only an uncaptioned source clip or the subtitle layer is insufficient.

| Acceptance subject | Required checks |
|---|---|
| Data and logic | Authoring references, state invariants, mathematical results, narrative evidence, and replay consistency |
| Audience and argument | Continuous progress on the main question, causal connections across chapters, declared display text; only audience content from the last body passage to black |
| Picture | Actual dimensions, frame rate, frame count, and timestamps; text, motion, formulas, arrows, occlusion, and safe areas |
| Subtitles | Correspondence to narration, activity windows, first/last frames and gaps, duplicate burning, Chinese/English readability |
| Audio | Actual track and sample specifications, complete sentences, encoded synchronization, loudness/true peaks, and music ducking |
| Reproducibility | Input/output hashes, versions, commands, music selection and synthesis parameters, failures, and checks not run |

Full decoding, caption pixel sampling, and waveform correlation each have limits. Report their
actual scope separately; they do not prove pronunciation accuracy or audience understanding. When
shared modules change, check the callers actually affected. Do not rerender the historical library
for a documentation edit or a local example.

Review the ending's audio, subtitles, and picture together, from the final body passage through the
last black frame. Academic references may remain, but project explanations, engines, internal
production language, and acceptance language must not appear anywhere in the film. Explicitly state
when actual listening has not been performed.

## 6. Deliver and clean up recoverably

The delivery record lists real video/cover paths, duration, resolution, frame rate, size, hashes,
narration/subtitle policy, test evidence, and checks not run. Preserve derived specifications
separately and protect published masters. For Library saves, report only entries whose successful
save has been confirmed by a tool. Attachment size limits do not invalidate a local film or imply
that it has been published to a platform.

Cleanup is a separate, authorized operation. `media/` contains assets that must be retained for the
long term; neither its name nor Git ignore rules authorize bulk deletion. First prepare candidate
and retention lists, check shared references, symlinks, and path ownership, and record each original
path, size, SHA-256, and the total size. Retain uncertain items and explain why.

Typical candidates include the episode's temporary fragments/isolated caches, draft previews,
temporary QA images, rebuildable caption layers, clean temporary masters explicitly no longer
needed, and canceled transcodes. Retain the final video/cover/delivered samples, source code,
authoring, narration text, subtitles, necessary original assets and voice, timelines, verification
reports, and cleanup manifests. Whether to keep high-resolution chapter sources and per-sentence
voice caches depends on the episode's reproduction cost and plan; do not apply a blanket rule.

Use the system Trash interface and record the actual recovery location. A recovery package, if
created first, retains original relative paths. Stop and report failed moves; do not fall back to
permanent deletion. Afterwards, verify retained files' sizes/hashes and the deliverable's
readability. Report the number and total size of moved files without claiming that disk space has
been released.

Before recovery, verify the manifest and hashes, and check whether original paths already exist.
Do not overwrite newer versions. Restoring a recovery package from Trash does not necessarily merge
its contents into the original directories; restore items according to the manifest. If cleanup
removed intermediate media referenced by historical acceptance, restore or rebuild it before
rerunning checks; a missing file is not evidence that the original acceptance failed.

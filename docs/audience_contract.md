English | [简体中文](audience_contract.zh-CN.md)

# Audience contract: argument and displayed text

A MathCoffee film answers a mathematical question its viewers are asking. Production records serve
the production team and belong in planning, review, and delivery documents. Their accuracy, detail,
or passing test status does not make them narration, subtitles, or on-screen content. This contract
covers the channel's content films. A film whose actual subject is production technology must first
define its audience and teaching purpose in the episode brief, then adjust the checks to that
purpose. Do not hide findings behind automatic exemption fields.

## Let the question create the need for a tool

Follow actual playback order and answer, passage by passage: what are viewers solving, what have
they established, what step is missing, and why does the next tool address that obstacle? Record
the answers in the episode plan or review notes; do not mechanically recite these four questions
to viewers. Show an observable difference, failure, or need before introducing the definition and
reasoning that explain it. Remove or combine passages that do not advance the main question.
Neither chapter count nor target duration justifies repeating an explanation.

For chapter transitions, check whether the preceding result actually supplies the next passage's
starting point. An announcement such as “next, we introduce…” is not a causal connection. A
representative continuous sample must cover a real conceptual transition, rather than assemble
the most attractive clips from each chapter. Record timestamps, original lines, conditions not yet
known to the viewer, revised connections, and actual dynamic picture. Technical tests,
mathematical review, argument-continuity review, audiovisual sampling, and human listening are
separate evidence and must be reported separately. No automated PASS proves audience understanding.

## Audience boundaries throughout the film and ending

Narration, subtitles, titles, figure captions, numeric explanations, formula annotations, reference
cards, and covers are all audience text. Do not insert project paths, version numbers, engines or
voice models, generation processes, debugging, acceptance details, reproduction commands, file
hashes, engineering handoff, or internal production workflow into the film or ending. Necessary
license attribution follows the asset rules. Present academic references using viewer-readable
authors, titles, years, and necessary source details; a link to “project notes” or “production
records” does not replace a reference.

Review the ending from the final body passage through the last black frame. The conclusion returns
to the opening question, mathematical limits explain where the result applies, references enable
further reading, and the channel closing is natural and concise. Do not move internal language
from the ending into the body. Changes to body text require updating the whole affected narration
passage, sentence windows, subtitles, and display text. Cache reuse must not restore an old ending.
Preserve complete trailing speech and the actual black frame; do not abruptly cut audio to remove
an old sentence.

Terms such as “generated subspace,” “verify the equality,” “continuous version,” and “fluid
computation in engineering” may be valid mathematical content. The checker uses contextual rules
instead of banning the words themselves. Editorial judgment is still required for missed findings
and false positives.

## Explicit display-text manifest

Each episode retains an `audience_display_manifest.json`, exported from the same text source used
by the renderer. Scanning only narration in authoring is insufficient: helper functions, animation
targets, and end cards may contain additional hard-coded text. The following is a machine interface;
paths and hashes are internal information and are not displayed to viewers:

```json
{
  "schema_version": 1,
  "episode": "episode_id",
  "authoring_sha256": "SHA-256 of the complete authoring file",
  "coverage": {"scene_ids": ["opening", "closing"], "declared_complete": true},
  "entries": [
    {"id": "opening.question", "scene_id": "opening", "kind": "heading",
     "text": "What is this velocity graph still missing?", "cue_ids": ["opening_01"]},
    {"id": "closing.brand", "scene_id": "closing", "kind": "brand",
     "text": "MathCoffee · See you next time", "cue_ids": ["closing_01"]}
  ],
  "renderer_sources": [{"path": "scenes/episode.py", "sha256": "file SHA-256"}],
  "metadata": {"description": "Internal generation and review record; not displayed text"}
}
```

Entry IDs are unique; `scene_id` and optional `cue_ids` must resolve in authoring. `kind` is
`heading`, `label`, `formula`, `reference`, or `brand`. Register at least one genuinely displayed
entry per chapter. A special chapter containing narration but no on-screen text requires an
explicit contract adjustment and explanation; do not invent invisible text to satisfy coverage.
Register dynamic text after formatting, including animation targets. Source hashes bind every
renderer module participating in display text. Declared chapter coverage does not prove that the
encoded frames contain no unregistered text. Actual renders must still be compared with display
receipts and encoded picture.

The real Manim construction path may use `dry_run` / `skip_animations` to export an initial display
manifest, then record actual entries during rendering for comparison. `Text`, `MathTex`, labels
created by helpers, animation targets, and text after `become` are all in scope. Scanning only the
last frame misses intermediate text. Numeric updaters may record formatting rules and measured
values, but “dynamic label” is not an exemption for Chinese explanatory text.

## Check entry points and evidence limits

Check narration first. Once both the timeline and display manifest are available, run the complete
declared-surface check:

```sh
.venv/bin/python scripts/check_audience_text.py \
  --authoring assets/episode_authoring.json \
  --report media/reports/episode/audience/authoring.json

.venv/bin/python scripts/check_audience_text.py \
  --authoring assets/episode_authoring.json \
  --display-manifest media/episode/audience_display_manifest.json \
  --timeline media/episode/timeline.json \
  --require-complete --report media/reports/episode/audience/complete.json
```

The checker reads only authoring titles, chapter titles, sentence text, and formulas; display
manifest `entries[].text`; and timeline sentence `caption` values and their consistency with the
body. It does not recursively scan internal `scope`, `review`, `question`, `result`, file paths,
or other metadata. If an internal field is actually displayed, register it as a display entry.
Subtitles may differ in whitespace or line breaks, but must not silently omit or reorder sentences
or substitute an older script.

`BLOCKED` means a rule matched, a source is stale, or structure/subtitles are inconsistent.
`SCOPED_TEXT_PASS` means only that the supplied input scope has no findings.
`DECLARED_SURFACES_TEXT_PASS` means the complete declared-surface check passed. Even this last status
does not establish understanding, pronunciation accuracy, or acceptance of all picture text.
`--require-complete` rejects a limited check missing a display manifest or timeline. Exit codes are
0 for a passed check, 1 for a blocked check, and 2 for unreadable/unparseable input. For a
representative sample of complete chapters, explicitly use `--allow-scene-subset`; sentences must
remain complete and follow authoring order. Do not use that option for the full production film.
The report records the chapters actually selected.

Renderers may import `check_text(text, location=..., channel=...)` to check real text at the point of
use, or call `check_audience(authoring, display_manifest=..., timeline=...,
authoring_sha256=..., root=..., allow_scene_subset=False)`. Before final packaging, recheck input
hashes for the manifest and timeline. Preserve argument review and the picture/audio review from
the final body passage to black as separate records.

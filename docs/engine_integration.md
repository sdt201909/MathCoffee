English | [简体中文](engine_integration.zh-CN.md)

# A shared timeline for Manim and Remotion

Manim handles computable mathematical state, geometry, and continuous transformations. Remotion
handles information layout, shots, and clip sequencing. Both read the same authoring data and
measured voice timing; neither maintains a second subtitle script. The unified CLI derives the
timeline from [Authoring v1](project_interface.md), and shared components read the same resolved
style. Manim draws the mathematical subject; Remotion draws titles, branding, and narration
captions when enabled, avoiding duplicate text.

The Python contract is [renderer_contract.py](../src/mathcoffee/renderer_contract.py), and the
JavaScript contract is [schema.ts](../engines/remotion/src/schema.ts). The base contract allows even
pixel dimensions; the current general compositions support landscape 16:9 and portrait 9:16.

| Field | Constraint |
|---|---|
| `schema_version` | Integer 1 |
| `width/height/fps/duration_frames` | Even dimensions, integer frame rate from 1–120, positive integer total frame count |
| `clips[]` | Stable ID, renderer, relative asset path/SHA-256, global start frame, source in-frame, length |
| `captions[]` | Original text, stable ID, global start/end frames |
| `audio` | One premix by default: 48 kHz stereo, exact sample count and SHA-256; null is allowed for explicit silent use |
| `qa.anchor_frames` | Optional two-frame measurement flashes, excluded from production audience content |

Intervals are `[start, end)`, sorted by time, nonoverlapping, and contained within the film. Source
clip audio is muted; narration comes only from the premix, and captions are burned only in the
final composition layer. v1 does not represent 29.97 fps and must not silently interpret it as 30.
Captions may be empty for a version without narration subtitles; necessary diagram labels and
formulas remain part of the scene. Optional `style` carries resolved colors, fonts, layout, and
caption policy; legacy v1 timelines without style remain readable. The portrait candidate preset
omits burned narration subtitles by default; landscape configuration is independent. See the
[candidate style baseline](style_baseline.md).

Each render exposes only a dedicated `public/` asset directory. URLs, absolute paths, parent paths,
and escaping symlinks are rejected. Preflight checks actual video dimensions, frame rate, source
frame spans, premix sample count, and all media hashes. Passing preflight does not establish
mathematical correctness, pronunciation accuracy, audience understanding, or a complete audiovisual
review.

## Run

Exact JavaScript dependencies are locked by `engines/remotion/package-lock.json`. Manim uses a
separate Python 3.13 environment and `uv.lock`; installing the auxiliary engine does not upgrade
historical dependencies.

For an installed package, use `mathcoffee preview --workspace <user-project>` to create a draft,
then `verify`, `status`, and `resume` to check or recover it. Runtime configuration resolves the
rendering Python, Node, browser, and separate Remotion engine location. The plugin installation
stays read-only. Framework rendering does not silently download a browser; a missing browser
produces a preparation requirement. Runtime preparation requires explicit `setup` execution; see
the root [README](../README.md).

The following source-checkout calls remain available:

```sh
make remotion-setup
make remotion-check
make remotion-browser

.venv/bin/python scripts/validate_renderer_timeline.py \
  /absolute/path/timeline.json --assets /absolute/path/public

node engines/remotion/render.mjs \
  --props /absolute/path/timeline.json \
  --public-dir /absolute/path/public --output /absolute/path/new-film.mp4
```

Portrait output uses the separate `render-shorts.mjs` entry and `shorts` data fields; see the
[engine README](../engines/remotion/README.md). Outputs require new paths. `--no-audio` is an explicit
silent mode; the default production entry requires a premix. All animation follows frame numbers,
not wall-clock time.

Render receipts record hashes for inputs, code, dependencies, browser, and output, and recheck that
inputs stayed unchanged during execution. Changes to narration, style, state, voice, or
implementation identity preserve old builds but invalidate their use as acceptance evidence for
the current build. Final rendering requires the same identity's draft technical checks to pass,
plus a `reviews.json` from actual picture review bound to the film hash. There is no force bypass.
Mathematical, narrative, and actual listening reviews still require separate records.

The final container still needs full decoding, caption-boundary checks, encoded audio
synchronization, and intermediate-motion review. This repository does not contain technical
acceptance records from historical films. Passing framework tests is not evidence that an arbitrary
new film has passed acceptance.

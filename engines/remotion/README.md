English | [简体中文](README.zh-CN.md)

# Remotion composition engine

This directory provides reusable landscape and portrait composition entry points. Manim clips own
mathematical state and geometry; Remotion reads an integer-frame timeline and combines pictures,
captions and one premixed audio track. The repository contains no episode, narration, video or
model weights.

## Environment and installation

Node 24, npm and FFmpeg/ffprobe are required. Remotion 4.0.531, React 19.2.3 and TypeScript 5.9.3
are pinned. Use the lockfile; do not modify Python environments to prepare this engine.

For source development:

```sh
cd engines/remotion
npm ci --ignore-scripts --no-audit --no-fund --cache .npm-cache --registry https://registry.npmjs.org
npm run browser:ensure
npm run typecheck
npm test
```

For an installed plugin, prefer `mathcoffee setup --component render`; its explicit `--execute`
mode prepares an external engine cache rather than writing to the plugin directory. See the root
[installation guide](../../docs/installation.md).

Package installation downloads npm dependencies; `browser:ensure` prepares a local Chrome Headless
Shell. Prepare dependencies and the browser separately before production. Fonts come from the
system. The current baseline uses Chinese fonts on Apple Silicon Mac; other platforms need their
own checks of fallback fonts, layout and browser availability.

## Rendering

`MathCoffeeTimeline` is the 16:9 landscape entry; `MathCoffeeShorts` is the 9:16 portrait entry.
Input and output paths must be absolute. Each asset `file` is relative to a dedicated public-assets
directory.

```sh
node render.mjs \
  --props /absolute/path/timeline.json \
  --public-dir /absolute/path/dedicated-public \
  --output /absolute/path/new-landscape.mp4 \
  --browser-executable /absolute/path/chrome

node render-shorts.mjs \
  --props /absolute/path/portrait-timeline.json \
  --public-dir /absolute/path/dedicated-public \
  --output /absolute/path/new-portrait.mp4 \
  --browser-executable /absolute/path/chrome
```

The landscape script can omit the browser option and let Remotion locate or prepare a compatible
browser. The portrait script defaults to the Apple Silicon Chrome Headless Shell under
`node_modules/.remotion/`. Passing an explicit local executable pins the browser actually used;
the installed production CLI does so. Rendering and tests do not invoke cloud rendering.

Silent experiments require both `audio: null` and `--no-audio`; the flag refuses to discard a
declared mix. Portrait also supports `--no-captions` and `--still-frame N` to export a PNG to a new
path. Existing output files or receipts are protected from overwrite. Failed artifacts are retained
for diagnosis; retry with a new output path.

## Shared contract

[`src/schema.ts`](src/schema.ts) defines the base timeline:

- `schema_version: 1`, even dimensions, an integer frame rate from 1 to 120, and a positive integer
  total frame count.
- `clips`: stable `id`, `renderer`, `file`, `sha256`, `start_frame`, `source_in_frame` and
  `duration_frames`. Source dimensions and frame rate must match the output.
- `captions`: stable `id`, `text`, `start_frame` and `end_frame`.
- `audio`: the single stereo 48 kHz premix, whose `samples` cover the entire film exactly; source
  video clips are muted.
- `qa.anchor_frames`: optional test anchors that show a white patch for two frames.

Intervals are `[start, end)`, ordered and non-overlapping. URLs, absolute asset paths, parent
traversal, escaping symlinks and source-hash mismatches are rejected. A dedicated public directory
must contain only inputs authorized for this production. Never use the project root or a user home
directory as `public-dir`.

Both engines accept the resolved MathCoffee style. Colors, font stack, canvas, title and brand
regions, caption geometry and subtitle policy come from that shared configuration. Optional
`headers` provide the displayed titles and subtitles; no episode copy is invented by the renderer.
See the [dual-engine contract](../../docs/engine_integration.md).

For compatibility, a landscape v1 timeline without `style` fills the frame with clips, uses a dark
background in gaps and places captions at logical 1920×1080 coordinates
`x=64, y=950, width=1792, height=110`. Reserve that space in source geometry. This legacy mode adds
no default episode title, brand or body copy.

The portrait extension is in [`src/shorts-schema.ts`](src/shorts-schema.ts). `shorts` contains episode,
brand, series, title windows and optional ending, black tail and caption switch. Every displayed
string comes from input data. Legacy titles are limited to 16 characters, subtitles to 24 and
captions to two lines of 18 characters each; resolved styles instead use their configured layout
budgets. Default registration data is neutral scaffolding, not an episode. Registration placeholders
hide narration captions. Real input should set `show_captions` explicitly; omission retains the
legacy caption-visible behavior. MathCoffee's default shorts preset disables burned narration
captions, independently of the landscape preset.

## Receipts and validation limits

Render receipts record input, asset, source, dependency, browser and output identities, SHA-256
hashes and actual media parameters. Inputs are checked again after rendering. Both orientations
encode the complete original PCM premix once with native FFmpeg, copy the video stream without
re-encoding and verify the exact final container audio clock. Portrait also emits a display-text
manifest.

`npm test` checks contracts, path isolation, CLI behavior and output protection. It includes a small
native FFmpeg mux regression when FFmpeg/ffprobe are available. `npm run typecheck` checks types.
These tests do not launch a browser or establish that real pictures, fonts, readability,
pronunciation or whole-film audiovisual synchronization are acceptable. Delivery still requires
low-resolution review, final container and encoded-audio checks, and actual listening.

## Third-party dependencies

Lockfiles pin dependency versions; they do not replace dependency licenses. Remotion and other
components retain their own conditions; the project's [Apache-2.0 license](../../LICENSE) does not
replace them. Before plugin
redistribution, distinguish dependency installation from bundling and check the pinned versions'
notices and [Remotion documentation](https://www.remotion.dev/docs/license). This directory does not
configure accounts, license keys, cloud rendering, paid APIs or external asset services.

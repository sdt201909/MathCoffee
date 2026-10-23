# Implementation and acceptance status

English | [简体中文](implementation_status.zh-CN.md)

The community release is **v0.2.0-alpha.2** (Python `0.2.0a2`), with project source
licensed under [Apache-2.0](../LICENSE). A source release does not mean every
production stage has passed acceptance. This document distinguishes implemented
code, automated checks, real-media inspection, and the author's approval.
Third-party dependencies, models, fonts, and media retain their own terms; see
[dependencies](dependencies.md) and [third-party notices](../THIRD_PARTY_NOTICES.md).

## Implemented framework capabilities

| Area | Current implementation |
|---|---|
| Independent installation | A wheel with a CLI entry point includes read-only package resources, voice configuration, Remotion, and toolchain lock files; builds use a reviewed file allowlist |
| User workspaces | Installation, external runtimes/caches, and user work are separate; paths with spaces are supported, and initialization refuses to overwrite existing directories |
| Environment preparation | `setup` returns a plan by default; explicit execution separates Python 3.13 rendering and Python 3.12 speech, retaining identities and resumable installation receipts |
| Planning and authoring | `doctor/init/plan` work without models or rendering dependencies; Authoring v1 and explicit legacy adapters derive common requests and timelines |
| Style and branding | Portrait/landscape candidate presets, strict overrides, and recorded differences; colors, fonts, layout, holds, voice, music, and branding are configurable |
| Mathematical scenes and composition | Generic Manim components and Remotion share the resolved style, register displayed text, real bounds, and action anchors, and reject unknown components/actions instead of silently degrading |
| Voice and mixing | Local Qwen synthesis, per-sentence PCM import, and explicit silence; measured activity windows drive sentence timing and music ducking, with original text and normalization evidence retained |
| Builds and recovery | Hash-bound stage receipts, selective clip reuse, and retained failure evidence; changed dependencies or text prevent old outputs from being treated as current |
| Container verification | Complete frame decoding and timestamps, dimensions/FPS/frame count, actual audio-track clock and synchronization, declared caption windows, and output hashes |
| Two host packages | Separate Codex and Claude Code manifests/marketplaces share the setup, create, review, and revise skills and the same CLI |

A user project still supplies the topic's mathematical model, argument, and
properly licensed assets. Generic components do not prove arbitrary new topics
correct or invent teaching actions and claim they occurred. Presets remain
`pending_author_confirmation`; that label does not establish that a new work
matches the author's approved style.

## Recorded 0.2.0a1 baseline validation

The following evidence belongs to the **0.2.0a1 implementation candidate** before
the community release. It was collected on an existing Apple Silicon Mac using
separate, already installed environments. Historical production dependencies
were not upgraded. No episode code, media, or models were added to the repository.
Tests use generic components and generated fixtures.

| Validation | Recorded result and scope |
|---|---|
| Python core | 168 passed, covering workspaces/planning/style, CLI, package resources, components, recovery, contracts, and host package boundaries |
| Separate speech environment | 40 passed, covering input, pacing, voice consistency, and retakes; this does not imply approved audible quality |
| Separate voice QA environment | 4 passed, checking proxy-metric logic; this does not replace listening |
| Remotion | 25 Node tests and TypeScript checking passed, covering v1 compatibility, layout configuration, and input boundaries |
| Wheel smoke test | Initialization, planning, setup plans, and diagnosis completed outside the source tree in a core environment without rendering dependencies; read-only installation resources were unchanged |
| Codex host | The final candidate ZIP completed marketplace add, install/enable, and remove in isolated configuration; plugin files were unchanged during the workflow, and core/project hashes were unchanged after removal |
| Claude Code host | Manifests, package structure, and launcher passed automated checks; Claude Code was unavailable on the test machine, so actual host loading was not performed |

Installation smoke tests, host tests, and real rendering each bind to their own
artifact identity. A passing earlier wheel does not validate a later release
wheel. The baseline's local delivery report records the exact media, hashes,
and command logs; this repository does not carry local acceptance projects or
historical episodes. Release-specific changes require their own checks against
the new build, rather than relabeling this baseline as alpha.2 evidence.

The final baseline wheel ran in a separate core environment with no NumPy,
Manim, PyAV, or SoundFile installed. Rendering and speech used separately
configured existing environments. Two real, low-resolution samples were
produced outside the read-only installation: each was 22.8 seconds and 684 frames.
Portrait output was 540×960 at 30 fps with narration captions off by default;
landscape output was 960×540 at 30 fps with its own caption policy enabled.
Both passed complete decoding, timestamp checks, and synchronization of the final
AAC track against the original premix, with zero measured per-sentence offset.
The landscape sample additionally checked 591 declared active-caption frames.
The wheel rebuilt from the source distribution had the same hash as the direct
wheel build. All 78 resource hashes in the read-only installation stayed
unchanged. Resume reused the same build, and an unapproved final-render request
was rejected as expected.

Encoded intermediate frames and adjacent-scene transitions were sampled without
observed label/formula cropping. Actual listening, a human second-by-second
review, and the author's style approval were not performed. Sample topics,
voice files, complete video code, and raw receipts remain only in the local
acceptance project. They demonstrate the technical loop, not acceptance of a
complete new-topic video or a three-chapter longform film.

## Acceptance work still required

1. The author reviews both calibration videos' continuous reasoning, actual
   motion, and real audio before freezing the default preset version.
2. Install through both Codex and Claude Code and complete a new-topic portrait
   video in independent projects. Record mathematical, narrative, visual,
   listening, style, and technical acceptance separately. Structure checks do
   not replace an actual Claude installation.
3. Complete a new-topic landscape film with at least three chapters. Check
   continuity, voice consistency over the film, selective rerendering, and
   interrupted-build recovery. A short technical sample does not meet this gate.
4. Have an independent user work on a Mac without the original production
   environment. Verify dependency preparation, fonts, upgrades, and uninstallation,
   preserving projects and required caches. Reusing environments on the current
   machine is not evidence of a clean-Mac installation.
5. Keep third-party licensing and distribution review separate from the project's
   Apache-2.0 source license. Confirm the applicable terms for any models, fonts,
   music, browsers, and dependencies before redistributing them or their assets.

Final rendering is bound to the same build's passing draft technical result and
the hash of the visually reviewed draft. This gate is implemented, but cannot
sign the author's mathematical, style, or listening approval. Installation does
not automatically download models, upload narration, invoke paid services,
publish videos, or clean media. See the [roadmap](plugin_roadmap.md),
[interface](project_interface.md), [production workflow](production_workflow.md),
and [new-Mac installation guide](installation.md).

# Plugin roadmap and acceptance gates

English | [简体中文](plugin_roadmap.zh-CN.md)

The framework began with the `0.2.0a1` implementation candidate; the community
source release is `v0.2.0-alpha.2` (Python `0.2.0a2`) under
[Apache-2.0](../LICENSE). Track implemented code, automated validation, real-media
inspection, and human approval separately. A version number is not acceptance
evidence. Initial support targets Codex and Claude Code on Apple Silicon Mac,
with portrait videos before landscape longform. Conversation and editable
configuration control style; the first version has no visual configuration editor.

1. **Style baseline.** Two candidate presets, separate branding, and calibration
   criteria are implemented. The author's visual/listening approval is still
   pending. Do not freeze an approved style or inherit approval from historical
   episodes.
2. **Independent installation and authoring.** The CLI, package resources,
   workspaces, and Authoring v1 compiler are implemented. Installation artifacts
   have been checked outside the source tree without rendering dependencies;
   consult the [implementation status](implementation_status.md) for exact scope
   and artifact versions.
3. **Configurable components.** Manim mathematical components and Remotion share
   colors, fonts, layout, timing windows, and caption policy, with display
   manifests, measured bounds, and action anchors. A new topic still needs its
   own model and independent mathematical review.
4. **Portrait alpha.** Voice synthesis/imported PCM, measured sentence windows,
   scenes, mixing, drafts, recovery, and technical verification are connected,
   with separate host packages. Component tests cannot approve style, actual
   audible quality, or real Claude host loading.
5. **Landscape beta.** The same core supports multiple chapters, captions,
   formulas, selective rebuilds, and the final-render gate. Representative
   samples and full-film-scale verification are separate; a short clip is not
   acceptance of a longform delivery.
6. **Community maintenance and external trials.** Publish the framework source
   under its project license and invite contributions. Independent users must
   still complete production on Macs without the original project environment,
   checking upgrades/uninstallation, fonts, and voice capability. Third-party
   distribution terms remain separate from the source license and from technical
   acceptance. See [contributing](../CONTRIBUTING.md) and
   [installation](installation.md).

User work, complete episode code, and media stay in local user projects. The
repository contains only generic components, templates, and generated test
fixtures. Installing the plugin does not automatically download models, invoke
paid services, upload narration, publish videos, or clean user media.

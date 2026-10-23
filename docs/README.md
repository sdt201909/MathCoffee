# Framework documentation

English | [简体中文](README.zh-CN.md)

This repository contains MathCoffee's reusable production framework. It does not
include the channel's episode scenes, scripts, media, or delivery records.

| Document | Purpose |
|---|---|
| [Installation on a new Mac](installation.md) | System prerequisites, isolated runtimes, and first use |
| [Agent conventions](../AGENTS.md) | Workspace protection, isolated environments, review, and recoverable cleanup |
| [Production workflow](production_workflow.md) | From a brief to verifiable delivery |
| [Authoring and configuration interface](project_interface.md) | User workspaces, Authoring v1, CLI, and build recovery |
| [Candidate style baseline](style_baseline.md) | Portrait and landscape presets, semantic colors, pacing, and approval boundaries |
| [Audience contract](audience_contract.md) | The question chain, displayed text, and ending boundaries |
| [Dual-engine interface](engine_integration.md) | A shared timeline, media contracts, and renderer entry points |
| [Voice pipeline](voice_pipeline.md) | Local providers, pronunciation lexicons, measured sentence windows, and listening review |
| [Dependencies and licensing boundaries](dependencies.md) | Runtime locks, third-party notices, and outstanding reviews |
| [Implementation and acceptance status](implementation_status.md) | Implemented capabilities, validation scope, and remaining acceptance gates |
| [Plugin roadmap](plugin_roadmap.md) | Staged goals and release-readiness requirements |
| [Repository scope](repository_scope.md) | The file allowlist, history isolation, and future commits |
| [Website maintenance](website.md) | Bilingual pages, browser checks, release links, and GitHub Pages deployment |
| [Contributing](../CONTRIBUTING.md) | Community changes, checks, and review expectations |

For each video, create a brief and a single authoring source in a local project.
The mathematical explanation, narration, measured sentence windows, scenes, and
delivery records must share stable IDs. Names such as `episode` and `example` in
the documentation are placeholders supplied by the production task; the repository
does not contain a finished example video.

Start with the root [README](../README.md) and the installation guide, create a
separate user workspace, and then complete its authoring source. Framework code,
runtimes, model caches, and user work belong in separate locations. The plugin
installation directory is not a video project. The candidate presets still need
the author's visual and listening approval; installation or automated checks do
not complete that review.

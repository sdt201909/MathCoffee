English | [简体中文](THIRD_PARTY_NOTICES.zh-CN.md)

# Third-party notices

MathCoffee's original framework code and documentation are available under
[Apache License 2.0](LICENSE). The [NOTICE](NOTICE) records project attribution.
That license does not replace the terms of dependencies, model weights, fonts,
recordings, channel branding, or other assets.

The source repository and plugin archives contain framework source, configuration,
locks, documentation, and a MathCoffee wheel. They exclude installed dependency
environments, `node_modules`, browser/FFmpeg binaries, model weights, fonts,
recordings, video materials, and complete episode projects. Setup downloads selected
runtime packages from their upstream distributors after explicit execution.

| Component | Source and terms | How it is used |
|---|---|---|
| Manim 0.20.1 | [Manim Community, MIT](https://github.com/ManimCommunity/manim/blob/v0.20.1/LICENSE) | Installed separately into the render environment; no upstream runtime is vendored |
| Remotion 4.0.531 | [Remotion license and terms](https://www.remotion.dev/docs/license) | Separate npm installation; Remotion's usage and commercial terms must be reviewed for the user's circumstances |
| React and TypeScript | [React license](https://github.com/facebook/react/blob/main/LICENSE), [TypeScript license](https://github.com/microsoft/TypeScript/blob/main/LICENSE.txt) | Separate npm dependencies recorded in the engine lockfile |
| MLX-Audio 0.5.7 | [Upstream MIT license](https://github.com/Blaizzy/mlx-audio/blob/main/LICENSE); [preserved text](toolchains/speech/LICENSE-mlx-audio.txt) | Local speech adapter uses a separately installed runtime |
| Qwen3-TTS CustomVoice model | [Pinned model card](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice/blob/0c0e3051f131929182e2c023b9537f8b1c68adfe/README.md); [preserved Apache-2.0 text](toolchains/speech/LICENSE-Qwen3-TTS.txt) | Optional anonymous download from a fixed revision with file integrity verification; weights are not included |
| Optional speech/voice QA providers | [Provider notes](docs/voice_pipeline.md), [voice QA provenance](toolchains/voice_qa/README.md) | Separate environments/models; not automatically installed by the standard runtime helper |
| Python libraries | `uv.lock`, `toolchains/render/requirements.lock`, `toolchains/speech/requirements.lock` | Their own upstream licenses remain in force; environments are not distributed |
| Cairo, Pango, FFmpeg, TeX and fonts | Their respective system package/distribution terms | Installed or supplied by the user; no binaries or font files are included |

Apache-2.0 licensing of the framework does **not** mean every dependency is
Apache-2.0 or free for every commercial use. In particular, consult Remotion's
upstream terms before using it in a team, product, or commercial service. The
framework does not create a Remotion account, purchase a license, configure a
license key, accept additional terms, or enable cloud rendering.

Each external asset in a video needs its own source, author, license, intended use,
and version/hash record. Using this framework does not grant rights to the original
channel's episodes, logos, recordings, or somebody else's likeness or voice. Use
your own brand during initialization.

This file describes distribution boundaries and key notices, not a complete audit
of every transitive runtime dependency. Consult the exact installed versions and
upstream license files when redistributing dependencies. See
[dependency details](docs/dependencies.md) and the [contribution guide](CONTRIBUTING.md).

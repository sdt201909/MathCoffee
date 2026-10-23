English | [简体中文](dependencies.zh-CN.md)

# Dependencies and licensing boundaries

Original project code is licensed under [Apache-2.0](../LICENSE); see the root [NOTICE](../NOTICE)
and [README](../README.md). Third-party dependencies, models, fonts and assets retain their own
terms. Licensing for original code, attribution and plugin packaging is separate from third-party
permissions. Keeping upstream notices does not give the project ownership of its dependencies or assets.

| Component | Pinned by | Distribution scope |
|---|---|---|
| Python 3.13 / Manim 0.20.1 | `pyproject.toml`, `uv.lock` | Dependency declarations and locks; environments are excluded |
| Node 24 / Remotion 4.0.531 | Engine `package.json`, `package-lock.json` | Generic compositor source and locks; dependencies and browser are excluded |
| Local Qwen MLX speech | `toolchains/speech/requirements.lock`, model file manifest | Adapter code, downloader and upstream notices; weights are excluded |
| Voice consistency proxy | `toolchains/voice_qa/requirements.lock` | Optional tooling and pinned provenance; models are excluded |
| Science voice, pronunciation and procedural music settings | `src/mathcoffee/data/speech/`, `src/mathcoffee/data/audio/` | Generic JSON; recordings and finished videos are excluded |

Remotion has its own license terms; do not describe all dependencies as MIT-licensed. Before
redistributing a plugin, changing team usage or bundling dependencies, check the relevant pinned
version and [upstream terms](https://www.remotion.dev/docs/license). This framework does not configure
a license key, accept new terms, create an account or enable cloud rendering. Preserved speech
runtime notices are in `toolchains/speech/LICENSE-*`.

System fonts, TeX and FFmpeg are not bundled. Dependency locks provide precise sources and hashes,
not a complete licensing audit. Record the author, source, license and intended use of external
assets separately. Files with unknown permissions must not enter a distribution bundle.

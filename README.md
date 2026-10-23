English | [简体中文](README.zh-CN.md)

# MathCoffee · 知数咖啡厅

An agent-native toolkit for making mathematics videos locally with **Codex or
Claude Code**. Start from one authoring source; use Manim for mathematical scenes,
Remotion for composition, and measured narration for the shared timeline.

MathCoffee's default presets capture a question-driven narrative, semantic colors,
dark mathematical visuals, and local science narration. Bring your own channel
brand, topic, mathematical model, and licensed assets. Style and branding are
configured separately.

**Community Alpha: `v0.2.0-alpha.2`** (Python `0.2.0a2`). Original framework code
and documentation are [Apache-2.0 licensed](LICENSE). This is an early community
release: default style confirmation, human listening, actual Claude Code loading,
long-film acceptance, and an independent clean-Mac trial remain open. See the
[implementation status](docs/implementation_status.md) and [roadmap](docs/plugin_roadmap.md).

## Start on a new Mac

Initial target: **Apple Silicon Mac**. Use a macOS version currently supported by
Homebrew. First install Apple's Command Line Tools and [Homebrew](https://docs.brew.sh/Installation.html),
then download and extract the appropriate ZIP from
[Releases](https://github.com/sdt201909/MathCoffee/releases).
The ZIP contains the plugin, wheel, documentation, locks, and setup helper.
Do not use GitHub's automatically generated source archive as an installed plugin.

From the extracted plugin directory:

```sh
# Inspect the full setup plan. This does not install or download anything.
bash bin/setup-macos --profile full --with-tex --with-model

# Explicitly prepare the same selected components.
bash bin/setup-macos --profile full --with-tex --with-model --execute

bin/mathcoffee doctor --profile full
bin/mathcoffee init --workspace "$HOME/Movies/MyMathVideo" \
  --brand 'My channel' --title 'A question worth answering'
bin/mathcoffee plan --workspace "$HOME/Movies/MyMathVideo"
```

`plan` returns `incomplete` until you fill in the blank authoring template. It can
run without a model or rendering dependencies. Use `--profile core` for planning
only, or `--profile render` with your own recordings. `--with-model` explicitly
opts into a multi-gigabyte model download; `--with-tex` may invoke a standard macOS
administrator prompt. Existing dependencies are reused; the helper does not install
Homebrew, accept OS agreements, edit shell profiles, or clean your media.

The [installation guide](docs/installation.md) covers prerequisites, profiles,
manual setup, host installation, storage, recovery, and uninstall behavior. After
host installation, ask the agent to use MathCoffee to create a new video in your
own workspace. Plugins are distributed through these release packages; this is
not a listing in either host's official public plugin directory.

## Create and review

```sh
bin/mathcoffee voice --workspace "$HOME/Movies/MyMathVideo"              # plan only
bin/mathcoffee voice --workspace "$HOME/Movies/MyMathVideo" --generate   # local synthesis
bin/mathcoffee preview --workspace "$HOME/Movies/MyMathVideo"
bin/mathcoffee verify --workspace "$HOME/Movies/MyMathVideo" --quality draft
bin/mathcoffee status --workspace "$HOME/Movies/MyMathVideo"
bin/mathcoffee resume --workspace "$HOME/Movies/MyMathVideo" --quality draft
```

Complete mathematical and narrative review, listen to the actual audio, and
inspect the full low-resolution film before final rendering. The final-render gate
requires a visual review bound to that exact draft's identity and hash. Automatic
checks do not sign off mathematics, audience understanding, pronunciation, or style.
Outputs and failed attempts stay in your workspace, outside the plugin installation.

## Default styles

| Preset | Delivery | Narration captions |
|---|---|---|
| `mathcoffee-shorts@1` | 1080×1920, 60 fps | Off by default; labels, formulas and titles remain |
| `mathcoffee-longform@1` | 1920×1080, 60 fps | Separately configurable; on by default |

Both engines read one resolved style configuration: colors, fonts, layout, sizes,
pacing, narration, music, and brand. Overrides record their differences and identity.
There is no global three-minute limit and no silent speed-up or truncation to fit a budget.

The current local narration default is **Serena / science_female / full_text**,
with a Chinese science-video brief. Choose a supported local provider/voice or
import per-sentence PCM recordings. Recheck pronunciation and consistency after
changing a voice. No paid synthesis service or voice cloning is required.

See [configuration and authoring](docs/project_interface.md),
[style baseline](docs/style_baseline.md), and the [production workflow](docs/production_workflow.md).
Custom mathematical scenes can extend `SceneBase` in a user-owned workspace.
The framework does not prove arbitrary mathematics or supply a complete episode.

## Contribute

Community contributions are welcome: installation reports, new-topic validation,
style components, accessibility, provider adapters, documentation, and fixes.
Start with [CONTRIBUTING](CONTRIBUTING.md), [AGENTS](AGENTS.md), and the
[documentation index](docs/README.md). Keep episode code, recordings, assets,
models, environments, and delivery archives out of the source repository.

```sh
uv sync --locked --no-editable --extra render
make test-core
make test-speech            # separate Python 3.12 .venv-speech
make test-voice-qa          # optional independent .venv-voice-qa
make remotion-check
uv build --wheel --sdist
```

Bare `make` shows help. The build backend does not support editable installation;
use a wheel or `--no-editable`. Versions remain pinned to the tested rendering and
speech interfaces. Source export is protected by `repository-files.txt` and the
repository guard. The lightweight CI does not replace a clean-Mac media/voice test.

## License and dependency boundaries

[Apache License 2.0](LICENSE) covers the original framework code and documentation;
see [NOTICE](NOTICE) and [third-party notices](THIRD_PARTY_NOTICES.md).
Dependencies keep their own terms, **including Remotion's separate usage and
commercial license terms**. Model weights, fonts, browser binaries, and media are
not bundled. Using the framework does not grant rights to the original channel's
brand, episodes, recordings, or somebody else's likeness or voice.

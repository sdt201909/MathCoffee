English | [简体中文](installation.zh-CN.md)

# Install on an Apple Silicon Mac

Use the **complete Codex or Claude Code ZIP** from the
[GitHub release](https://github.com/sdt201909/MathCoffee/releases), not the automatic
source-code archive. Each ZIP contains one matching wheel, setup helper, host
catalog, common skills, licenses, and English/Chinese documentation. Compare the
ZIP's `shasum -a 256` output with its row in the release's `SHA256SUMS` before use.
Extract to a new directory. Paths containing spaces are supported.

This Alpha targets native Apple Silicon macOS. Use a version currently supported
by [Homebrew](https://docs.brew.sh/Installation.html); its current supported baseline
is macOS 15 or later. Intel/Rosetta, Windows, and Linux production runtimes are not
part of the initial support promise. Lightweight Linux CI checks planning and
contracts only.

## 1. Prepare the operating-system prerequisites once

On a blank Mac, open Terminal and run:

```sh
xcode-select --install
```

Complete Apple's installation dialog yourself, then install Homebrew using its
[official installation instructions](https://docs.brew.sh/Installation.html).
The helper can find native Homebrew at `/opt/homebrew` without changing a shell
profile. It does not install Xcode/Homebrew, handle administrator passwords, or
accept OS agreements for you. A full Xcode application is not required by this guide.

Install your preferred agent host separately and sign in there. MathCoffee does
not create host accounts, choose a subscription, or store host credentials.
Host authentication and how the host processes prompts follow that host's settings.

## 2. Choose a profile and inspect its plan

Run commands from the extracted plugin directory:

| Profile | Prepares | Appropriate use |
|---|---|---|
| `core` (default) | uv, Python 3.13, isolated MathCoffee core | Brief, authoring, configuration, model-free planning |
| `render` | Core plus Node 24, Cairo/Pango, pkgconf, FFmpeg, locked Manim/Remotion, browser | Render using imported recordings or explicit silence |
| `full` | Render plus the separate Python 3.12 / MLX-Audio environment | Local Serena narration after model preparation |

```sh
bash bin/setup-macos --profile core
bash bin/setup-macos --profile render --with-tex
bash bin/setup-macos --profile full --with-tex --with-model
```

These commands only inspect local state and print JSON plans. They do not install,
download, or create managed directories. A blank machine with no usable Python
prints a smaller frontend plan with the prerequisite steps instead.

- `--with-tex` explicitly permits installing missing `mactex-no-gui`. Existing
  TeX is reused. Its standard macOS installer may ask for administrator approval;
  complete that prompt yourself. A smaller BasicTeX installation is not a verified
  substitute unless it includes all required packages and the OpenType math font.
- `--with-model` is valid only with `full` and explicitly requests the pinned
  Qwen3-TTS CustomVoice snapshot: **4,520,218,951 bytes** before caches or overhead.
  It downloads anonymously and checks the fixed source/file identities.
- Without `--with-model`, `full` prepares the speech environment and clearly
  reports that model preparation was not requested. No weights are downloaded.
- Formula rendering needs XeLaTeX, `standalone.cls`, `unicode-math.sty`,
  `latinmodern-math.otf`, and dvisvgm. `doctor` checks their presence; actual
  compilation and visual/font correctness still require a sample render.

Full TeX, runtime caches, weights, and video outputs need substantial free disk
space. Budget at least tens of GB for a full working setup and production outputs.
The previous local speech calibration reached about 7.7 GB peak process memory;
16 GB or more unified memory is a practical recommendation, not a new-machine
benchmark or a guarantee. Core planning and imported recordings avoid local TTS costs.

## 3. Execute the chosen plan

For the complete local stack:

```sh
bash bin/setup-macos --profile full --with-tex --with-model --execute
bin/mathcoffee doctor --profile full
```

Or install only the smaller selected profile:

```sh
bash bin/setup-macos --profile core --execute
bin/mathcoffee doctor --profile core
```

The helper installs missing selected Homebrew formulae without requesting upgrades
or cleanup of existing packages. It creates owned, versioned environments and
records the selected executable paths. The framework wheel is installed offline
with `--no-deps`; render and speech dependencies are prepared from their locks.
System packages and the browser are separate upstream downloads. Homebrew/system
package versions are not made bit-for-bit reproducible by the Python/npm locks.

Setup prints its receipt and launcher paths. If interrupted, rerun the same command
with the same wheel: matching owned steps can resume. A different wheel under the
same version, an unowned environment, or a symlinked destination is rejected rather
than overwritten. Do not delete retained evidence to force a retry; inspect the
reported receipt/error or ask the maintainers.

`doctor` returns JSON with `profile`, `required_checks`, and `missing_required`.
Check for `status: ready`; a successful inspection process is not itself a complete
production acceptance. `core` does not require render/speech/model checks, and
`render` does not require speech weights. The default profile is `full`.

## 4. Install the host plugin

The supplied local catalogs point to the same extracted distribution containing
the wheel. Keep that directory available for marketplace refreshes.

**Codex:** add the extracted directory as a local marketplace:

```sh
codex plugin marketplace add /absolute/path/to/extracted-plugin
```

Open the plugin browser, choose the `mathcoffee-codex` source, install MathCoffee,
and start a new chat/restart the host if requested. On Codex CLI versions exposing
plugin installation, `codex plugin add mathcoffee@mathcoffee-codex` is also available
and was used in local installation tests. See the current
[official packaging instructions](https://developers.openai.com/plugins/build/plugins).

**Claude Code:** in a Claude Code session:

```text
/plugin marketplace add /absolute/path/to/extracted-plugin
/plugin install mathcoffee@mathcoffee-claude
```

Follow the host's scope/reload prompts. See its
[official plugin installation guide](https://code.claude.com/docs/en/discover-plugins).
The Claude bundle is structurally checked; actual Claude loading remains a community
test target. These packages are not listings in either host's official plugin directory.

Use the setup/create/review/revise skills from the installed MathCoffee plugin.
No lifecycle hook automatically installs packages, downloads models, or runs a film.
The CLI is also usable without a host plugin.

## 5. Create a user-owned project

```sh
bin/mathcoffee init --workspace "$HOME/Movies/MyMathVideo" \
  --brand 'My channel' --title 'A question worth answering'
bin/mathcoffee plan --workspace "$HOME/Movies/MyMathVideo"
```

The workspace must be new. Fill its `authoring.json` and `mathcoffee.json`, then
plan again. The blank template intentionally returns `incomplete`. Follow the
[authoring interface](project_interface.md) and [production workflow](production_workflow.md).

| Location | Contents |
|---|---|
| Extracted/host-cached plugin | Read-only skills, launcher, wheel and packaged resources |
| `~/Library/Application Support/MathCoffee/runtimes/<version>/core` | Owned Python 3.13 core |
| The same version's `render` and `speech` directories | Independent render and Python 3.12 speech environments |
| `~/Library/Application Support/MathCoffee/runtime.json` | Paths selected by explicit setup |
| `~/Library/Caches/MathCoffee` | Versioned engine/browser cache and pinned model cache |
| Your chosen workspace | Authoring, recordings, build stages, outputs and review evidence |

`MATHCOFFEE_DATA_HOME` and `MATHCOFFEE_CACHE_HOME` may select dedicated external
roots. `MATHCOFFEE_PYTHON` explicitly selects an existing core for the launcher.
Project runtime overrides support separately maintained environments.

## Manual setup and source development

If you already have dependencies, install the local wheel into a new external
Python 3.13 environment and point the launcher at it:

```sh
uv venv --python /absolute/path/to/python3.13 /absolute/path/to/mathcoffee-core
uv pip install --offline --no-deps --python /absolute/path/to/mathcoffee-core/bin/python \
  /absolute/path/to/mathcoffee-0.2.0a2-py3-none-any.whl
export MATHCOFFEE_PYTHON=/absolute/path/to/mathcoffee-core/bin/python
bin/mathcoffee setup --component render
bin/mathcoffee setup --component speech
bin/mathcoffee setup --component model
```

The component commands show plans until `--execute` is added. Keep Node 24 on the
process PATH or register its absolute path; the helper handles this automatically.
Do not mix speech packages into the Python 3.13 core/render environments.

A source checkout has no bundled wheel. Contributors build one with `uv build --wheel`
and pass `--wheel /absolute/path/to/the-wheel.whl` to the helper, or follow
[CONTRIBUTING](../CONTRIBUTING.md). `Brewfile` lists full runtime prerequisites
excluding TeX and weights; `brew bundle --no-upgrade` is an alternative for someone
who intentionally wants the entire list. The helper selects fewer packages for core/render.

## Upgrade, remove, and report problems

Extract a new release separately, verify its checksum, and run its helper. A new
version gets a new owned core/runtime directory; it does not edit old projects.
Global launcher selection may move to the newly prepared core. Keep older
plugin/runtime paths for projects that deliberately pin them; use project runtime
settings or `MATHCOFFEE_PYTHON` for explicit selection. Do not overwrite installed
resources or migrate production outputs implicitly.

Host uninstall removes the host plugin registration/cache. It does not remove
MathCoffee's external runtimes, model cache, or user workspaces. Uninstalling a
plugin is not a cleanup request. Report diagnostics through the
[issue template](https://github.com/sdt201909/MathCoffee/issues/new/choose), removing
private narration, paths, credentials, and copyrighted assets first.

The setup helper and package workflows are tested locally, but a truly clean Mac
provisioning run is still pending. See [validation status](implementation_status.md).

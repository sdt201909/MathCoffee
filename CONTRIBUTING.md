English | [简体中文](CONTRIBUTING.zh-CN.md)

# Contributing to MathCoffee

Contributions are welcome in English or Chinese. Start with the [README](README.md),
[installation guide](docs/installation.md), [documentation index](docs/README.md) and
[agent working agreements](AGENTS.md). Discuss broad changes in an issue before investing in a
large implementation. Small, focused fixes can go straight to a pull request.

## What belongs in this repository

Contribute reusable production components, host adapters, configuration, documentation and tests.
Use original, synthetic fixtures that demonstrate the problem without bringing in a complete
video production. Keep the framework independent of a particular episode or a maintainer's machine.

Do not submit episode source, authoring or narration, media, model weights, fonts, recordings,
virtual environments, caches, credentials or private logs. Ignoring a file in Git does not make it
disposable. Keep user projects outside the plugin installation and preserve them across updates.

When adding a framework file, review its content and rights, add its exact path to
`repository-files.txt`, then stage it explicitly. The repository guard also inspects committed
history; adding a prohibited asset and removing it later does not remove it from that history.

## Making a change

1. Keep one authoring source and stable scene, sentence, state and event IDs. Shared mathematical
   values and geometry should not diverge across engines, voices or captions.
2. Keep a single writer for each file when working with multiple agents. Make a focused change,
   include a concise explanation of the behavior before and after, and update affected interfaces
   and both documentation languages.
3. Add or run checks that address the changed behavior and compatibility boundary. Prefer small
   reproducible fixtures over expensive full-film rendering. State checks you could not run.
4. If a visual or speech change needs real media, keep that validation project outside the
   repository. Report source and output identities and the scope actually reviewed. Do not attach
   private narration or assets to a public issue or pull request.

## Relevant checks

With the appropriate isolated environments already configured:

```sh
make test-core
make test-speech
make test-voice-qa
make remotion-check
make repository-check
.venv/bin/python scripts/repository_guard.py --ref HEAD --history
```

The full core suite includes rendering-component imports. For lightweight planning and package
changes, the following subset runs without Manim, voice models or a browser:

```sh
PYTHONPATH=src python -m unittest \
  tests.test_project_style tests.test_cli_runtime tests.test_plugin_bundle \
  tests.test_repository_guard tests.test_bootstrap
uv build --wheel
```

The Ubuntu CI checks that subset, package installation and the Remotion contract/types. It does not
establish Apple Silicon rendering, actual host discovery, mathematical correctness, default-style
acceptance or good pronunciation. Do not run paid services, download voice models or render historical
videos merely to make a documentation or small planning change.

For mathematics or narrative changes, explain assumptions, derivation and remaining boundaries.
For visual changes, distinguish measured bounds and encoded-frame samples from complete dynamic
review. For speech changes, distinguish text or signal checks from real listening and check final
encoded audio when appropriate. A technical PASS must never sign off a human review.

## Pull requests and licensing

Use the pull request template to describe the user-visible change, relevant checks, limitations and
any dependency or redistribution changes. Do not claim unrun checks passed. Keep incidental
formatting and unrelated episode work out of the change.

Submit only material you have permission to contribute under the project's [Apache-2.0 license](LICENSE).
Retain required third-party notices and attribution, and identify anything that has different terms.
The project license does not replace dependency, model, font, music or other asset licenses. See
[dependency boundaries](docs/dependencies.md) and [third-party notices](THIRD_PARTY_NOTICES.md).

Report vulnerabilities privately through the process in [SECURITY.md](SECURITY.md), not a public
issue containing exploit details or secrets.

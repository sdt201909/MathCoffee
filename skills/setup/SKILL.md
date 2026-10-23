---
name: setup
description: Prepare or diagnose the local MathCoffee video runtime after plugin installation, without touching existing video projects.
---

Use this for MathCoffee installation, missing dependencies, or first-use environment checks. Plugin installation exposes workflows; Python, Manim, TeX, browsers and voice weights are prepared separately.

Resolve `../../bin/mathcoffee` relative to this skill directory to an absolute executable path, and quote that path in shell commands. Do not assume a plugin-root environment variable exists in the shell. Run its `--help` if a core runtime already exists.

If it returns `setup_required`, locate the single MathCoffee wheel under the installed plugin's `wheels/`. Use an existing Python 3.13 environment when possible. For an authorized first setup, use uv to create an external environment at `~/Library/Application Support/MathCoffee/core`, then install that exact wheel into it. Package installation may need public dependency downloads; report the components and download size when known. Never install into the plugin directory or mix the Python 3.12 speech environment with the Python 3.13 core. Set `MATHCOFFEE_PYTHON` to the selected executable for subsequent launcher calls; existing custom runtimes need not use the default directory.

After core preparation, run `doctor --workspace <user-project> --json`, then inspect `setup --help`. `setup --component render|speech|model` reports an action plan; adding `--execute` performs that explicit preparation. Prepare only the components needed for the user's intended task and already authorized scope. Weight downloads, browser preparation and speech environment setup are explicit operations. Missing credentials, costs or legal acceptance require a user decision; don't invent a cloud fallback or repeat authorization already given for the same setup.

Support starts with Apple Silicon Mac. Record actual executable paths and versions in the user project configuration, not in the plugin. A missing component should produce a concrete next step; it must not prevent brief or authoring planning when that component isn't needed yet.

Finish with the checks actually run, components still missing, and the workspace path. Do not claim installed host discovery, readable Chinese fonts, Metal inference, real pronunciation or video quality from dependency checks alone. Never delete user projects during repair, upgrade or uninstall.

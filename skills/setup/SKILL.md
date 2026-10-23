---
name: setup
description: Prepare or diagnose the local MathCoffee video runtime after plugin installation, including a new Apple Silicon Mac, without touching existing video projects.
---

Use this for MathCoffee installation, missing dependencies, or first-use checks. Plugin installation exposes workflows; Python, Manim, TeX, browsers and voice weights are prepared separately.

Resolve `../../bin/setup-macos` and `../../bin/mathcoffee` relative to this skill directory to absolute paths and quote them. Do not assume a plugin-root variable or an ambient `mathcoffee` command. Read the installed `../../docs/installation.md` for prerequisites and recovery.

Start with the bootstrap's read-only plan: `bash <absolute-setup-macos> --profile core|render|full`. Choose core for model-free planning, render for imported recordings or explicit silence, and full for the local Python 3.12 speech runtime. `--with-tex` explicitly selects missing MacTeX; `--with-model` explicitly selects the pinned multi-gigabyte Qwen weights and is valid only with full. No model is downloaded without that flag or an explicit model setup command.

Adding `--execute` prepares only the selected components. Proceed when that setup/download scope is already authorized; report components and known download sizes first without asking again for the same authorization. Apple Command Line Tools and native Homebrew must be installed by the user. Do not install either through a remote shell script, handle passwords, bypass administrator prompts, or accept legal agreements. The opted-in MacTeX installer may request normal interactive administrator approval.

The complete release ZIP contains one matching wheel. The bootstrap installs it offline into a versioned external Python 3.13 core, records `core_python`, and prepares separate render/speech environments with ownership and recovery receipts. It installs missing selected Homebrew packages without requesting upgrades or cleanup. It never edits shell profiles or user works. A source checkout needs a separately built wheel passed with `--wheel`; do not claim it is an already complete distribution.

For existing custom environments, `MATHCOFFEE_PYTHON` may select a core explicitly. Never mix Python 3.12 speech packages with the Python 3.13 core/render runtime. Preserve existing project runtime selections unless changing them is part of the task.

Run `doctor --profile core|render|full --json`, optionally with `--workspace <existing-project>`. Inspect `status`, `required_checks`, and `missing_required`; a missing optional model does not block core planning or imported-voice rendering. `setup --component render|speech|model` remains available for explicit component plans and recovery, with execution only when `--execute` is present.

Support starts with native Apple Silicon Mac. Finish with actual executable paths, checks run, components still missing and the user workspace path. Do not claim clean-Mac acceptance, Claude host loading, glyph coverage, Metal inference, audible pronunciation or style from dependency checks alone. No paid-service fallback, account creation, content upload, film publication or media cleanup is part of installation repair.

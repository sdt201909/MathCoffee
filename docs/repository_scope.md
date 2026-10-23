English | [简体中文](repository_scope.zh-CN.md)

# Repository scope and history isolation

This repository contains the reusable MathCoffee framework. Video assets and complete episode
implementations are excluded. The original local production project and its Git history are retained
separately. The first framework commit has no parent, so it does not carry historical scene code to
the remote. Push only reviewed framework refs; never use `--all` or `--mirror`, or push unrelated
historical branches and tags as part of framework publication.

## Included

- Shared timeline, audio, speech, procedural music and figure-label contracts.
- Generic CLI commands, tests and dual-engine compositors without episode-input dependencies.
- Shared dictionaries and settings, dependency locks, upstream notices and production requirements.

## Excluded

- `media/`, `scenes/`, `examples/`, `notebooks/` and episode-specific authoring, mathematical models,
  narration, captions, editorial plans, covers, delivery reports and acceptance records.
- Images, video, audio, fonts, model weights, archives and generated caches.
- Virtual environments, `node_modules`, credentials, environment files, test private keys and local
  databases.
- Historical cleanup tools that permanently empty media directories.

`.gitignore` is the first boundary. [repository-files.txt](../repository-files.txt) is the exact
reviewed allowlist. `scripts/repository_guard.py` checks actual Git index bytes, or a specified
commit and its ancestors. It rejects files outside the allowlist, prohibited paths or suffixes,
symlinks, oversized files, binary content and common credential markers. It cannot detect all
private information or automatically determine whether a new file belongs to an episode; human
review remains necessary.

```sh
make repository-check
.venv/bin/python scripts/repository_guard.py --ref HEAD --history
```

Before adding shared files, review their contents, licenses and dependencies on episode directories.
Then update the exact allowlist and stage paths explicitly with `git add`. Continue framework work
in its isolated worktree rather than pushing from old production branches. Ignoring local production
materials establishes a version-control boundary; it never authorizes deletion.

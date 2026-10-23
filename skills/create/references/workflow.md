# Runtime and workspace workflow

The executable is `../../bin/mathcoffee` relative to a skill directory (`skills/<name>/`); resolve it before calling a shell. Installed plugin roots may contain spaces and change on upgrade. Shells need not expose the host's plugin-root placeholders.

Use `--help` to inspect the installed CLI's current arguments. Its user-level commands are `setup`, `doctor`, `init`, `plan`, `preview`, `render`, `verify`, `status`, `resume`; select a workspace explicitly with `--workspace` and use `--json` for structured results. A `setup_required` result calls for environment preparation, not an improvised fallback. In a development checkout without a packaged wheel, follow its project installation instructions rather than borrowing a production project's virtual environment.

The core package is read-only. Runtime environments and versioned models live in an external MathCoffee directory; authoring, topic-specific models/scenes, audio, previews, revisions and final outputs belong to the user project. Keep paths and dependency identities in engineering records, not in audience text.

Use a single authoring source. The normalized form is ordered `scenes` containing ordered `sentences` with stable IDs; existing `chapters/cues` inputs are adapted explicitly. The source records mathematical states and visual/action references. Voice requests, sentence windows, display manifests and renderer timelines are derived. A separate copy of the narration or scene plan must not become another editable source of truth.

For new work: brief and mathematics → complete authoring and independent review → voice/style sample → measured voice windows → mathematical clips and premix → full draft → recorded reviews → final render and encoded-container verification. When a review requires the user's judgment, finish all independent checks and present a concrete playable sample; leave that review pending until the user responds.

For revisions: preserve the authored IDs that still describe the same item, calculate the dependency changes, and use a new output revision. `status` and `resume` may reuse only artifacts whose source, style, model, voice and runtime identities still match. An old caption, closing line or voice file must not survive a changed source through cache reuse.

Style calibration applies to the versioned default preset. A custom preset records its differences and is evaluated on its own actual output. Semantic object identity, shared computed geometry, readable mathematical labels and truthful review evidence remain required for every preset. Do not force a fixed three-column layout, chapter count or three-minute cap onto content that needs another structure.

Final evidence distinguishes automatic validation, encoded-frame sampling, complete human viewing, actual listening and target-audience feedback. If a skill cannot access an output or a reviewer hasn't listened, say so directly. No automatic score grants human acceptance.

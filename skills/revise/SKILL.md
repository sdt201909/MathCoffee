---
name: revise
description: Revise an existing MathCoffee video project while preserving authoring identity, immutable prior deliveries and auditable cache invalidation.
---

Resolve `../../bin/mathcoffee` from this skill directory to an absolute quoted path. Inspect the requested changes, current authoring, selected style, latest reviews and `status --workspace <project> --json` before editing. Apply authorized fixes directly; don't ask again for routine work within that scope.

Keep a sentence or scene ID when its identity is preserved, and use a new ID when introducing a distinct element. Change the canonical source; regenerate narration, voice requests, display text and timelines from it. Original display text and normalized model input stay separate. Topic-specific code remains in the user workspace.

Classify dependencies actually changed: wording, voice take, mathematical state, motion, layout, style or renderer. Rebuild the affected artifacts and descendants; `resume` may reuse only matching identities. A voice duration change invalidates dependent sentence windows, motion, music ducking and final muxing. Preserve previous WAVs and delivered masters and choose a new output revision.

After text changes, examine a representative continuous cross-scene sample, then the full draft. Recheck the last body section through the black frame for old closing lines in voice or subtitle caches. Run the relevant technical validation and provide playable samples for judgments that require listening or style comparison. Keep those reviews pending until actually performed.

Report what changed, why, what was tested and what still requires review. Do not claim that reused files were newly rendered, that sample inspection was full viewing, or that automatic checks granted a person's approval. Do not clean old outputs or publish unless the user separately authorized that operation.

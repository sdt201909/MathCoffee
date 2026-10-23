---
name: create
description: Create a new mathematics video in a user workspace using MathCoffee style presets, shared mathematical state and local production tools.
---

Use this when the user asks to make a mathematics explanation video with MathCoffee. Read [workflow](references/workflow.md) for CLI routing, data ownership and the review checkpoints.

Establish the audience, question, mathematical scope, format and delivery goal from the request and available context. Default to `mathcoffee-shorts@1`; use `mathcoffee-longform@1` for landscape chapters. Ask only for missing choices that materially change the work. Use the user's own channel name or leave branding blank; the MathCoffee style preset does not authorize branding a video as the original channel.

Initialize a new user-selected workspace with the CLI; never store work in the installed plugin. Create one canonical authoring source with stable scene and sentence IDs. Start from a concrete question, show the observable need, and let the result motivate the next tool. Calculate models and events independently of animation; make the visuals and narration read those results. Declare assumptions, approximations and counterexamples. Generate topic-specific scene extensions only in the user workspace.

Resolve the complete style configuration before producing a sample. Defaults are configurable: colors and semantic roles, typography, layout, motion, reading holds, narrative preferences, voice, music and branding. Record overrides; do not silently change an approved preset. Mathematical correctness and truthful review records remain independent of style overrides.

Plan without requiring voice weights. Then prepare a short continuous sample covering the actual labels, numbers, polyphones and bilingual phrases. Default voice is Serena/science_female/full_text; another local provider or imported per-sentence recording is allowed when explicitly selected. Preserve original display text and auditable spoken normalization. Measure actual PCM windows before scheduling captions, actions or music ducking. Never compress narration by cropping tail syllables or changing playback rate to fit a budget.

Build and review the complete low-resolution target before high-resolution delivery. Portrait defaults keep narration but do not burn narration captions; necessary mathematical labels, formulae and headings remain. Landscape caption policy is separate. Check intermediate motion, occlusion, long text, formula holds and the final content through the black frame. Technical checks, mathematics review, narrative continuity, visual sampling, human listening and audience understanding are separate records.

Report exact output paths, real media specs, hashes and pending reviews. Don't label a video approved, style-calibrated or fully listened to without matching evidence. Producing a local file does not publish it or save it to a library. Follow an explicit publishing request separately.

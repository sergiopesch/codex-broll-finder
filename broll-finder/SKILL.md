---
name: broll-finder
description: "Use when sourcing, vetting, formatting, or placing b-roll/cutaways for talking-head videos from a transcript, audio/video file, or editor project. Optimized for Codex: plan first, use structured manifests, run deterministic helper tools, and verify rendered cuts before delivery."
---

# B-Roll Finder

Codex uses this skill to find accurate b-roll for talking-head edits and place it on the right word. The workflow favors objective sources, structured state, and visual verification over vague keyword searches.

## Core Rule

The agent narrows the funnel; the user makes taste calls. For objective routes, an approved plan authorizes sourcing one best candidate per beat. For taste-heavy routes, especially memes and reaction clips, propose the moment and let the user provide or approve the asset.

## Workflow

1. **Load profile**: read the user's b-roll profile if provided. If none exists, create `BROLL-PROFILE.md` beside the project using `references/profile.md`.
2. **Understand the video**: read the full transcript first. If only media is provided, transcribe once with word timestamps.
3. **Plan beats before fetching**: identify high-value cutaway moments, write the real interpretation of each line, classify its route, and present the plan for approval.
4. **Source by origin**: after approval, group beats by source so one website capture or official video can cover several beats.
5. **Format assets**: output silent, full-bleed clips. Use the bundled tool for still zooms, page captures, validation, and cutaway renders.
6. **Maintain state**: keep a `BROLL-MANIFEST.json` for machine execution and a short `BROLL-MANIFEST.md` for human review. Approved beats must not disappear between renders.
7. **Verify visually**: extract midpoint and joint frames after each render, inspect them, and fix rejected frames before presenting the result.

## Planning Contract

Each proposed beat must include:

- `id`: stable short id, such as `b001`
- `time`: transcript or word-timestamp anchor
- `line`: the narration being illustrated
- `interpretation`: what the line is actually about
- `route`: `receipt`, `entity`, `product-ui`, `concept`, `evocative`, or `taste`
- `source_plan`: where the correct asset should come from
- `fallback`: what to try if the preferred source fails

Before sourcing, check the palette. If more than 60% of planned beats are website screenshots, revise the plan unless the script is explicitly receipt-heavy.

## References

Load only the file needed for the current step:

- `references/routing.md`: classification, search rules, scoring, and source escalation.
- `references/profile.md`: taste profile schema and onboarding questions.
- `references/manifest.md`: JSON manifest format for renderable beat plans.
- `references/verification.md`: render, frame-grid, and auto-reject rules.

## Tooling

Run helper commands through:

```bash
python broll-finder/scripts/broll_tool.py --help
```

Primary commands:

- `validate-manifest`: parse and check `BROLL-MANIFEST.json`.
- `zoom-still`: render a smooth sub-pixel still zoom without ffmpeg `zoompan`.
- `capture-page`: capture a public page or tweet embed with headless Chrome/Chromium.
- `render-cutaways`: replace base-video visuals during beat windows while preserving base audio.
- `verify-frames`: extract beat midpoint and transition frames for inspection.

If a helper fails once, switch method. If a second distinct method fails for the same beat, drop or flag the beat instead of burning time.

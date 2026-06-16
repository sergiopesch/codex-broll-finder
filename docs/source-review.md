# Source Repo Review

Reviewed repo: upstream `b-roll-finder`
Commit inspected: `36b8a56`

## What It Is

The upstream repo is a methodology skill, not an application. Its core value is editorial judgment: understand the full transcript, classify each b-roll beat by the type of evidence needed, source from authoritative places, then place full-bleed silent cutaways precisely on the spoken word.

## Strongest Ideas To Preserve

- Meaning-first sourcing: interpret each beat before searching.
- Routing model: receipts, entities, concepts, and taste calls go to different sources.
- Taste profile: curation and guardrails are first-class, not afterthoughts.
- Lean path: approved objective beats get one best candidate instead of endless contact sheets.
- Source clustering: fetch once per origin, not serially per beat.
- Manifest discipline: approved beats should not disappear between revisions.
- Visual verification: inspect midpoint and joint frames before delivery.
- Sub-pixel still motion: avoid ffmpeg `zoompan` because integer stepping causes jitter.

## Gaps In The Upstream Shape

- `SKILL.md` is long and mixes core workflow, edge cases, source policy, ffmpeg recipes, and personal anecdotes.
- `TASTE.md` ships as a confirmed personal profile, which is useful as an example but not as a generic default.
- The helper scripts are prototypes: hardcoded macOS Chrome path, manual constants, no argument validation, no packaging, no tests.
- Render state is described in prose but not represented as a machine-validated manifest.
- Contact-sheet behavior conflicts slightly with the newer lean-path rule.
- There is no CI, dependency declaration, or reproducible install path.

## Codex Direction

The Codex version should be a skill plus tools:

- small `SKILL.md` for trigger-time behavior
- detailed references loaded only as needed
- structured `KINO-PROFILE.md` and `KINO-MANIFEST.json`
- portable Python CLI wrappers around fragile media operations
- tests for parsing, validation, and generated ffmpeg command shape
- explicit attribution to the MIT upstream

# Goal

Build `kino` into an open-source Codex-native video editing system: first as a high-quality reusable skill, then as an installable Codex plugin once the workflow, tools, validation, and documentation are stable.

The controlling specification is [product-spec.md](./product-spec.md).

The active implementation target is [phase-1-build-goal.md](./phase-1-build-goal.md).

## Product Thesis

Video editing with Codex should not imitate a timeline UI. It should let a creator describe editorial intent, inspect structured plans, approve taste decisions, and receive a technically correct edit with manifests, reproducible renders, and visual/audio verification.

The first wedge is b-roll for talking-head video because it has objective correctness: a claim, person, product, quote, UI, or receipt can be sourced and validated. The long-term product is a Codex-native editing layer for sound, video, text, animation, effects, transitions, and platform-specific exports.

## Current Strategic Decision

Keep the workflow as a **Codex skill** while the editing model is still changing. Package it as a **Codex plugin** when distribution, marketplace installation, bundled tools, or optional MCP/app integrations become core to the experience.

Why:

- Skills are the Codex authoring format for reusable workflows.
- Plugins are the installable distribution unit for skills, apps, MCP servers, hooks, and assets.
- This project needs the skill format now, but the public/open-source goal points toward a plugin package.

## Milestones

1. **Skill MVP**: source and place b-roll from a transcript or base video using a manifest-driven render loop.
2. **Editing Core**: expand from b-roll to timeline operations, captions, titles, audio normalization, transitions, effects, and export presets.
3. **Quality Harness**: add automated and visual tests for frame accuracy, audio loudness, captions, safe zones, and export compliance.
4. **Plugin Package**: add `.codex-plugin/plugin.json`, marketplace metadata, install tests, and optional MCP/app integrations.
5. **Public Release**: publish docs, examples, demo assets, contribution guide, and a reproducible evaluation suite.

## Definition Of Done

The project is ready to position as a serious Codex video-editing plugin when a fresh Codex install can:

- install the plugin from a public marketplace source,
- run an end-to-end sample edit,
- pass the validation suite,
- export platform-specific files for major social formats,
- produce a human-readable edit manifest and verification report,
- preserve creative intent through multiple revision cycles.

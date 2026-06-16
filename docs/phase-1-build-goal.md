# Phase 1 Build Goal

Last updated: 2026-06-16

## Goal

Build the first usable Kino editing loop: a skill-driven workflow plus deterministic helpers that can render a sample cutaway edit, export social variants, and produce machine-readable validation reports.

This goal implements the Phase 1 slice of [product-spec.md](./product-spec.md). The plugin scaffold exists to keep packaging pressure visible, but public plugin release remains Phase 3 until install, marketplace, and sample-project criteria pass.

This phase also establishes the edit-engine foundation for the next slice without requiring a broad core rewrite: `KINO-MANIFEST.json` stays the executable Phase 1 input, while `KINO-EDIT.json`, typed render graphs, render receipts, and source receipts become the contract that future implementation work can stage toward.

The second build target is transcript-to-manifest planning v1: initialize edit state from a transcript, propose beat candidates against transcript ranges, preserve explicit approvals and rejections, and compile only approved beats into the existing `KINO-MANIFEST.json` render input.

## Current Scope

Phase 1 includes:

- manifest validation for planned b-roll beats
- cutaway rendering while preserving base narration
- verification-frame extraction
- social export presets for `9:16`, `1:1`, `4:5`, and `16:9`
- media probing through `ffprobe`
- JSON and Markdown validation reports
- strict validation mode for CI/release gates
- `KINO-EDIT` planning-state data structures for transcript tokens, source receipts, asset candidates, beat candidates, approvals, and rejections
- the documented `init-edit` -> propose beat -> approve/reject beat -> `compile-manifest` planning flow
- typed render graph data structures and conversion from the current cutaway manifest
- render receipts for successful cutaway renders
- repo-local plugin scaffold validation, including bundled skill and helper source

Phase 1 does not yet include:

- a graph executor that replaces direct cutaway rendering
- rendering directly from `KINO-EDIT.json`
- automated sourcing from stock or social platforms
- automated source-receipt writing from live sourcing tools
- transcription and word-level alignment
- caption rendering
- loudness normalization
- safe-zone geometry checks
- marketplace install/reinstall flow

## Edit-Engine Foundation

The Phase 1 renderer is intentionally narrow: it accepts a cutaway manifest and emits a finished video. The next foundation should preserve that deterministic path but wrap it in inspectable project state:

- `KINO-EDIT.json`: project-level planning state. It records transcript tokens, source receipts, asset candidates, beat candidates, approvals, and rejections.
- Render graph: a typed intermediate representation of sources, tracks, clips, outputs, and validation expectations that can be generated from the current cutaway manifest.
- Source receipts: evidence records for each external or local asset, including origin URL or path, retrieval method, timestamp, credit, rights notes, and any transformation into `assets/fmt/`.
- Render receipts: machine-readable records for cutaway renders, including manifest hash, render graph hash, command hash, command argv, tool versions, input/output paths, and formatted-asset commands.

The staged path is:

1. Keep `KINO-MANIFEST.json` as the Phase 1 execution format for cutaways.
2. Use `init-edit` to create `KINO-EDIT.json` from transcript state and project metadata.
3. Propose beat candidates from transcript ranges, then record user or agent approvals and rejections without deleting rejected context.
4. Run `compile-manifest` to translate approved beat candidates into `KINO-MANIFEST.json`.
5. Validate and render through the existing `validate-manifest`, `render-cutaways`, and `verify-frames` path.
6. Write render receipts around existing cutaway commands before changing render semantics.
7. Compile supported graph structures into the current deterministic helpers.
8. Replace direct cutaway-only orchestration only after graph execution has equivalent tests and receipts.

## Agent Workstreams

Parallel review goals:

- **CI/package readiness**: verify clean install, CI workflow, dev dependencies, skill validation, and CLI entrypoints.
- **Codex architecture**: review the skill, references, product spec, and plugin path for the smallest useful Codex-native implementation slice.
- **Media engine quality**: review ffmpeg command generation, probing, validation, smoke tests, and missing audio/video/text checks.
- **Social export validation**: review presets, platform assumptions, safe zones, captions, audio targets, and validation gaps against current public platform guidance.

## Acceptance Criteria

The Phase 1 build is acceptable when:

- `pip install -e ".[dev]"` works in a clean virtualenv.
- `kino --help` exposes manifest, render, verification, preset, probe, validation, and export commands.
- `pytest` passes, including at least one real ffmpeg smoke test when `ffmpeg` and `ffprobe` are installed.
- `ruff check .` passes.
- `.ci/quick_validate_skill.py` validates the root skill using the active interpreter.
- `plugins/kino` passes plugin manifest validation.
- `validate-export --strict` exits nonzero for warnings or manual-review items.
- Validation reports include concrete checks for container, dimensions, codec, pixel format, scan type, square pixels, frame rate, audio codec/sample rate, and fast-start atom order when the file is available.
- Docs identify the future `KINO-EDIT` model without claiming the graph executor is complete.
- Docs make clear that transcript planning compiles to `KINO-MANIFEST.json` and rendering still uses the manifest path.

## Verification Commands

Run:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
ruff check .
pytest
python .ci/quick_validate_skill.py
python /path/to/plugin-creator/scripts/validate_plugin.py plugins/kino
kino --help
```

Clean-install smoke:

```bash
tmpdir="$(mktemp -d)"
python3 -m venv "$tmpdir/venv"
"$tmpdir/venv/bin/python" -m pip install -e ".[dev]"
"$tmpdir/venv/bin/kino" --help
"$tmpdir/venv/bin/pytest"
```

## Risks

- Platform export requirements change; release candidates must re-check current primary docs.
- The plugin scaffold is not a public release package until install and marketplace flows are tested.
- Fast-start detection is a lightweight atom-order check, not a full MP4 parser.
- Audio loudness, captions, and safe-zone checks are still planned Phase 2 work.

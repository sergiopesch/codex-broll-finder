# Phase 1 Build Goal

Last updated: 2026-06-15

## Goal

Build the first usable Codex-native b-roll editing loop: a skill-driven workflow plus deterministic helpers that can render a sample cutaway edit, export social variants, and produce machine-readable validation reports.

This goal implements the Phase 1 slice of [product-spec.md](./product-spec.md). The plugin scaffold exists to keep packaging pressure visible, but public plugin release remains Phase 3 until install, marketplace, and sample-project criteria pass.

## Current Scope

Phase 1 includes:

- manifest validation for planned b-roll beats
- cutaway rendering while preserving base narration
- verification-frame extraction
- social export presets for `9:16`, `1:1`, `4:5`, and `16:9`
- media probing through `ffprobe`
- JSON and Markdown validation reports
- strict validation mode for CI/release gates
- repo-local plugin scaffold validation, including bundled skill and helper source

Phase 1 does not yet include:

- automated sourcing from stock or social platforms
- transcription and word-level alignment
- caption rendering
- loudness normalization
- safe-zone geometry checks
- marketplace install/reinstall flow

## Agent Workstreams

Parallel review goals:

- **CI/package readiness**: verify clean install, CI workflow, dev dependencies, skill validation, and CLI entrypoints.
- **Codex architecture**: review the skill, references, product spec, and plugin path for the smallest useful Codex-native implementation slice.
- **Media engine quality**: review ffmpeg command generation, probing, validation, smoke tests, and missing audio/video/text checks.
- **Social export validation**: review presets, platform assumptions, safe zones, captions, audio targets, and validation gaps against current public platform guidance.

## Acceptance Criteria

The Phase 1 build is acceptable when:

- `pip install -e ".[dev]"` works in a clean virtualenv.
- `broll-tool --help` exposes manifest, render, verification, preset, probe, validation, and export commands.
- `pytest` passes, including at least one real ffmpeg smoke test when `ffmpeg` and `ffprobe` are installed.
- `ruff check .` passes.
- `.ci/quick_validate_skill.py` validates the root skill using the active interpreter.
- `plugins/codex-broll-finder` passes plugin manifest validation.
- `validate-export --strict` exits nonzero for warnings or manual-review items.
- Validation reports include concrete checks for container, dimensions, codec, pixel format, scan type, square pixels, frame rate, audio codec/sample rate, and fast-start atom order when the file is available.

## Verification Commands

Run:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
ruff check .
pytest
python .ci/quick_validate_skill.py
python /path/to/plugin-creator/scripts/validate_plugin.py plugins/codex-broll-finder
broll-tool --help
```

Clean-install smoke:

```bash
tmpdir="$(mktemp -d)"
python3 -m venv "$tmpdir/venv"
"$tmpdir/venv/bin/python" -m pip install -e ".[dev]"
"$tmpdir/venv/bin/broll-tool" --help
"$tmpdir/venv/bin/pytest"
```

## Risks

- Platform export requirements change; release candidates must re-check current primary docs.
- The plugin scaffold is not a public release package until install and marketplace flows are tested.
- Fast-start detection is a lightweight atom-order check, not a full MP4 parser.
- Audio loudness, captions, and safe-zone checks are still planned Phase 2 work.

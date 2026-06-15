# Codex B-Roll Finder

A Codex-native version of Louise de Sadeleer's `b-roll-finder`: a skill plus helper tooling for planning, sourcing, formatting, placing, and visually verifying b-roll for talking-head videos.

This repo is intentionally split into:

- `broll-finder/SKILL.md`: compact Codex instructions loaded when the skill triggers.
- `broll-finder/references/`: detailed routing, profile, manifest, and verification guidance loaded only when needed.
- `src/codex_broll_finder/`: deterministic Python helpers for manifest validation, still zooms, page capture, rendering, and verification-frame extraction.
- `plugins/codex-broll-finder/`: repo-local Codex plugin scaffold for packaging the skill once the workflow stabilizes.
- `tests/`: fast unit tests for manifest and render-command behavior.

## Quick Start

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
python broll-finder/scripts/broll_tool.py --help
pytest
```

External tools used by real video workflows:

- `ffmpeg` and `ffprobe`
- Chrome or Chromium for page capture
- `yt-dlp` for public video metadata/downloads
- Whisper or another transcription tool that can emit word timestamps

## Project State

This is the starter scaffold. The first usable slice is the manifest-driven rendering loop:

1. plan beats with Codex
2. save them to `BROLL-MANIFEST.json`
3. validate with `validate-manifest`
4. render with `render-cutaways`
5. extract inspection frames with `verify-frames`

The first quality-harness commands are also available:

```bash
broll-tool list-presets
broll-tool probe-media output.mp4
broll-tool validate-export output.mp4 --preset vertical-social --json-out BROLL-VALIDATION.json --md-out BROLL-VALIDATION.md
broll-tool validate-export output.mp4 --preset vertical-social --strict
broll-tool export-variant output.mp4 output.vertical.mp4 --preset vertical-social
```

## Product Direction

The project goal and full product specification live in:

- [docs/goal.md](docs/goal.md)
- [docs/product-spec.md](docs/product-spec.md)
- [docs/phase-1-build-goal.md](docs/phase-1-build-goal.md)

Short version: keep iterating as a Codex skill while the workflow is changing, then package it as a Codex plugin once it is stable enough for marketplace-style installation.

## Attribution

Adapted from the MIT-licensed [`louisedesadeleer/b-roll-finder`](https://github.com/louisedesadeleer/b-roll-finder) methodology and helper scripts.

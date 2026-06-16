# Kino

![Kino product concept showing an AI-assisted video editing timeline, b-roll cards, validation checks, captions, audio waveform, and social export presets.](docs/assets/kino-hero.png)

Kino is a Codex-native video edit engine: a manifest-driven core plus helper tooling for planning, assembling, rendering, exporting, and verifying video edits.

This repo is intentionally split into:

- `kino/SKILL.md`: compact Codex instructions loaded when the skill triggers.
- `kino/references/`: detailed routing, profile, manifest, and verification guidance loaded only when needed.
- `src/kino/`: deterministic Python helpers for manifest validation, still zooms, page capture, rendering, and verification-frame extraction.
- `plugins/kino/`: repo-local Codex plugin scaffold for packaging the skill once the workflow stabilizes.
- `tests/`: fast unit tests for manifest, render-command, probing, export, and validation behavior.

## Quick Start

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
python kino/scripts/kino_tool.py --help
pytest
```

External tools used by real video workflows:

- `ffmpeg` and `ffprobe`
- Chrome or Chromium for page capture
- `yt-dlp` for public video metadata/downloads
- Whisper or another transcription tool that can emit word timestamps

## Project State

This is the starter scaffold. The first usable slice is the manifest-driven cutaway rendering loop:

1. plan beats with Codex
2. save them to `KINO-MANIFEST.json`
3. validate with `validate-manifest`
4. render with `render-cutaways`
5. extract inspection frames with `verify-frames`

The first quality-harness commands are also available:

```bash
kino list-presets
kino probe-media output.mp4
kino validate-export output.mp4 --preset vertical-social --json-out KINO-VALIDATION.json --md-out KINO-VALIDATION.md
kino validate-export output.mp4 --preset vertical-social --strict
kino export-variant output.mp4 output.vertical.mp4 --preset vertical-social
```

## Product Direction

The project goal and full product specification live in:

- [docs/goal.md](docs/goal.md)
- [docs/product-spec.md](docs/product-spec.md)
- [docs/phase-1-build-goal.md](docs/phase-1-build-goal.md)

Short version: keep iterating as a Codex skill while the workflow is changing, then package it as a Codex plugin once it is stable enough for marketplace-style installation.

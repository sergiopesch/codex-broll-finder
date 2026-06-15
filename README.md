# Codex B-Roll Finder

A Codex-native version of Louise de Sadeleer's `b-roll-finder`: a skill plus helper tooling for planning, sourcing, formatting, placing, and visually verifying b-roll for talking-head videos.

This repo is intentionally split into:

- `broll-finder/SKILL.md`: compact Codex instructions loaded when the skill triggers.
- `broll-finder/references/`: detailed routing, profile, manifest, and verification guidance loaded only when needed.
- `src/codex_broll_finder/`: deterministic Python helpers for manifest validation, still zooms, page capture, rendering, and verification-frame extraction.
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

## Attribution

Adapted from the MIT-licensed [`louisedesadeleer/b-roll-finder`](https://github.com/louisedesadeleer/b-roll-finder) methodology and helper scripts.

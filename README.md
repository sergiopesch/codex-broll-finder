# Kino

![Kino engine diagram showing transcript tokens flowing into KINO-EDIT planning state, approved beats, receipts, KINO-MANIFEST, KINO-RENDER, render graph, and QC validation.](docs/assets/kino-hero.png)

Kino is a Codex-native video edit engine: a manifest-driven core plus helper tooling for planning, assembling, rendering, exporting, and verifying video edits.

The current executable format is `KINO-MANIFEST.json` for cutaway edits. The staged edit-engine foundation is `KINO-EDIT.json`: a project-level planning model for transcript tokens, sources, asset candidates, beat candidates, approvals, and rejections. The package also includes a typed render graph that can represent the existing cutaway manifest, plus render receipts for cutaway renders.

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

Run the reproducible sample edit:

```bash
python3 examples/quickstart/run.py
```

The quickstart generates tiny media with `ffmpeg`, writes all artifacts under `examples/quickstart/out/`, and exercises the current loop: `init-edit` -> `add-source`/`add-asset` -> `propose-beat` -> `approve-beat` -> `compile-manifest` -> `render-cutaways` -> `verify-frames` -> `export-variant` -> `validate-export`.

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
kino --help
kino list-presets
kino probe-media output.mp4
kino validate-export output.mp4 --preset vertical-social --json-out KINO-VALIDATION.json --md-out KINO-VALIDATION.md
kino validate-export output.mp4 --preset vertical-social --strict
kino export-variant output.mp4 output.vertical.mp4 --preset vertical-social
```

## Edit-Engine Foundation

Kino is moving in stages from a cutaway manifest to a graph-backed edit engine:

- `KINO-MANIFEST.json` remains the supported Phase 1 execution input.
- `KINO-EDIT.json` is the planning state initialized by `init-edit` for transcript tokens, source receipts, asset candidates, beat candidates, approvals, and rejections.
- The second build target is a transcript-to-manifest planning loop: initialize an edit, propose beats from transcript ranges, approve or reject each candidate, then run `compile-manifest` to write the approved beats into `KINO-MANIFEST.json`.
- Rendering still goes through `KINO-MANIFEST.json`: validate with `validate-manifest`, render with `render-cutaways`, and inspect with `verify-frames`.
- The render graph is a typed intermediate representation for sources, tracks, clips, outputs, validation expectations, canonical JSON, and stable hashes.
- Cutaway renders now write `KINO-RENDER.json` with manifest hash, render graph hash, ffmpeg command hash, tool versions, paths, and formatted-asset commands.
- Source receipts are represented in `KINO-EDIT.json`; automated source-receipt writing and graph execution are still future work.

## Product Direction

The project goal and full product specification live in:

- [docs/goal.md](docs/goal.md)
- [docs/product-spec.md](docs/product-spec.md)
- [docs/phase-1-build-goal.md](docs/phase-1-build-goal.md)

Short version: keep iterating as a Codex skill while the workflow is changing, then package it as a Codex plugin once it is stable enough for marketplace-style installation.

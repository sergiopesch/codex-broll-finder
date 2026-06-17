# Kino Quickstart Runner

This example generates tiny local media with `ffmpeg`, then exercises the public Kino CLI loop:

```bash
python3 examples/quickstart/run.py
```

The run writes all generated files to `examples/quickstart/out` by default:

- `KINO-EDIT.json`
- `KINO-MANIFEST.json`
- `KINO-RENDER.json`
- `rendered.mp4`
- `verify_frames/`
- `KINO-CONTACT-SHEET.jpg`
- `KINO-FRAME-QC.json`
- `KINO-FRAME-QC.md`
- `KINO-AUDIO-QC.json`
- `KINO-AUDIO-QC.md`
- `export.landscape-web.mp4`
- `KINO-VALIDATION.json`
- `KINO-VALIDATION.md`

Use a temporary output directory when you want a clean run:

```bash
python3 examples/quickstart/run.py --workdir /tmp/kino-quickstart
```

The runner requires `ffmpeg`, `ffprobe`, and the Python package dependencies from the repo setup step, including Pillow for contact-sheet generation. It sets `PYTHONPATH` for child CLI calls so it can run directly from an installed source checkout.

The sample keeps one approved beat and one rejected beat in `KINO-EDIT.json`. Only the approved beat is compiled into `KINO-MANIFEST.json`, which is still the render input for this milestone.

After rendering, the runner extracts verification frames, generates a labeled contact sheet, writes frame QC reports, analyzes audio on the rendered master, exports a platform variant, and validates that export against the selected preset.

# Exports And Validation

Use this reference after rendering an edit or when the user asks for platform variants.

## Built-In Presets

Run:

```bash
python3 broll-finder/scripts/broll_tool.py list-presets
```

Current presets:

- `vertical-social`: 1080x1920, 9:16, H.264/AAC, 30 fps minimum.
- `square-social`: 1080x1080, 1:1, H.264/AAC, 30 fps minimum.
- `portrait-feed`: 1080x1350, 4:5, H.264/AAC, 30 fps minimum.
- `landscape-web`: 1920x1080, 16:9, H.264/AAC, preserve source frame rate.

## Probe Media

Run:

```bash
python3 broll-finder/scripts/broll_tool.py probe-media output.mp4
```

Use this before claiming an export is complete. Check at minimum:

- dimensions
- codec
- frame rate
- sample aspect ratio
- scan type
- audio codec
- audio sample rate

## Validate Export

Run:

```bash
python3 broll-finder/scripts/broll_tool.py validate-export output.mp4 \
  --preset vertical-social \
  --json-out BROLL-VALIDATION.json \
  --md-out BROLL-VALIDATION.md
```

Treat `fail` as blocking. Treat `warning` and `manual-review-required` as visible handoff items unless the user explicitly accepts them. For release or CI gates, add `--strict` so any non-`pass` report exits nonzero.

Current automated checks:

- MP4-compatible container
- expected dimensions
- H.264 video codec
- progressive scan
- square pixels
- yuv420p pixel format
- minimum frame rate for social presets
- AAC audio codec, if audio exists
- 48 kHz audio sample rate, if audio exists
- fast-start MP4 atom order when the file is available

## Export Variant

Run:

```bash
python3 broll-finder/scripts/broll_tool.py export-variant input.mp4 output.vertical.mp4 \
  --preset vertical-social
```

Use this after the main edit is approved. Variants should be generated from the finished master, then probed and validated independently.

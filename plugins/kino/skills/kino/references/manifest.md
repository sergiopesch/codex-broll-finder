# Manifest And Edit State

Use `KINO-MANIFEST.json` as the current executable source of truth for Phase 1 cutaway renders. It is intentionally small and maps directly to `validate-manifest`, `render-cutaways`, and `verify-frames`.

`KINO-EDIT.json` is the staged project-level format for the broader edit engine. It is not the complete execution format yet; treat it as the contract future graph execution should grow into while the cutaway manifest remains supported.

## Current Cutaway Manifest

```json
{
  "version": 1,
  "base": "input.mp4",
  "output": "output_with_kino.mp4",
  "size": [1920, 1080],
  "fps": 30,
  "beats": [
    {
      "id": "b001",
      "start": 2.2,
      "end": 5.1,
      "line": "Today we are using Codex to build this.",
      "interpretation": "The line introduces Codex as the tool being used.",
      "route": "product-ui",
      "asset": "assets/fmt/b001.mp4",
      "kind": "video",
      "source_in": 0.0,
      "status": "approved",
      "credit": "OpenAI / YouTube"
    }
  ],
  "removed": []
}
```

## Rules

- Beat ids are stable across renders.
- `start` and `end` are seconds in the base video.
- `kind` is `video` or `still`.
- Beats must be sorted and non-overlapping before rendering.
- Approved beats cannot be removed unless their id appears in `removed` with a reason.
- Keep raw downloads in `assets/raw/` and formatted render inputs in `assets/fmt/`.

## Future KINO-EDIT Shape

`KINO-EDIT.json` starts as planning state around transcripts, source receipts, asset candidates, and beat candidates:

```json
{
  "version": 2,
  "id": "demo",
  "transcript": {
    "id": "tx001",
    "language": "en",
    "source": "input.mp4",
    "words": [
      {"id": "w001", "text": "Kino", "start": 0.0, "end": 0.25, "speaker": "S1", "confidence": 0.98}
    ]
  },
  "sources": [
    {
      "id": "src001",
      "kind": "url",
      "locator": "https://example.com/source",
      "title": "Canonical source",
      "license": "manual-review-required"
    }
  ],
  "assets": [
    {
      "id": "asset001",
      "source_id": "src001",
      "kind": "web",
      "uri": "assets/raw/source.png",
      "score": 0.91
    }
  ],
  "beats": [
    {
      "id": "beat001",
      "token_start": 0,
      "token_end": 1,
      "route": "receipt",
      "interpretation": "Show the canonical source while this claim is spoken.",
      "source_plan": "Capture the source page.",
      "source_ids": ["src001"],
      "asset_ids": ["asset001"],
      "selected_asset_id": "asset001",
      "status": "approved"
    }
  ]
}
```

## Transcript-To-Manifest Planning

The second build planning loop is:

1. `init-edit` creates `KINO-EDIT.json` from project metadata, source media, and transcript tokens.
2. Codex proposes beat candidates against transcript token ranges. Proposed beats should include the route, interpretation, source plan, candidate sources/assets, and unresolved questions.
3. Approved beats are marked `approved` with the selected asset and enough timing information to become manifest beats.
4. Rejected beats stay in `KINO-EDIT.json` as `rejected` with a rationale. Do not silently delete them; they prevent repeated bad suggestions and preserve edit history.
5. `compile-manifest` writes approved, renderable beats into `KINO-MANIFEST.json`.
6. Rendering still uses `KINO-MANIFEST.json`: run `validate-manifest`, then `render-cutaways`, then `verify-frames`.

`KINO-EDIT.json` is allowed to hold incomplete or rejected planning state. `KINO-MANIFEST.json` should contain only renderable, approved cutaway beats.

## Render Graph

The first render graph implementation is a typed intermediate representation for the current cutaway manifest. It records:

- sources such as base media and cutaway media
- picture and base-audio tracks
- fixed-duration and open-ended clips
- output dimensions, FPS, codec defaults, and path
- validation expectations and midpoint/joint frame checks
- canonical JSON and stable graph hashes

Future graph execution can add explicit operation nodes such as `ingest-source`, `still-motion`, `overlay-cutaway`, `extract-verify-frames`, `export-variant`, `probe-media`, and `validate-export`. Those nodes need stable ids, explicit inputs and outputs, and a receipt path. Nodes should be idempotent: unchanged inputs and settings should produce the same command and materially equivalent media characteristics.

## Source Receipts

A source receipt records why an asset is allowed into the edit. It should include:

- receipt version and source id
- origin URL or local path
- retrieval method, timestamp, and operator/agent
- credit string and rights/license notes
- selected time range, crop, viewport, or screenshot settings
- raw asset path and checksum when available
- formatted asset path used by the renderer
- warnings or manual-review notes

## Render Receipts

A render receipt records how an artifact was produced. Current cutaway render receipts include:

- receipt schema
- manifest hash
- render graph hash
- command hash
- full command argv, not a shell string
- relevant tool versions such as ffmpeg and ffprobe
- manifest, source, output, formatted, and asset paths
- formatted-asset command argv for clips created during the render

Later receipts should add graph node ids, operation parameters, media probe summaries, validation report paths, warnings, failures, and manual-review notes. The long-term target is writing receipts beside generated artifacts under `receipts/sources/` and `receipts/renders/` so a final delivery can be audited without replaying the whole edit.

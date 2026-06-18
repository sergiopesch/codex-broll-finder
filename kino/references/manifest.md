# Manifest And Edit State

Use `KINO-MANIFEST.json` as the current executable source of truth for Phase 1 cutaway renders. It is intentionally small and maps directly to `validate-manifest`, `render-cutaways`, and `verify-frames`.

`KINO-EDIT.json` is the staged project-level format for the broader edit engine. It is not the complete execution format yet; treat it as the contract future graph execution should grow into while the cutaway manifest remains supported.

`KINO-PLAN.json` is the review artifact between transcript understanding and edit-state mutation. It lets Codex propose beat choices for approval before sourcing media, changing `KINO-EDIT.json`, or compiling a renderable manifest.

`KINO-CAPTIONS.json` is the transcript-derived caption artifact. It stores word-aligned caption segments, style presets, emphasized words, reasons, and confidence before ffmpeg burns captions into a rendered video.

`KINO-REVIEW.json` is the media-aware review artifact. It inspects the actual rendered/exported file, samples frames, checks audio, validates export settings, and records caption/archetype contract issues before final evaluation.

`KINO-EVAL.json` is the build/test/refine scorecard. It aggregates specialized reports into a normalized status, score, decision, and next-action list.

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

## KINO-PLAN Shape

`KINO-PLAN.json` is small enough for review and strict enough to validate before it enters project state. It does not expose seconds, durations, start ratios, end ratios, or selected assets:

```json
{
  "version": 1,
  "schema": "kino.plan.v1",
  "id": "demo:social-short:plan",
  "edit_id": "demo",
  "transcript_id": "tx001",
  "transcript_hash": "sha256:...",
  "archetype_id": "social-short",
  "aspect_ratio": "9:16",
  "summary": {
    "asset_count": 1,
    "cue_count": 4,
    "beat_count": 5,
    "average_confidence": 0.74,
    "review_notes": []
  },
  "cues": [],
  "beats": [
    {
      "id": "planbeat:01:hook",
      "role": "hook",
      "anchor": {
        "token_start": 0,
        "token_end": 6,
        "word_start_id": "w001",
        "word_end_id": "w006",
        "quote": "This mistake cost us a week"
      },
      "route": "hook",
      "interpretation": "Show the canonical source while this claim is spoken.",
      "source_plan": "Capture the source page after approval.",
      "fallback": "Use a generated explainer card if the page cannot be captured.",
      "confidence": 0.78,
      "reasons": ["Uses archetype section 'hook' from template 'hook'."],
      "cue_ids": ["cue:01:problem"],
      "asset_fits": [
        {
          "asset_id": "asset001",
          "source_id": "src001",
          "role": "product-ui",
          "score": 0.91,
          "reasons": ["asset role 'product-ui' matches beat role 'hook'"]
        }
      ]
    }
  ]
}
```

The CLI contract is:

1. `plan-edit KINO-EDIT.json KINO-PLAN.json --archetype social-short` creates proposed beats with reasons and confidence from transcript/source/asset state.
2. `validate-plan KINO-PLAN.json` checks schema, transcript anchors, confidence bounds, asset references, and editorial review metadata.
3. `apply-plan KINO-PLAN.json KINO-EDIT.json` imports validated proposed beats into `KINO-EDIT.json` without sourcing assets, approving taste decisions, or compiling render output.

Current rendering still starts from `KINO-MANIFEST.json`.

## KINO-CAPTIONS Shape

`KINO-CAPTIONS.json` is generated from `KINO-EDIT.json` transcript words and an archetype:

```json
{
  "version": 1,
  "schema": "kino.captions.v1",
  "id": "demo:social-short:captions",
  "edit_id": "demo",
  "transcript_id": "tx001",
  "transcript_hash": "sha256:...",
  "archetype_id": "social-short",
  "style": {
    "preset": "social-short-bold",
    "font": "Arial",
    "font_size": 64,
    "alignment": 2,
    "margin_v": 150,
    "max_chars_per_line": 18,
    "max_lines": 2,
    "uppercase": true
  },
  "segments": [
    {
      "id": "cap:001",
      "anchor": {
        "token_start": 0,
        "token_end": 5,
        "word_start_id": "w001",
        "word_end_id": "w005"
      },
      "start": 0.0,
      "end": 1.2,
      "text": "THIS MISTAKE COST A WEEK",
      "emphasized_words": ["mistake"],
      "confidence": 0.89,
      "reasons": ["Caption timing is derived from word alignment."]
    }
  ]
}
```

The CLI contract is:

1. `plan-captions KINO-EDIT.json KINO-CAPTIONS.json --archetype social-short` creates readable word-aligned caption segments.
2. `validate-captions KINO-CAPTIONS.json --edit KINO-EDIT.json` checks readability, token anchors, transcript hash parity, and confidence bounds.
3. `render-captions input.mp4 KINO-CAPTIONS.json output.captioned.mp4` writes an ASS sidecar and burns captions into the video.

## KINO-REVIEW Shape

`KINO-REVIEW.json` should be generated from the actual rendered or exported media file:

```json
{
  "version": 1,
  "schema": "kino.review.v1",
  "id": "kino-review",
  "media": "output.vertical.mp4",
  "preset": "vertical-social",
  "archetype_id": "social-short",
  "overall": "warning",
  "recommendations": ["Run plan-captions and render-captions before final review."],
  "artifacts": [
    {
      "kind": "frame-qc",
      "path": "review_frames",
      "summary": "3 sampled review frame(s)"
    }
  ],
  "checks": [
    {
      "name": "social_short_captions",
      "category": "archetype",
      "status": "warning",
      "expected": "caption artifact",
      "observed": "missing",
      "message": "Short-form videos usually need burned-in captions for silent autoplay.",
      "recommendation": "Run plan-captions and render-captions before final review."
    }
  ]
}
```

The CLI contract is:

1. `review-media output.vertical.mp4 --preset vertical-social --archetype social-short --captions KINO-CAPTIONS.json --frames-dir review_frames --contact-sheet KINO-REVIEW-SHEET.jpg --out KINO-REVIEW.json --md-out KINO-REVIEW.md`
2. Default exit behavior matches other Kino QC commands: nonzero only on `fail`.
3. `--strict` exits nonzero unless the direct review passes cleanly.

## KINO-EVAL Shape

`KINO-EVAL.json` should be generated after the available planning, caption, direct media review, frame, audio, and export checks:

```json
{
  "version": 1,
  "schema": "kino.eval.v1",
  "id": "kino-eval",
  "overall": "warning",
  "score": 0.842,
  "decision": "revise-before-handoff",
  "recommendations": ["Review 1 audio-qc warning/manual-review item(s)."],
  "artifacts": [
    {
      "kind": "audio-qc",
      "path": "KINO-AUDIO-QC.json",
      "status": "warning",
      "score": 0.65,
      "summary": "audio-qc overall warning with 1 check(s)"
    }
  ],
  "checks": [
    {
      "name": "audio-qc_issue_count",
      "category": "audio-qc",
      "status": "warning",
      "score": 0.5,
      "message": "audio-qc report has 0 fail(s) and 1 warning/manual-review item(s).",
      "recommendation": "Review 1 audio-qc warning/manual-review item(s).",
      "artifact": "KINO-AUDIO-QC.json"
    }
  ]
}
```

The CLI contract is:

1. `eval --plan KINO-PLAN.json --captions KINO-CAPTIONS.json --review KINO-REVIEW.json --frame-qc KINO-FRAME-QC.json --audio-qc KINO-AUDIO-QC.json --validation KINO-VALIDATION.json --out KINO-EVAL.json --md-out KINO-EVAL.md`
2. Default exit behavior matches other Kino QC commands: nonzero only on `fail`.
3. `--strict` exits nonzero unless the evaluation passes cleanly.

## Transcript-To-Manifest Planning

The second build planning loop is:

1. `init-edit` creates `KINO-EDIT.json` from project metadata, source media, and transcript tokens.
2. Codex proposes beat candidates against transcript token ranges, ideally as `KINO-PLAN.json` when a review step is needed. Proposed beats should include the route, interpretation, source plan, candidate sources/assets when known, fallback, and unresolved questions.
3. Validated plan beats are imported into `KINO-EDIT.json` as proposed state.
4. Approved beats are marked `approved` with the selected asset and enough timing information to become manifest beats.
5. Rejected beats stay in `KINO-EDIT.json` as `rejected` with a rationale. Do not silently delete them; they prevent repeated bad suggestions and preserve edit history.
6. `compile-manifest` writes approved, renderable beats into `KINO-MANIFEST.json`.
7. Rendering still uses `KINO-MANIFEST.json`: run `validate-manifest`, then `render-cutaways`, then `verify-frames`.

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

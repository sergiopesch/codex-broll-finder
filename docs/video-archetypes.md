# Video Archetypes

Last updated: 2026-06-17

Kino should not expose a timeline as the user interface. The user should express intent, approve taste decisions, and review artifacts. Kino can still compile that intent into an internal timeline, render graph, or execution plan.

This document captures real video formats Kino should learn to produce. Each archetype defines the editorial grammar the agent should plan, render, verify, and iterate.

Machine-readable fixtures live under `examples/archetypes/`. Use `kino list-archetypes` to inspect built-in templates, `kino plan-replica examples/archetypes/<id>/reference-analysis.json` to produce an intent-level beat plan, and `python3 examples/archetypes/run.py --workdir /tmp/kino-archetypes` to generate tiny synthetic replica skeletons without committing reference media.

## 1. Social Short

Reference example: `https://youtube.com/shorts/jsBikM65h5w`

Target platforms:

- YouTube Shorts
- TikTok
- Instagram Reels
- LinkedIn/X vertical clips

Typical shape:

- duration: 15-60 seconds
- aspect ratio: 9:16
- primary spine: talking head or voiceover
- goal: retention, clarity, proof, and a fast payoff

Observed structure:

```text
0-2s: provocative hook
2-9s: problem/confession
9-14s: fix or upgrade claim
14-19s: proof/demo
19-28s: product/site CTA
```

Editing grammar:

- talking head remains the narrative spine
- no meaningful dead air
- hard cuts beat fancy transitions
- visual proof every 2-4 seconds
- bold burned-in captions, usually 1-4 emphasized words at a time
- UI/product/object inserts are tied to transcript meaning
- final section becomes CTA or proof montage

Agent planning primitives:

- hook detector
- speech compression and filler/dead-air removal
- semantic emphasis-caption planner
- proof-insert planner for concrete claims
- vertical UI/screen formatter with safe readable scale
- CTA montage generator
- frame/audio/caption QC reports

Kino advantage:

The agent should understand claims and find proof visuals automatically. CapCut gives manual controls; Kino should decide that "new agent" needs an agent UI insert, "parts" needs hardware footage, and "website" needs a site montage.

## 2. Founder Product Explainer

Reference example: `https://www.youtube.com/watch?v=Con4KzJsSmg`

Target platforms:

- YouTube
- landing-page embeds
- Product Hunt / launch pages
- investor/customer updates
- long-form social clips

Typical shape:

- duration: 60-120 seconds
- aspect ratio: usually 16:9, with possible 9:16 cutdown
- primary spine: founder-led explanation
- goal: make the problem, product promise, demo, and CTA understandable

Observed structure:

```text
0-6s: cold open with surprising result
6-24s: origin story and user problem
24-36s: product positioning
36-56s: live product walkthrough
56-72s: physical/product proof
72-80s: CTA
```

Editing grammar:

- slower than a Short, but still tightly compressed
- talking head introduces motivation and transitions
- captions support clarity rather than pure retention hacking
- product UI is shown long enough to understand the workflow
- physical/object proof validates the product claim
- screen recordings and face-camera picture-in-picture can coexist
- CTA is clean and explicit

Agent planning primitives:

- narrative arc planner: hook, problem, product, demo, proof, CTA
- screen-recording selector and crop planner
- picture-in-picture facecam layout
- product-demo step detector
- proof-shot selector for real-world validation
- caption planner optimized for clarity
- 16:9 master plus 9:16 cutdown compiler
- demo continuity QC: every claim should have either visible UI proof or spoken context

Kino advantage:

The agent should produce a coherent launch/demo edit from raw founder footage, screen recordings, and product assets. The user should approve story beats and proof choices, not arrange clips on a timeline.

## Build Implications

These two archetypes now feed `KINO-PLAN.json`: `kino plan-edit KINO-EDIT.json KINO-PLAN.json --archetype social-short` or `--archetype founder-product-explainer` turns transcript, source, and asset state into proposed beats with token anchors, reasons, asset-fit scores, and confidence. They also feed `KINO-CAPTIONS.json`: `kino plan-captions KINO-EDIT.json KINO-CAPTIONS.json --archetype social-short` creates word-aligned caption segments and archetype-specific styles. The user reviews intent; Kino owns the internal timing and render compilation.

These two archetypes point to the next foundation:

1. Transcription and word alignment as the timing spine.
2. Caption planning and rendering as first-class output.
3. Intent-level edit plans with internal render graph/timeline compilation.
4. Proof sourcing and source receipts for claims.
5. Review artifacts: beat plan, contact sheet, caption frames, proof map, QC reports.
6. Platform variants from the same approved intent, not separate manual edits.

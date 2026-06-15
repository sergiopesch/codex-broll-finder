# Codex B-Roll Finder Product Specification

Last updated: 2026-06-15

## 1. Executive Summary

`codex-broll-finder` should become an open-source Codex-native video editing system. The initial product is a b-roll specialist for talking-head edits. The expanded product is a reproducible editing layer where Codex can plan, source, assemble, validate, and export professional video edits without relying on a GUI timeline.

The system should learn from the quality bar of Final Cut Pro, DaVinci Resolve, Premiere Pro, After Effects, CapCut, Descript, and Runway, but it should not clone their interfaces. The differentiator is agentic editing: structured intent, source-aware assets, manifests, deterministic renders, and verifiable outputs.

## 2. Codex Surface Decision

### Recommendation

Build the editing workflow as a **skill first**, then package it as a **plugin** for distribution.

### Rationale

Codex skills are the right authoring unit for reusable task workflows. They package instructions, references, and scripts, and Codex can invoke them explicitly or implicitly when a prompt matches the skill description.

Codex plugins are the right distribution unit when a workflow should be installable by others or when it bundles multiple skills, apps, MCP servers, hooks, or assets. This project should become a plugin once the workflow stabilizes and the repo needs marketplace installation.

### Plugin Readiness Criteria

Do not package a public plugin until:

- `SKILL.md` triggers reliably from realistic user prompts.
- The CLI works from a clean install.
- At least one sample project renders end-to-end.
- Validation produces a pass/fail report, not only logs.
- External dependencies are declared clearly.
- The plugin manifest and marketplace entry are tested locally.

## 3. Product Principles

1. **Intent beats timeline manipulation**: the user expresses the desired edit; Codex produces a plan and manifest.
2. **Objective media first**: receipts, real UI, official footage, and canonical source material beat generic stock.
3. **No silent drift**: approved beats, captions, effects, and audio changes remain in the manifest across revisions.
4. **Every render is inspectable**: outputs include source metadata, commands, verification frames, and quality reports.
5. **Professional defaults**: full-bleed video, clean audio, readable text, safe-zone awareness, and platform-correct exports.
6. **Human taste gates**: Codex narrows options; users approve taste-heavy choices.

## 4. User Workflows

### 4.1 B-Roll Edit

Input:

- transcript or source video/audio
- optional user profile
- optional trusted source list

Flow:

1. transcribe or parse transcript
2. identify b-roll beats
3. classify each beat by route
4. present plan for approval
5. source assets by origin
6. render silent full-bleed cutaways
7. verify midpoint and joint frames
8. export final video and manifest

Output:

- edited video
- `BROLL-MANIFEST.json`
- `BROLL-MANIFEST.md`
- verification frames
- source/license notes

### 4.2 Full Codex Edit

Input:

- media folder, script, or rough cut
- target platforms
- creative brief

Flow:

1. inspect media
2. create edit plan with story beats
3. propose timeline operations
4. normalize audio and assemble picture
5. add b-roll, captions, titles, motion graphics, effects, transitions
6. export platform variants
7. validate technical and editorial quality

Output:

- timeline manifest
- project cache
- platform exports
- QC report

## 5. Architecture

### 5.1 Skill Layer

Location: `broll-finder/SKILL.md`

Responsibilities:

- define Codex workflow
- require plan-before-source behavior
- route Codex to references and helper tools
- keep context small through progressive disclosure

### 5.2 Reference Layer

Location: `broll-finder/references/`

Responsibilities:

- routing rules
- profile schema
- manifest schema
- verification rules
- export specs
- editorial quality rubrics

### 5.3 Tooling Layer

Location: `src/codex_broll_finder/`

Responsibilities:

- manifest validation
- ffmpeg command generation
- still image motion
- browser capture
- render orchestration
- verification frame extraction
- export preset validation

### 5.4 Future Plugin Layer

Target:

```text
plugins/codex-broll-finder/
├── .codex-plugin/plugin.json
├── skills/broll-finder/
├── assets/
├── scripts/
└── marketplace metadata
```

Responsibilities:

- installable package
- marketplace discoverability
- bundled skills and tools
- optional MCP/app integrations
- optional hooks for validation before final delivery

### 5.5 Optional MCP/App Layer

Possible future integrations:

- local media index MCP server
- frame/audio analysis MCP server
- editor project import/export bridge
- stock library connectors
- asset-library connector
- caption/transcription service connector

## 6. Editing Capability Spec

### 6.1 Video Assembly

Must support:

- trim, split, concat
- insert and replace visual ranges
- cover-crop and blur-fill
- constant frame-rate exports
- no accidental letterboxing
- source and output duration reconciliation
- render cache reuse

Quality criteria:

- no black frames at joins
- no flash frames under 3 frames unless deliberate
- no VFR stutter in final output
- no unexpected resolution or SAR changes

### 6.2 Audio

Must support:

- preserve base narration by default
- strip b-roll audio by default
- optional source audio ducking
- gain normalization
- fade in/out
- crossfades
- peak and integrated loudness analysis
- silence and clipping detection

Target defaults:

- spoken-word integrated loudness: `-16 LUFS` for stereo web exports
- true peak: `<= -1.0 dBTP`
- sample rate: `48 kHz`
- codec: AAC for MP4 exports

Quality criteria:

- no clipping
- no abrupt audio cuts at edit boundaries
- music and b-roll audio do not mask narration
- captions match audible words

### 6.3 Text And Captions

Must support:

- captions from word timestamps
- burned-in captions
- sidecar captions (`.srt`, later `.vtt`)
- titles and lower thirds
- source-credit overlays
- safe-zone checks
- dynamic text wrapping

Quality criteria:

- captions are readable on mobile
- text never exceeds safe zones
- captions do not cover faces, key UI, or platform controls
- title animations do not distract from narration

### 6.4 Animation And Motion Graphics

Must support:

- subtle still zooms using sub-pixel rendering
- on-brand stat cards
- simple charts
- progress/process animations
- motion graphic import from an existing Remotion project

Quality criteria:

- no shaky `zoompan`-style motion
- no generic template look
- no generated card when literal footage exists
- animation timing supports the spoken beat

### 6.5 Effects

Must support:

- crop, scale, blur-fill
- color-space preservation
- simple color correction
- background blur
- overlay opacity
- source-credit compositing

Should support later:

- masks
- keying
- motion tracking
- face/subject-safe reframing
- noise reduction
- stabilization

Quality criteria:

- effects are reversible in manifest
- visual treatment is consistent across related beats
- no unreadable blur/fill artifacts

### 6.6 Transitions

Default:

- hard cuts for b-roll and talking-head editorial work

Must support:

- audio crossfades
- video dissolve
- dip-to-color
- motion transition only when explicitly requested

Quality criteria:

- transitions must be intentional and named in the plan
- no transition masks bad timing
- adjacent b-roll should connect instead of flashing back to face for under 1s

### 6.7 Sourcing

Must support:

- channel-scoped YouTube metadata search
- page/tweet/headline capture
- local asset reuse
- source authority scoring
- cached raw assets

Quality criteria:

- no random open-source footage when authoritative source exists
- no watermarked stock previews
- no stale product UI for current product claims
- source URL and credit retained

### 6.8 Export

Must support:

- platform presets
- aspect-ratio variants
- safe-zone overlays during validation
- MP4/H.264/AAC web export
- high-quality mezzanine export later

Quality criteria:

- progressive scan
- square pixels
- fast-start MP4
- consistent frame rate
- no letterboxing/pillarboxing
- audio sample rate 48 kHz

## 7. Export Presets

These are implementation defaults, not legal promises. Validate against platform docs during release because specs change.

| Preset | Size | Ratio | FPS | Codec | Audio | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `vertical-social` | 1080x1920 | 9:16 | 30 or source | H.264 MP4 | AAC 48 kHz | Default for Shorts, Reels, TikTok |
| `square-social` | 1080x1080 | 1:1 | 30 or source | H.264 MP4 | AAC 48 kHz | Feed-compatible fallback |
| `portrait-feed` | 1080x1350 | 4:5 | 30 or source | H.264 MP4 | AAC 48 kHz | LinkedIn/Meta feed style |
| `landscape-web` | 1920x1080 | 16:9 | source | H.264 MP4 | AAC 48 kHz | YouTube/web standard |
| `archive-master` | source or 4K | native | source | ProRes/DNxHR later | PCM later | Future mezzanine |

### Platform Baselines Checked 2026-06-15

- YouTube recommends MP4, H.264, AAC-LC/Opus/Eclipsa audio, 48 kHz sample rate, progressive scan, 4:2:0 chroma, and preserving the recorded frame rate. YouTube lists 1080p SDR upload bitrate guidance at 8 Mbps for standard frame rates and 12 Mbps for high frame rates.
- YouTube formatting guidance says uploads should use native aspect ratios and should not include letterboxing or pillarboxing.
- TikTok Auction In-Feed Ads list vertical 9:16 at at least 540x960, horizontal 16:9 at at least 960x540, square 1:1 at at least 640x640, file formats including MP4/MOV/MPEG/3GP/AVI, duration up to 10 minutes, file size up to 500 MB, and bitrate at least 516 kbps.
- Instagram Reels Help says reels can be uploaded between 1.91:1 and 9:16, with minimum 30 FPS and minimum resolution requirements. Meta safe-zone docs should be rechecked interactively because public access redirected to login from this environment.
- LinkedIn video ads list MP4, AAC or MPEG4 sound, 30 FPS recommendation, ratios 4:5, 9:16, 16:9, and 1:1, duration 3 seconds to 30 minutes, and dimensions up to 1920x1920 depending on ratio.

## 8. Quality Bar Inspired By Professional Editors

### Final Cut Pro Lessons

- real-time preview matters
- magnetic sequencing is valuable, but manifests should make movement explicit
- metadata and libraries are product features, not implementation details

### DaVinci Resolve Lessons

- color and audio quality cannot be afterthoughts
- scopes, loudness, and QC reports should be first-class
- professional export presets need exact technical control

### Premiere Pro / After Effects Lessons

- timeline interchange and compositing matter
- motion graphics should be reusable templates, not one-off generated media
- captions and titles need style systems

### CapCut / Descript Lessons

- social-first defaults matter
- transcript editing is a powerful UI model
- fast iteration beats complex manual setup

### Codex-Native Difference

- the user approves intent, not keyframes
- every edit is represented as structured data
- every output has a reproducible command path
- every render has testable quality criteria

## 9. Manifest Model

Future timeline manifest should include:

- project metadata
- source assets
- transcript tokens
- tracks
- clips
- effects
- captions
- transitions
- audio operations
- exports
- validation results

Every operation must be:

- idempotent
- reversible or explicitly destructive
- traceable to a user request, skill rule, or generated plan
- validated before final delivery

## 10. Test Plan

### Unit Tests

Required:

- manifest parsing
- overlapping beat rejection
- duplicate id rejection
- export preset validation
- safe-zone geometry
- ffmpeg command generation
- source scoring
- text wrapping
- timestamp anchoring
- loudness parser

### Integration Tests

Required:

- render one b-roll beat over base video
- render adjacent beats with no face flash
- export 9:16, 1:1, 4:5, and 16:9 variants
- generate verification frames
- preserve base audio
- strip b-roll audio
- generate sidecar captions

### Golden Media Tests

Use committed tiny synthetic fixtures:

- color bars
- tone audio
- speech sample
- portrait still
- landscape still
- short b-roll clip
- caption sample

Assertions:

- frame dimensions
- duration tolerance within 1 frame
- audio stream exists or is stripped as expected
- black-frame detection
- frozen-frame detection
- crop coverage
- caption timing
- safe-zone text bounds

### Visual Regression Tests

Generate contact sheets and compare:

- beat midpoints
- b-roll joints
- caption frames
- title frames
- export safe-zone overlays

Threshold:

- structural checks must be deterministic
- perceptual diffs can be warning-level at first
- final release should fail on major visual drift

### Audio QC Tests

Check:

- integrated loudness
- true peak
- clipping
- silence gaps
- abrupt jumps at cuts
- channel count
- sample rate

### End-To-End Acceptance Tests

Each release must include a sample command that:

1. validates a manifest
2. renders a sample edit
3. extracts QC frames
4. runs media probes
5. exports social variants
6. produces a validation report

## 11. Validation Report

Every render should produce `BROLL-VALIDATION.json` and `BROLL-VALIDATION.md`.

Required fields:

- input media probes
- output media probes
- export preset compliance
- duration comparison
- frame checks
- audio checks
- caption checks
- safe-zone checks
- source/license notes
- human inspection checklist

Pass/fail categories:

- `pass`
- `warning`
- `fail`
- `manual-review-required`

## 12. CLI Roadmap

Current:

- `validate-manifest`
- `zoom-still`
- `capture-page`
- `render-cutaways`
- `verify-frames`

Next:

- `probe-media`
- `validate-export`
- `export-variant`
- `render-captions`
- `check-safe-zones`
- `analyze-audio`
- `make-contact-sheet`
- `write-report`
- `init-profile`
- `init-plugin`

## 13. Open-Source Requirements

Before broader announcement:

- CONTRIBUTING.md
- CODE_OF_CONDUCT.md
- SECURITY.md
- issue templates
- example project with tiny generated fixtures
- CI for tests and lint
- release workflow
- license attribution maintained
- docs on copyright/source responsibility
- clear non-goals

## 14. Privacy, Rights, And Safety

The tool should:

- keep local media local by default
- avoid uploading private videos without explicit user action
- record sources and licenses
- distinguish etiquette credit from actual usage rights
- reject or flag scraped/watermarked/unauthorized assets
- avoid representing generated content as real footage
- require confirmation for publishing, posting, or paid actions

## 15. Release Phases

### Phase 0: Repo Foundation

Done when:

- public repo exists
- skill validates
- tests pass
- basic CLI works
- product spec exists

### Phase 1: B-Roll MVP

Done when:

- sample b-roll edit renders end-to-end
- manifest and validation report are generated
- verification frames are extracted
- export presets validate

### Phase 2: Social Editing Core

Done when:

- captions, titles, audio normalization, and export variants are supported
- platform safe-zone checks exist
- audio/video QC report catches common defects

### Phase 3: Plugin Packaging

Done when:

- `.codex-plugin/plugin.json` exists
- skill is moved or mirrored into plugin structure
- local marketplace install works
- install docs are tested
- plugin can be shared through a Codex marketplace source

### Phase 4: Professional Editing Loop

Done when:

- multi-pass revisions preserve manifest state
- Codex can make targeted edits without full re-render when possible
- project can round-trip through structured state
- visual/audio regression suite gates releases

## 16. Source References

- OpenAI Codex manual, Agent Skills section: skills package instructions, references, and scripts; plugins are the distribution unit for reusable skills and apps.
- OpenAI Codex manual, Build Plugins section: start with local skills while iterating; build a plugin when sharing workflows, bundling app/MCP config, hooks, or publishing a stable package.
- YouTube Help, recommended upload encoding settings: MP4, H.264, audio/sample-rate, frame-rate, bitrate, and color guidance.
- YouTube Help, video/audio formatting specifications: native frame rates, native aspect ratios, no letterboxing/pillarboxing.
- TikTok Business Help, Auction In-Feed Ads: dimensions, duration, file format, file size, bitrate, and safe-zone guidance.
- Instagram Help Center, Reel size and aspect ratios: aspect-ratio range, frame-rate, and resolution guidance.
- LinkedIn Marketing Solutions, Video Ads Specifications: format, audio, frame-rate, ratio, duration, file-size, and dimensions.

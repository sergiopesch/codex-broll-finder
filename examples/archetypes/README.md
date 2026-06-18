# Archetype Fixtures

These fixtures capture lightweight planning contracts for two reference video archetypes without committing video blobs, downloaded media, generated captures, or binary assets.

Each archetype directory contains:

- `recipe.json`: a planner-facing contract for the archetype, including reference metadata, observed scene timing, transcript cue snippets, section structure, replica plan inputs, expected outputs, and quality gates.
- `reference-analysis.json`: machine-readable reference observations for `kino plan-replica`.
- `KINO-EDIT.json`: a canonical `KINO-EDIT` v2 fixture that current core code can load with `kino.edit.KinoEdit.from_json` and compile with `kino.compile.compile_edit_to_manifest`.

The JSON files intentionally use placeholder media URIs such as `inputs/...` and `planned/...`. They describe required source material and expected planner output, but they do not require those files to exist. Runners that render media must resolve or generate these placeholders outside the repository.

Generate tiny synthetic replica skeletons without committing media blobs:

```bash
python3 examples/archetypes/run.py --workdir /tmp/kino-archetypes
python3 examples/archetypes/run.py --workdir /tmp/kino-archetypes-render --archetype founder-product-explainer --render
```

Plan from a reference-analysis fixture:

```bash
kino plan-replica examples/archetypes/social-short/reference-analysis.json \
  --json-out /tmp/kino-social-replica-plan.json
```

`plan-replica` writes an intent-level replica plan, not `KINO-PLAN.json`. Use `kino eval --plan ...` only with review plans produced by `kino plan-edit`; use these fixtures and the runner to validate the doc-to-edit-to-manifest bridge.

## Recipe Contract

`recipe.json` uses `recipe_schema_version: 1` with this shape:

- `id`: stable fixture id.
- `archetype`: stable archetype id, display name, and editorial goal.
- `reference`: source URL and repo-safety notes for the observed reference.
- `target`: target duration, aspect ratio, platform variants, and pacing.
- `observed_scene_timing`: ordered timing observations from the reference, in seconds.
- `structure_sections`: reusable story sections with intent, timing, visuals, and planning primitives.
- `transcript_cue_snippets`: short cue snippets aligned to timing observations; these are anchors, not full transcripts.
- `replica_plan`: intended planner inputs and outputs for producing a similar edit from user-owned footage and assets.
- `core_consumable_fixtures`: files in the directory that current core code should parse.
- `quality_gates`: checks the planner or reviewer should satisfy before a recipe is considered ready.

## Current Core Consumption

The current stable machine-consumable fixture is `KINO-EDIT.json`. It contains:

- `transcript.words`: word-aligned cue tokens that provide the timing spine.
- `sources`: source receipts for the reference, user-owned input categories, generated caption treatments, and planned captures.
- `assets`: placeholder asset candidates that point to repo-safe paths rather than committed media.
- `beats`: approved beat candidates mapping transcript token ranges to proof/caption/demo assets.

The higher-level `recipe.json` contract is plain JSON until dedicated recipe APIs exist.

## Runner Integration

The runner starts with built-in tiny recipes, then loads JSON recipes from `--recipe-dir` and `--recipe` paths. With the default `--recipe-dir`, it adapts the checked-in `*/recipe.json` reference contracts into tiny runtime recipes by turning cue snippets into synthetic transcript words, still assets, approved beats, `KINO-EDIT.json`, and `KINO-MANIFEST.json`. Custom JSON recipes override built-ins by archetype id.

The runner validates the current bridge from repo-safe archetype docs to executable cutaway manifests. It does not download reference videos, does not source real user footage, and does not promise full-fidelity replication. The optional `--render` flag only runs the existing `kino render-cutaways` command against the generated manifest, and KINO-REVIEW/KINO-EVAL remain separate media-review and aggregation steps over rendered media, `KINO-PLAN.json`, caption, or QC artifacts produced elsewhere.

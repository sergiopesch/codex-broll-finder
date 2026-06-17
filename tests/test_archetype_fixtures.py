import json
from pathlib import Path

from kino.archetypes import classify_archetype, load_reference_analysis_json, plan_replica_beats
from kino.compile import compile_edit_to_manifest
from kino.edit import KinoEdit


ARCHETYPE_ROOT = Path(__file__).resolve().parents[1] / "examples" / "archetypes"
REQUIRED_RECIPE_KEYS = {
    "recipe_schema_version",
    "id",
    "archetype",
    "reference",
    "target",
    "observed_scene_timing",
    "structure_sections",
    "transcript_cue_snippets",
    "replica_plan",
    "core_consumable_fixtures",
    "quality_gates",
}


def archetype_dirs():
    ignored = {"__pycache__", "out", "recipes"}
    return tuple(path for path in sorted(ARCHETYPE_ROOT.iterdir()) if path.is_dir() and path.name not in ignored)


def test_archetype_recipe_contract_is_present_and_repo_safe():
    dirs = archetype_dirs()

    assert [path.name for path in dirs] == ["founder-product-explainer", "social-short"]
    for directory in dirs:
        recipe = json.loads((directory / "recipe.json").read_text())

        assert REQUIRED_RECIPE_KEYS <= set(recipe)
        assert recipe["recipe_schema_version"] == 1
        assert recipe["reference"]["url"].startswith("https://")
        assert "Do not commit downloaded" in recipe["reference"]["media_policy"]
        assert len(recipe["observed_scene_timing"]) >= 5
        assert len(recipe["structure_sections"]) >= 5
        assert len(recipe["transcript_cue_snippets"]) >= 5
        assert recipe["replica_plan"]["inputs"]
        assert recipe["replica_plan"]["planner_outputs"]
        assert recipe["core_consumable_fixtures"] == [
            {
                "path": "KINO-EDIT.json",
                "format": "KINO-EDIT v2",
                "consumer": "kino.edit.KinoEdit.from_json and kino.compile.compile_edit_to_manifest",
            }
        ]


def test_archetype_edit_fixtures_load_and_compile_without_media_files():
    for directory in archetype_dirs():
        edit = KinoEdit.from_json((directory / "KINO-EDIT.json").read_text())
        manifest = compile_edit_to_manifest(
            edit,
            base=f"inputs/{directory.name}/primary-spine.mp4",
            output=f"out/{directory.name}.mp4",
            size=tuple(json.loads((directory / "recipe.json").read_text())["target"]["master_size"]),
        )

        assert len(edit.transcript.words) > 0
        assert len(manifest.beats) == len(edit.beats)
        assert all(beat.status == "planned" for beat in manifest.beats)
        assert all(not beat.asset.is_absolute() for beat in manifest.beats)


def test_reference_analysis_fixtures_classify_and_plan_replica_beats():
    expected = {
        "social-short": "social-short",
        "founder-product-explainer": "founder-product-explainer",
    }

    for directory in archetype_dirs():
        analysis = load_reference_analysis_json(directory / "reference-analysis.json")
        match = classify_archetype(analysis)
        plan = plan_replica_beats(analysis)

        assert match.archetype_id == expected[directory.name]
        assert plan.archetype_id == expected[directory.name]
        assert plan.beats
        assert all(beat.intent for beat in plan.beats)
        assert all(beat.visual_plan for beat in plan.beats)

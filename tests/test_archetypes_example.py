from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from kino.manifest import load_manifest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "examples" / "archetypes" / "run.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("kino_archetypes_runner", RUNNER)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _patch_runtime_generation(module, monkeypatch):
    monkeypatch.setattr(module, "_require_tools", lambda *tools: None)
    monkeypatch.setattr(module, "_require_python_modules", lambda *modules: None)

    def fake_generate_base_video(path, recipe):
        path.write_text(f"synthetic base for {recipe.id}\n")

    def fake_generate_visuals(directory, recipe):
        directory.mkdir(parents=True, exist_ok=True)
        paths = {}
        for visual in recipe.visuals:
            path = directory / visual.filename
            path.write_text(f"synthetic visual for {visual.id}\n")
            paths[visual.id] = path
        return paths

    monkeypatch.setattr(module, "_generate_base_video", fake_generate_base_video)
    monkeypatch.setattr(module, "_generate_visuals", fake_generate_visuals)


def test_builtin_archetype_runner_writes_replica_contracts(tmp_path, monkeypatch):
    module = _load_runner()
    _patch_runtime_generation(module, monkeypatch)

    outputs = module.run_archetypes(tmp_path, recipe_dir=tmp_path / "no-recipes")

    assert sorted(outputs) == ["founder-product-explainer", "social-short"]
    social = outputs["social-short"]
    founder = outputs["founder-product-explainer"]

    social_manifest = load_manifest(social["manifest"])
    founder_manifest = load_manifest(founder["manifest"])

    assert social_manifest.size == (180, 320)
    assert [beat.id for beat in social_manifest.beats] == ["beat.hook", "beat.proof", "beat.cta"]
    assert social_manifest.beats[0].asset == social["directory"] / "assets" / "hook.png"

    assert founder_manifest.size == (320, 180)
    assert [beat.id for beat in founder_manifest.beats] == [
        "beat.cold-open",
        "beat.walkthrough",
        "beat.proof-shot",
    ]

    summary = json.loads(social["summary"].read_text())
    assert summary["schema"] == "kino.archetype.replica.v1"
    assert summary["contract"]["media_policy"] == "All binary media is generated at runtime under the workdir."
    assert summary["contract"]["rendered"] is False
    assert "render" not in summary["outputs"]

    edit = json.loads(social["edit"].read_text())
    assert edit["sources"][0]["kind"] == "generated"
    assert edit["sources"][0]["locator"] == "fixture-recipe:social-short"


def test_json_fixture_recipe_overrides_builtin_when_available(tmp_path):
    module = _load_runner()
    recipe_path = tmp_path / "social-short.json"
    recipe_path.write_text(
        json.dumps(
            {
                "id": "social-short",
                "title": "Fixture override",
                "archetype": "social-short",
                "size": [120, 200],
                "fps": 24,
                "duration": 0.5,
                "words": [{"text": "Override", "start": 0.0, "end": 0.5}],
                "visuals": [{"id": "card", "label": "Fixture card"}],
                "beats": [
                    {
                        "id": "beat.fixture",
                        "token_start": 0,
                        "token_end": 1,
                        "route": "concept",
                        "interpretation": "Use the fixture recipe instead of the built-in.",
                        "source_plan": "Generate a fixture card.",
                        "asset_id": "card",
                    }
                ],
            }
        )
    )

    recipes = module.load_recipes(recipe_dir=tmp_path)

    assert recipes["social-short"].title == "Fixture override"
    assert recipes["social-short"].origin == str(recipe_path)
    assert recipes["social-short"].size == (120, 200)


def test_reference_recipe_fixture_shape_compiles_to_tiny_runtime_recipe(tmp_path):
    module = _load_runner()
    recipe_path = tmp_path / "recipe.json"
    recipe_path.write_text(
        json.dumps(
            {
                "recipe_schema_version": 1,
                "id": "social-short.reference-recipe",
                "archetype": {"id": "social-short", "name": "Social Short"},
                "target": {"aspect_ratio": "9:16", "fps": 30},
                "transcript_cue_snippets": [
                    {
                        "id": "cue.hook",
                        "section": "hook",
                        "snippet": "Stop hiding proof.",
                        "proof_requirement": "Use retention caption.",
                    },
                    {
                        "id": "cue.proof",
                        "section": "proof",
                        "snippet": "Show the product UI.",
                        "proof_requirement": "Show product UI proof.",
                    },
                ],
            }
        )
    )

    recipe = module.load_recipes(recipe_dir=tmp_path)["social-short"]

    assert recipe.origin == str(recipe_path)
    assert recipe.size == (180, 320)
    assert recipe.duration == 2.8
    assert [beat.id for beat in recipe.beats] == ["beat.hook", "beat.proof"]
    assert recipe.beats[1].route == "product-ui"


def test_render_flag_runs_existing_kino_render_command(tmp_path, monkeypatch):
    module = _load_runner()
    _patch_runtime_generation(module, monkeypatch)
    calls = []

    def fake_run(command, *, cwd, env=None):
        calls.append((command, cwd, env))

    monkeypatch.setattr(module, "_run", fake_run)

    outputs = module.run_archetypes(
        tmp_path,
        archetype="social-short",
        recipe_dir=tmp_path / "no-recipes",
        render=True,
        python="/python",
    )

    assert "render" in outputs["social-short"]
    assert len(calls) == 1
    command, cwd, env = calls[0]
    assert command == ["/python", "-m", "kino.cli", "render-cutaways", "KINO-MANIFEST.json"]
    assert cwd == outputs["social-short"]["directory"]
    assert env is not None


def test_render_flag_sets_pythonpath_for_kino_cli(tmp_path, monkeypatch):
    module = _load_runner()
    _patch_runtime_generation(module, monkeypatch)
    calls = []

    def fake_run(command, *, cwd, env=None):
        calls.append((command, cwd, env))

    monkeypatch.setattr(module, "_run", fake_run)

    module.run_archetypes(
        tmp_path,
        archetype="social-short",
        recipe_dir=tmp_path / "no-recipes",
        render=True,
        python="/python",
    )

    command, cwd, env = calls[0]
    assert command == ["/python", "-m", "kino.cli", "render-cutaways", "KINO-MANIFEST.json"]
    assert cwd == tmp_path.resolve() / "social-short"
    assert str(ROOT / "src") in env["PYTHONPATH"].split(module.os.pathsep)


def test_examples_archetypes_contains_no_committed_binary_media():
    media_suffixes = {".aac", ".gif", ".jpg", ".jpeg", ".m4a", ".mov", ".mp3", ".mp4", ".png", ".wav", ".webp"}
    ignored_parts = {"__pycache__", "out"}

    binary_media = [
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "examples" / "archetypes").rglob("*")
        if path.is_file()
        and path.suffix.lower() in media_suffixes
        and not (set(path.parts) & ignored_parts)
    ]

    assert binary_media == []

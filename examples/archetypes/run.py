#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from kino.compile import compile_edit_to_manifest, write_manifest_json  # noqa: E402
from kino.edit import AssetCandidate, BeatCandidate, KinoEdit, SourceReceipt, Transcript, WordToken, write_edit_json  # noqa: E402


DEFAULT_WORKDIR = Path(__file__).resolve().parent / "out"
DEFAULT_RECIPE_DIR = Path(__file__).resolve().parent / "recipes"
SUMMARY_FILENAME = "KINO-ARCHETYPE-RUN.json"


class ArchetypeRunnerError(RuntimeError):
    pass


@dataclass(frozen=True)
class VisualRecipe:
    id: str
    filename: str
    label: str
    background: tuple[int, int, int]
    accent: tuple[int, int, int]


@dataclass(frozen=True)
class BeatRecipe:
    id: str
    token_start: int
    token_end: int
    route: str
    interpretation: str
    source_plan: str
    asset_id: str
    fallback: str


@dataclass(frozen=True)
class ArchetypeRecipe:
    id: str
    title: str
    archetype: str
    size: tuple[int, int]
    fps: int
    duration: float
    tone_hz: int
    preset: str
    words: tuple[WordToken, ...]
    visuals: tuple[VisualRecipe, ...]
    beats: tuple[BeatRecipe, ...]
    origin: str = "builtin"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate tiny reproducible Kino archetype replicas with synthetic media."
    )
    parser.add_argument("--workdir", type=Path, default=DEFAULT_WORKDIR, help="Directory for generated outputs.")
    parser.add_argument(
        "--archetype",
        default="all",
        help="Recipe id to generate, or 'all'. Built-ins: social-short, founder-product-explainer.",
    )
    parser.add_argument(
        "--recipe-dir",
        type=Path,
        default=DEFAULT_RECIPE_DIR,
        help="Optional directory of JSON fixture recipes. Files in this directory override built-ins by id.",
    )
    parser.add_argument(
        "--recipe",
        action="append",
        type=Path,
        default=[],
        help="Optional JSON fixture recipe file. May be passed more than once.",
    )
    parser.add_argument(
        "--render",
        action="store_true",
        help="Also run kino.cli render-cutaways for each generated manifest.",
    )
    parser.add_argument("--python", default=sys.executable, help="Python executable used when --render is enabled.")
    args = parser.parse_args(argv)

    try:
        outputs = run_archetypes(
            args.workdir,
            archetype=args.archetype,
            recipe_dir=args.recipe_dir,
            recipe_paths=tuple(args.recipe),
            render=args.render,
            python=args.python,
        )
    except ArchetypeRunnerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print("Kino archetype replicas complete")
    for recipe_id, paths in outputs.items():
        print(f"{recipe_id}: {paths['directory']}")
        print(f"  edit: {paths['edit']}")
        print(f"  manifest: {paths['manifest']}")
        print(f"  summary: {paths['summary']}")
        if "render" in paths:
            print(f"  render: {paths['render']}")
    return 0


def run_archetypes(
    workdir: Path,
    *,
    archetype: str = "all",
    recipe_dir: Path = DEFAULT_RECIPE_DIR,
    recipe_paths: tuple[Path, ...] = (),
    render: bool = False,
    python: str = sys.executable,
) -> dict[str, dict[str, Path]]:
    _require_tools("ffmpeg")
    _require_python_modules("PIL")
    recipes = load_recipes(recipe_dir=recipe_dir, recipe_paths=recipe_paths)
    selected = _select_recipes(recipes, archetype)

    root = workdir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    outputs: dict[str, dict[str, Path]] = {}
    for recipe in selected:
        outputs[recipe.id] = _materialize_recipe(root / recipe.id, recipe, render=render, python=python)
    return outputs


def load_recipes(*, recipe_dir: Path = DEFAULT_RECIPE_DIR, recipe_paths: tuple[Path, ...] = ()) -> dict[str, ArchetypeRecipe]:
    recipes = _builtin_recipes()

    for path in _recipe_paths(recipe_dir, recipe_paths):
        recipe = _recipe_from_json_path(path)
        recipes[recipe.id] = recipe
    return recipes


def _recipe_paths(recipe_dir: Path, recipe_paths: tuple[Path, ...]) -> list[Path]:
    paths: list[Path] = []
    if recipe_dir.exists():
        paths.extend(sorted(path for path in recipe_dir.glob("*.json") if path.is_file()))
        paths.extend(sorted(path for path in recipe_dir.glob("*/recipe.json") if path.is_file()))
    elif recipe_dir == DEFAULT_RECIPE_DIR:
        paths.extend(sorted(path for path in DEFAULT_RECIPE_DIR.parent.glob("*/recipe.json") if path.is_file()))
    paths.extend(recipe_paths)
    return paths


def _materialize_recipe(directory: Path, recipe: ArchetypeRecipe, *, render: bool, python: str) -> dict[str, Path]:
    assets_dir = directory / "assets"
    directory.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    base = directory / "base.mp4"
    transcript_path = directory / "transcript.json"
    edit_path = directory / "KINO-EDIT.json"
    manifest_path = directory / "KINO-MANIFEST.json"
    summary_path = directory / SUMMARY_FILENAME
    rendered = directory / "rendered.mp4"

    _generate_base_video(base, recipe)
    visual_paths = _generate_visuals(assets_dir, recipe)

    transcript = Transcript(
        id=f"{recipe.id}.transcript",
        language="en",
        source="base.mp4",
        words=recipe.words,
    )
    transcript_path.write_text(json.dumps(transcript.to_dict(), indent=2, sort_keys=True) + "\n")

    edit = _build_edit(recipe, transcript, visual_paths)
    write_edit_json(edit, edit_path)

    manifest = compile_edit_to_manifest(
        edit,
        base="base.mp4",
        output="rendered.mp4",
        size=recipe.size,
        fps=recipe.fps,
    )
    write_manifest_json(manifest, manifest_path)

    if render:
        _run_cli_render(python, directory)

    _write_summary(
        summary_path,
        recipe=recipe,
        paths={
            "base": base,
            "transcript": transcript_path,
            "edit": edit_path,
            "manifest": manifest_path,
            "render": rendered,
            "assets": assets_dir,
        },
        rendered=render,
    )

    paths = {
        "directory": directory,
        "base": base,
        "transcript": transcript_path,
        "edit": edit_path,
        "manifest": manifest_path,
        "summary": summary_path,
        "assets": assets_dir,
    }
    if render:
        paths["render"] = rendered
    return paths


def _build_edit(recipe: ArchetypeRecipe, transcript: Transcript, visual_paths: dict[str, Path]) -> KinoEdit:
    source = SourceReceipt(
        id="src.synthetic",
        kind="generated",
        locator=f"fixture-recipe:{recipe.id}",
        title=recipe.title,
        publisher="examples/archetypes/run.py",
        license="synthetic local test asset",
        notes=f"Recipe origin: {recipe.origin}",
    )
    assets = tuple(
        AssetCandidate(
            id=f"asset.{visual.id}",
            source_id=source.id,
            kind="still",
            uri=visual_paths[visual.id].relative_to(visual_paths[visual.id].parents[1]).as_posix(),
            width=recipe.size[0],
            height=recipe.size[1],
            credit="Generated synthetic archetype fixture",
            notes=visual.label,
        )
        for visual in recipe.visuals
    )
    beats = tuple(
        BeatCandidate(
            id=beat.id,
            token_start=beat.token_start,
            token_end=beat.token_end,
            route=beat.route,
            interpretation=beat.interpretation,
            source_plan=beat.source_plan,
            fallback=beat.fallback,
            source_ids=(source.id,),
            asset_ids=(f"asset.{beat.asset_id}",),
            selected_asset_id=f"asset.{beat.asset_id}",
            status="approved",
        )
        for beat in recipe.beats
    )
    return KinoEdit(
        id=f"{recipe.id}.replica",
        transcript=transcript,
        sources=(source,),
        assets=assets,
        beats=beats,
    )


def _generate_base_video(path: Path, recipe: ArchetypeRecipe) -> None:
    width, height = recipe.size
    _run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size={width}x{height}:rate={recipe.fps}:duration={recipe.duration}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={recipe.tone_hz}:sample_rate=48000:duration={recipe.duration}",
            "-shortest",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(path),
        ],
        cwd=path.parent,
    )


def _generate_visuals(directory: Path, recipe: ArchetypeRecipe) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for visual in recipe.visuals:
        path = directory / visual.filename
        _write_still(path, recipe.size, visual)
        paths[visual.id] = path
    return paths


def _write_still(path: Path, size: tuple[int, int], visual: VisualRecipe) -> None:
    from PIL import Image, ImageDraw, ImageFont

    width, height = size
    image = Image.new("RGB", size, visual.background)
    draw = ImageDraw.Draw(image)

    margin = max(10, min(width, height) // 14)
    draw.rectangle((margin, margin, width - margin, height - margin), outline=visual.accent, width=max(3, margin // 3))
    draw.rectangle((margin * 2, margin * 2, width - margin * 2, margin * 3), fill=visual.accent)

    font = ImageFont.load_default()
    lines = _wrap_label(visual.label, max_chars=max(8, width // 18))
    line_height = _text_size(draw, "Ag", font)[1] + 6
    total_height = len(lines) * line_height
    y = max(margin * 4, (height - total_height) // 2)
    for line in lines:
        text_width, text_height = _text_size(draw, line, font)
        x = max(margin, (width - text_width) // 2)
        draw.text((x, y), line, fill=(255, 255, 255), font=font)
        y += line_height

    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _wrap_label(label: str, *, max_chars: int) -> list[str]:
    words = label.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join([*current, word])
        if current and len(candidate) > max_chars:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines or [label]


def _text_size(draw: Any, text: str, font: Any) -> tuple[int, int]:
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    return right - left, bottom - top


def _write_summary(summary_path: Path, *, recipe: ArchetypeRecipe, paths: dict[str, Path], rendered: bool) -> None:
    data = {
        "schema": "kino.archetype.replica.v1",
        "recipe": {
            "id": recipe.id,
            "title": recipe.title,
            "archetype": recipe.archetype,
            "origin": recipe.origin,
            "preset": recipe.preset,
            "size": list(recipe.size),
            "fps": recipe.fps,
            "duration": recipe.duration,
        },
        "contract": {
            "media_policy": "All binary media is generated at runtime under the workdir.",
            "rendered": rendered,
        },
        "outputs": {key: str(path) for key, path in paths.items() if rendered or key != "render"},
    }
    summary_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def _run_cli_render(python: str, directory: Path) -> None:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(SRC_ROOT) if not existing else os.pathsep.join([str(SRC_ROOT), existing])
    _run([python, "-m", "kino.cli", "render-cutaways", "KINO-MANIFEST.json"], cwd=directory, env=env)


def _run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True)
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ArchetypeRunnerError(f"{' '.join(command)} failed: {detail}")


def _require_tools(*tools: str) -> None:
    missing = [tool for tool in tools if shutil.which(tool) is None]
    if missing:
        raise ArchetypeRunnerError(f"missing required tool(s): {', '.join(missing)}")


def _require_python_modules(*modules: str) -> None:
    missing = [module for module in modules if importlib.util.find_spec(module) is None]
    if missing:
        raise ArchetypeRunnerError(
            f"missing required Python module(s): {', '.join(missing)}. "
            'Install project dependencies with pip install -e ".[dev]" or run from an environment with Pillow.'
        )


def _select_recipes(recipes: dict[str, ArchetypeRecipe], archetype: str) -> tuple[ArchetypeRecipe, ...]:
    if archetype == "all":
        return tuple(recipes[key] for key in sorted(recipes))
    try:
        return (recipes[archetype],)
    except KeyError as exc:
        available = ", ".join(["all", *sorted(recipes)])
        raise ArchetypeRunnerError(f"unknown archetype {archetype!r}; available: {available}") from exc


def _recipe_from_json_path(path: Path) -> ArchetypeRecipe:
    try:
        data = json.loads(path.read_text())
    except OSError as exc:
        raise ArchetypeRunnerError(f"could not read recipe {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ArchetypeRunnerError(f"could not parse recipe {path}: {exc}") from exc
    return _recipe_from_mapping(data, origin=str(path))


def _recipe_from_mapping(data: dict[str, Any], *, origin: str) -> ArchetypeRecipe:
    if data.get("recipe_schema_version") == 1 and "transcript_cue_snippets" in data:
        return _recipe_from_reference_fixture(data, origin=origin)

    size = data.get("size", [180, 320])
    words = tuple(_word_from_mapping(index, item) for index, item in enumerate(_required_list(data, "words")))
    visuals = tuple(_visual_from_mapping(item) for item in _required_list(data, "visuals"))
    beats = tuple(_beat_from_mapping(item) for item in _required_list(data, "beats"))
    duration = float(data.get("duration", max(word.end for word in words)))
    return ArchetypeRecipe(
        id=_required_str(data, "id"),
        title=_required_str(data, "title"),
        archetype=str(data.get("archetype", data["id"])),
        size=(int(size[0]), int(size[1])),
        fps=int(data.get("fps", 30)),
        duration=duration,
        tone_hz=int(data.get("tone_hz", 660)),
        preset=str(data.get("preset", "vertical-social")),
        words=words,
        visuals=visuals,
        beats=beats,
        origin=origin,
    )


def _recipe_from_reference_fixture(data: dict[str, Any], *, origin: str) -> ArchetypeRecipe:
    archetype = _required_dict(data, "archetype")
    target = _required_dict(data, "target")
    cues = _required_list(data, "transcript_cue_snippets")

    archetype_id = _required_str(archetype, "id")
    duration, size, preset = _tiny_target(target)
    segment = duration / len(cues)
    palette = (
        ((19, 32, 40), (236, 95, 87)),
        ((24, 42, 54), (55, 171, 142)),
        ((38, 39, 58), (245, 190, 88)),
        ((31, 41, 55), (96, 165, 250)),
        ((42, 36, 47), (251, 146, 60)),
        ((20, 34, 38), (45, 212, 191)),
    )

    words: list[WordToken] = []
    visuals: list[VisualRecipe] = []
    beats: list[BeatRecipe] = []
    token_index = 0
    seen_visual_ids: set[str] = set()

    for cue_index, cue in enumerate(cues):
        section = str(cue.get("section", f"section-{cue_index + 1}"))
        visual_id = _unique_id(_slug(section), seen_visual_ids)
        seen_visual_ids.add(visual_id)

        start = round(cue_index * segment, 3)
        end = round(duration if cue_index == len(cues) - 1 else (cue_index + 1) * segment, 3)
        snippet_words = _snippet_words(_required_str(cue, "snippet"))
        word_duration = (end - start) / len(snippet_words)
        token_start = token_index

        for word_index, text in enumerate(snippet_words):
            word_start = round(start + word_index * word_duration, 3)
            word_end = round(end if word_index == len(snippet_words) - 1 else start + (word_index + 1) * word_duration, 3)
            words.append(WordToken(id=f"w{token_index + 1:03d}", text=text, start=word_start, end=word_end))
            token_index += 1

        background, accent = palette[cue_index % len(palette)]
        visuals.append(
            VisualRecipe(
                id=visual_id,
                filename=f"{visual_id}.png",
                label=str(cue.get("section", cue.get("id", visual_id))).replace("_", " ").title(),
                background=background,
                accent=accent,
            )
        )
        beats.append(
            BeatRecipe(
                id=f"beat.{visual_id}",
                token_start=token_start,
                token_end=token_index,
                route=_route_for_reference_cue(cue),
                interpretation=str(cue.get("proof_requirement", f"Fixture cue for {section}.")),
                source_plan=f"Generate synthetic placeholder for {section}.",
                asset_id=visual_id,
                fallback="Keep the synthetic placeholder and flag for replacement with user-owned footage.",
            )
        )

    return ArchetypeRecipe(
        id=archetype_id,
        title=str(archetype.get("name", archetype_id)),
        archetype=archetype_id,
        size=size,
        fps=int(target.get("fps", 30)),
        duration=duration,
        tone_hz=740 if size[1] > size[0] else 520,
        preset=preset,
        words=tuple(words),
        visuals=tuple(visuals),
        beats=tuple(beats),
        origin=origin,
    )


def _tiny_target(target: dict[str, Any]) -> tuple[float, tuple[int, int], str]:
    aspect = str(target.get("aspect_ratio", "9:16"))
    if aspect == "16:9":
        return 3.6, (320, 180), "landscape-web"
    if aspect == "9:16":
        return 2.8, (180, 320), "vertical-social"
    if aspect == "1:1":
        return 2.8, (240, 240), "square-social"
    return 2.8, (180, 320), "vertical-social"


def _snippet_words(snippet: str) -> list[str]:
    words = [word for word in re.sub(r"[^A-Za-z0-9']+", " ", snippet).split() if word]
    if not words:
        raise ArchetypeRunnerError("reference fixture cue snippets must contain at least one word")
    return words


def _route_for_reference_cue(cue: dict[str, Any]) -> str:
    haystack = " ".join(str(cue.get(key, "")) for key in ("section", "proof_requirement", "snippet")).lower()
    if any(term in haystack for term in ("screen", "website", "ui", "product", "workflow", "walkthrough", "render plan")):
        return "product-ui"
    if any(term in haystack for term in ("proof", "result", "physical", "customer", "receipt")):
        return "receipt"
    return "concept"


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "section"


def _unique_id(value: str, existing: set[str]) -> str:
    if value not in existing:
        return value
    index = 2
    while f"{value}-{index}" in existing:
        index += 1
    return f"{value}-{index}"


def _word_from_mapping(index: int, data: dict[str, Any]) -> WordToken:
    return WordToken(
        id=str(data.get("id", f"w{index + 1:03d}")),
        text=_required_str(data, "text"),
        start=float(data["start"]),
        end=float(data["end"]),
        speaker=data.get("speaker"),
        confidence=float(data["confidence"]) if data.get("confidence") is not None else None,
    )


def _visual_from_mapping(data: dict[str, Any]) -> VisualRecipe:
    return VisualRecipe(
        id=_required_str(data, "id"),
        filename=str(data.get("filename", f"{data['id']}.png")),
        label=_required_str(data, "label"),
        background=_rgb(data.get("background", [28, 45, 59])),
        accent=_rgb(data.get("accent", [38, 166, 154])),
    )


def _beat_from_mapping(data: dict[str, Any]) -> BeatRecipe:
    return BeatRecipe(
        id=_required_str(data, "id"),
        token_start=int(data["token_start"]),
        token_end=int(data["token_end"]),
        route=_required_str(data, "route"),
        interpretation=_required_str(data, "interpretation"),
        source_plan=_required_str(data, "source_plan"),
        asset_id=_required_str(data, "asset_id"),
        fallback=str(data.get("fallback", "Keep generated placeholder and flag for human replacement.")),
    )


def _required_list(data: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = data.get(key)
    if not isinstance(value, list):
        raise ArchetypeRunnerError(f"recipe field {key!r} must be a list")
    return value


def _required_dict(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ArchetypeRunnerError(f"recipe field {key!r} must be an object")
    return value


def _required_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or value == "":
        raise ArchetypeRunnerError(f"recipe field {key!r} must be a non-empty string")
    return value


def _rgb(value: Any) -> tuple[int, int, int]:
    if not isinstance(value, list | tuple) or len(value) != 3:
        raise ArchetypeRunnerError("recipe colors must be three-item RGB lists")
    return int(value[0]), int(value[1]), int(value[2])


def _builtin_recipes() -> dict[str, ArchetypeRecipe]:
    recipes = (
        _recipe_from_mapping(
            {
                "id": "social-short",
                "title": "Social short synthetic skeleton",
                "archetype": "social-short",
                "size": [180, 320],
                "fps": 30,
                "duration": 2.8,
                "tone_hz": 740,
                "preset": "vertical-social",
                "words": [
                    {"text": "Stop", "start": 0.0, "end": 0.35},
                    {"text": "hiding", "start": 0.35, "end": 0.7},
                    {"text": "demos", "start": 0.7, "end": 1.05},
                    {"text": "show", "start": 1.05, "end": 1.4},
                    {"text": "proof", "start": 1.4, "end": 1.75},
                    {"text": "then", "start": 1.75, "end": 2.1},
                    {"text": "ask", "start": 2.1, "end": 2.45},
                    {"text": "cleanly", "start": 2.45, "end": 2.8},
                ],
                "visuals": [
                    {
                        "id": "hook",
                        "filename": "hook.png",
                        "label": "Hook caption",
                        "background": [19, 32, 40],
                        "accent": [236, 95, 87],
                    },
                    {
                        "id": "proof",
                        "filename": "proof.png",
                        "label": "Product proof",
                        "background": [24, 42, 54],
                        "accent": [55, 171, 142],
                    },
                    {
                        "id": "cta",
                        "filename": "cta.png",
                        "label": "CTA montage",
                        "background": [38, 39, 58],
                        "accent": [245, 190, 88],
                    },
                ],
                "beats": [
                    {
                        "id": "beat.hook",
                        "token_start": 0,
                        "token_end": 2,
                        "route": "concept",
                        "interpretation": "Fast opening hook with a bold retention caption.",
                        "source_plan": "Use generated vertical caption card.",
                        "asset_id": "hook",
                    },
                    {
                        "id": "beat.proof",
                        "token_start": 4,
                        "token_end": 6,
                        "route": "product-ui",
                        "interpretation": "Show visible proof at the concrete claim.",
                        "source_plan": "Use generated product proof insert.",
                        "asset_id": "proof",
                    },
                    {
                        "id": "beat.cta",
                        "token_start": 6,
                        "token_end": 8,
                        "route": "concept",
                        "interpretation": "End with a clean call-to-action visual.",
                        "source_plan": "Use generated CTA card.",
                        "asset_id": "cta",
                    },
                ],
            },
            origin="builtin",
        ),
        _recipe_from_mapping(
            {
                "id": "founder-product-explainer",
                "title": "Founder product explainer synthetic skeleton",
                "archetype": "founder-product-explainer",
                "size": [320, 180],
                "fps": 30,
                "duration": 3.6,
                "tone_hz": 520,
                "preset": "landscape-web",
                "words": [
                    {"text": "Here", "start": 0.0, "end": 0.36},
                    {"text": "is", "start": 0.36, "end": 0.72},
                    {"text": "the", "start": 0.72, "end": 1.08},
                    {"text": "painful", "start": 1.08, "end": 1.44},
                    {"text": "workflow", "start": 1.44, "end": 1.8},
                    {"text": "now", "start": 1.8, "end": 2.16},
                    {"text": "Kino", "start": 2.16, "end": 2.52},
                    {"text": "turns", "start": 2.52, "end": 2.88},
                    {"text": "clips", "start": 2.88, "end": 3.24},
                    {"text": "into", "start": 3.24, "end": 3.42},
                    {"text": "proof", "start": 3.42, "end": 3.6},
                ],
                "visuals": [
                    {
                        "id": "cold-open",
                        "filename": "cold-open.png",
                        "label": "Cold open result",
                        "background": [20, 34, 38],
                        "accent": [96, 165, 250],
                    },
                    {
                        "id": "walkthrough",
                        "filename": "walkthrough.png",
                        "label": "Product walkthrough",
                        "background": [31, 41, 55],
                        "accent": [45, 212, 191],
                    },
                    {
                        "id": "proof-shot",
                        "filename": "proof-shot.png",
                        "label": "Physical proof",
                        "background": [42, 36, 47],
                        "accent": [251, 146, 60],
                    },
                ],
                "beats": [
                    {
                        "id": "beat.cold-open",
                        "token_start": 0,
                        "token_end": 3,
                        "route": "concept",
                        "interpretation": "Open on the result before the origin story.",
                        "source_plan": "Use generated wide result card.",
                        "asset_id": "cold-open",
                    },
                    {
                        "id": "beat.walkthrough",
                        "token_start": 4,
                        "token_end": 8,
                        "route": "product-ui",
                        "interpretation": "Hold a readable product walkthrough long enough to understand.",
                        "source_plan": "Use generated product UI card.",
                        "asset_id": "walkthrough",
                    },
                    {
                        "id": "beat.proof-shot",
                        "token_start": 8,
                        "token_end": 11,
                        "route": "receipt",
                        "interpretation": "Close with proof that validates the product claim.",
                        "source_plan": "Use generated physical proof card.",
                        "asset_id": "proof-shot",
                    },
                ],
            },
            origin="builtin",
        ),
    )
    return {recipe.id: recipe for recipe in recipes}


if __name__ == "__main__":
    raise SystemExit(main())

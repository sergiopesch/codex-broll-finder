from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_plugin_mirrors_kino_planner_runtime_files():
    for relative in (
        "src/kino/captions.py",
        "src/kino/eval.py",
        "src/kino/review.py",
        "src/kino/plan.py",
        "src/kino/edit.py",
        "src/kino/cli.py",
        "kino/SKILL.md",
        "kino/references/manifest.md",
    ):
        plugin_relative = relative
        if relative.startswith("src/kino/"):
            plugin_relative = f"plugins/kino/{relative}"
        elif relative.startswith("kino/"):
            plugin_relative = f"plugins/kino/skills/{relative}"

        assert (ROOT / plugin_relative).read_text() == (ROOT / relative).read_text()

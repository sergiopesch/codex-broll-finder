from __future__ import annotations

import re
from pathlib import Path

import pytest

from kino import cli


ROOT = Path(__file__).resolve().parents[1]


def _cli_help_commands(capsys) -> set[str]:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])

    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    usage_match = re.search(r"\{([^}]+)\}", help_text)
    assert usage_match is not None
    return set(usage_match.group(1).split(","))


def test_documented_kino_example_commands_exist_in_cli_help(capsys):
    docs = (
        ROOT / "README.md",
        ROOT / "examples" / "archetypes" / "README.md",
        ROOT / "examples" / "quickstart" / "README.md",
        ROOT / "docs" / "video-archetypes.md",
    )
    documented_commands: set[str] = set()
    for path in docs:
        text = path.read_text()
        documented_commands.update(re.findall(r"\bkino\s+([a-z][a-z0-9-]+)\b", text))

    assert documented_commands
    assert documented_commands <= _cli_help_commands(capsys)


def test_example_docs_mark_current_runtime_boundaries():
    quickstart = (ROOT / "examples" / "quickstart" / "README.md").read_text()
    archetypes = (ROOT / "examples" / "archetypes" / "README.md").read_text()

    assert "rendering still starts from `KINO-MANIFEST.json`" in quickstart
    assert "does not download reference videos" in archetypes
    assert "does not promise full-fidelity replication" in archetypes

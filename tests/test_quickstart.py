from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
QUICKSTART = ROOT / "examples" / "quickstart" / "run.py"


def _load_quickstart():
    spec = importlib.util.spec_from_file_location("kino_quickstart", QUICKSTART)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_quickstart_runner_invokes_cli_loop_after_generating_media(tmp_path, monkeypatch):
    module = _load_quickstart()
    calls: list[tuple[list[str], Path]] = []

    monkeypatch.setattr(module.shutil, "which", lambda tool: f"/usr/bin/{tool}")

    def fake_run(command, *, cwd, env=None, capture_output=False, text=False):
        calls.append((list(command), Path(cwd)))
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    outputs = module.run_quickstart(tmp_path, python="/python", repo_root=ROOT)

    assert outputs["manifest"] == tmp_path.resolve() / "KINO-MANIFEST.json"
    assert (tmp_path / "transcript.json").exists()

    ffmpeg_calls = [command for command, _ in calls if command[0] == "ffmpeg"]
    cli_calls = [command for command, _ in calls if command[:3] == ["/python", "-m", "kino.cli"]]

    assert len(ffmpeg_calls) == 2
    assert [command[3] for command in cli_calls] == [
        "init-edit",
        "add-source",
        "add-asset",
        "propose-beat",
        "approve-beat",
        "propose-beat",
        "reject-beat",
        "compile-manifest",
        "render-cutaways",
        "verify-frames",
        "export-variant",
        "validate-export",
    ]
    assert cli_calls[-2][-4:] == ["--preset", "landscape-web", "--crf", "28"]
    assert cli_calls[-1][-5:] == [
        "--json-out",
        "KINO-VALIDATION.json",
        "--md-out",
        "KINO-VALIDATION.md",
        "--strict",
    ]


def test_quickstart_runner_reports_missing_ffmpeg(tmp_path, monkeypatch):
    module = _load_quickstart()

    monkeypatch.setattr(module.shutil, "which", lambda tool: None)

    with pytest.raises(module.QuickstartError, match="missing required tool"):
        module.run_quickstart(tmp_path)


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="ffmpeg and ffprobe are required for the quickstart smoke test",
)
def test_quickstart_runner_real_tiny_media_smoke(tmp_path):
    module = _load_quickstart()

    outputs = module.run_quickstart(tmp_path, python=sys.executable, repo_root=ROOT)

    assert outputs["edit"].exists()
    assert outputs["manifest"].exists()
    assert outputs["render"].exists()
    assert outputs["render_receipt"].exists()
    assert outputs["export"].exists()
    assert outputs["validation_json"].exists()
    assert any(outputs["verify_frames"].glob("*.jpg"))

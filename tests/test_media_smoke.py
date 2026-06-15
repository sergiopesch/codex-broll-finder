from __future__ import annotations

import shutil
import subprocess

import pytest

from codex_broll_finder.export import build_export_command
from codex_broll_finder.presets import get_preset
from codex_broll_finder.probe import probe_media
from codex_broll_finder.validation import validate_export, write_json_report, write_markdown_report


pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="ffmpeg and ffprobe are required for media smoke tests",
)


def test_export_probe_validate_real_tiny_video(tmp_path):
    source = tmp_path / "source.mp4"
    exported = tmp_path / "vertical.mp4"
    json_report = tmp_path / "BROLL-VALIDATION.json"
    md_report = tmp_path / "BROLL-VALIDATION.md"

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x180:rate=30:duration=0.25",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:sample_rate=48000:duration=0.25",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(source),
        ],
        check=True,
    )
    subprocess.run(build_export_command(source, exported, get_preset("vertical-social"), crf=28), check=True)

    report = validate_export(probe_media(exported), get_preset("vertical-social"))
    write_json_report(report, json_report)
    write_markdown_report(report, md_report)

    assert exported.exists()
    assert json_report.exists()
    assert md_report.read_text().startswith("# B-Roll Validation Report")
    assert report.overall in {"pass", "manual-review-required"}

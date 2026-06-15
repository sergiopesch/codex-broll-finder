from pathlib import Path

import pytest

from codex_broll_finder.export import build_export_command
from codex_broll_finder.presets import get_preset


def test_build_export_command_uses_preset_dimensions_and_faststart():
    cmd = build_export_command(Path("in.mp4"), Path("out.mp4"), get_preset("vertical-social"))
    joined = " ".join(cmd)

    assert "fps=30" in joined
    assert "scale=1080:1920" in joined
    assert "crop=1080:1920" in joined
    assert "+faststart" in cmd
    assert cmd[-1] == "out.mp4"


def test_landscape_web_preserves_source_frame_rate():
    cmd = build_export_command(Path("in.mp4"), Path("out.mp4"), get_preset("landscape-web"))

    assert "fps=" not in " ".join(cmd)


def test_mp4_preset_rejects_non_mp4_output_path():
    with pytest.raises(ValueError, match="must use an .mp4 output path"):
        build_export_command(Path("in.mp4"), Path("out.mov"), get_preset("vertical-social"))

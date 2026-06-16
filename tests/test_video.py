from pathlib import Path

from kino.manifest import Beat, Manifest
from kino.video import build_render_command, verification_times, video_filter


def test_video_filter_is_full_bleed():
    assert video_filter(1920, 1080, 30) == (
        "scale=1920:1080:force_original_aspect_ratio=increase,"
        "crop=1920:1080,setsar=1,fps=30,format=yuv420p"
    )


def test_render_command_preserves_audio():
    beat = Beat(
        id="b001",
        start=1.0,
        end=2.0,
        line="line",
        interpretation="meaning",
        route="entity",
        asset=Path("asset.mp4"),
        kind="video",
    )
    manifest = Manifest(path=Path("m.json"), base=Path("base.mp4"), output=Path("out.mp4"), beats=(beat,))

    cmd = build_render_command(manifest, [Path("fmt/b001.mp4")], end=5.0)

    assert any("[0:a]atrim=start=0:end=5.0" in part for part in cmd)
    assert "-map" in cmd
    assert "out.mp4" == cmd[-1]


def test_verification_times_include_midpoints():
    beat = Beat(
        id="b001",
        start=2.0,
        end=6.0,
        line="line",
        interpretation="meaning",
        route="entity",
        asset=Path("asset.mp4"),
        kind="video",
    )
    manifest = Manifest(path=Path("m.json"), base=Path("base.mp4"), output=Path("out.mp4"), beats=(beat,))

    assert ("b001-mid", 4.0) in verification_times(manifest)

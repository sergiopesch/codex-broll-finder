import json
from pathlib import Path

import kino.receipt as receipt
from kino.manifest import Beat, Manifest
from kino.video import build_render_command, formatted_clip_path, render_cutaways, verification_times, video_filter


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


def test_formatted_clip_path_changes_with_asset_and_timing(tmp_path):
    asset = tmp_path / "asset.mp4"
    asset.write_bytes(b"first")
    vf = video_filter(1920, 1080, 30)
    beat = Beat(
        id="b001",
        start=1.0,
        end=2.0,
        line="line",
        interpretation="meaning",
        route="entity",
        asset=asset,
        kind="video",
        source_in=3.0,
    )

    first = formatted_clip_path(beat, tmp_path / "fmt", vf)
    asset.write_bytes(b"second")
    changed_asset = formatted_clip_path(beat, tmp_path / "fmt", vf)
    changed_timing = formatted_clip_path(
        Beat(
            id="b001",
            start=1.0,
            end=2.5,
            line="line",
            interpretation="meaning",
            route="entity",
            asset=asset,
            kind="video",
            source_in=3.0,
        ),
        tmp_path / "fmt",
        vf,
    )

    assert first.name.startswith("b001-")
    assert first != changed_asset
    assert changed_asset != changed_timing


def test_render_cutaways_writes_render_receipt(tmp_path, monkeypatch):
    asset = tmp_path / "asset.mp4"
    asset.write_bytes(b"asset")
    manifest_path = tmp_path / "KINO-MANIFEST.json"
    manifest_path.write_text('{"version":1,"base":"base.mp4","beats":[]}\n')
    beat = Beat(
        id="b001",
        start=1.0,
        end=2.0,
        line="line",
        interpretation="meaning",
        route="entity",
        asset=asset,
        kind="video",
    )
    manifest = Manifest(
        path=manifest_path,
        base=tmp_path / "base.mp4",
        output=tmp_path / "out.mp4",
        beats=(beat,),
    )
    commands: list[list[str]] = []

    def fake_run(command: list[str]) -> None:
        commands.append(command)
        Path(command[-1]).parent.mkdir(parents=True, exist_ok=True)
        Path(command[-1]).write_bytes(b"video")

    monkeypatch.setattr("kino.video.run", fake_run)
    monkeypatch.setattr("kino.video.ffprobe_duration", lambda path: 5.0)
    monkeypatch.setattr(receipt, "collect_tool_versions", lambda: {"ffmpeg": "ffmpeg test", "ffprobe": "ffprobe test"})

    output = render_cutaways(manifest)

    assert output == tmp_path / "out.mp4"
    assert len(commands) == 2
    data = json.loads((tmp_path / "KINO-RENDER.json").read_text())
    assert data["paths"]["output"] == str(tmp_path / "out.mp4")
    assert data["paths"]["formatted"][0].startswith(str(tmp_path / "assets" / "fmt" / "b001-"))
    assert data["formatted_commands"] == [commands[0]]
    assert data["command"] == commands[1]
    assert data["tool_versions"] == {"ffmpeg": "ffmpeg test", "ffprobe": "ffprobe test"}

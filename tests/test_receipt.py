import json

from kino.manifest import Beat, Manifest
from kino.graph import manifest_to_graph
from kino.receipt import build_render_receipt, command_graph_hash, write_render_receipt


def test_render_receipt_records_command_hashes_paths_and_versions(tmp_path):
    manifest_path = tmp_path / "KINO-MANIFEST.json"
    manifest_path.write_text('{"version":1,"base":"base.mp4","beats":[]}\n')
    command = [
        "ffmpeg",
        "-filter_complex",
        "[0:v]trim=start=0:end=1,setpts=PTS-STARTPTS[v]",
        str(tmp_path / "out.mp4"),
    ]
    manifest = Manifest(
        path=manifest_path,
        base=tmp_path / "base.mp4",
        output=tmp_path / "out.mp4",
        beats=(
            Beat(
                id="b001",
                start=0.0,
                end=1.0,
                line="line",
                interpretation="meaning",
                route="entity",
                asset=tmp_path / "asset.mp4",
                kind="video",
            ),
        ),
    )

    receipt = build_render_receipt(
        manifest,
        command,
        [tmp_path / "assets" / "fmt" / "b001-deadbeef.mp4"],
        base_duration=3.0,
        timestamp="2026-06-16T12:00:00Z",
        tool_versions={"ffmpeg": "ffmpeg version test", "ffprobe": "ffprobe version test"},
    )
    path = write_render_receipt(receipt, tmp_path)

    data = json.loads(path.read_text())
    assert path.name == "KINO-RENDER.json"
    assert data["schema"] == "kino.render.receipt.v1"
    assert data["timestamp"] == "2026-06-16T12:00:00Z"
    assert data["input"]["type"] == "manifest"
    assert data["input"]["hash"]
    assert data["graph_hash"] == manifest_to_graph(manifest, base_duration=3.0).stable_hash()
    assert data["command_hash"] == command_graph_hash(command)
    assert data["command"] == command
    assert data["tool_versions"] == {"ffmpeg": "ffmpeg version test", "ffprobe": "ffprobe version test"}
    assert data["paths"]["manifest"] == str(manifest_path)
    assert data["paths"]["source"] == str(tmp_path / "base.mp4")
    assert data["paths"]["output"] == str(tmp_path / "out.mp4")
    assert data["paths"]["assets"] == [str(tmp_path / "asset.mp4")]

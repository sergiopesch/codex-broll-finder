from pathlib import Path

import pytest

from kino.graph import (
    GraphError,
    RenderClip,
    RenderGraph,
    RenderOutput,
    RenderSource,
    RenderTrack,
    ValidationExpectations,
    manifest_to_graph,
)
from kino.manifest import Beat, Manifest


def make_beat(
    id_: str,
    start: float,
    end: float,
    *,
    asset: str | None = None,
    kind: str = "video",
    source_in: float = 0.0,
) -> Beat:
    return Beat(
        id=id_,
        start=start,
        end=end,
        line=f"line {id_}",
        interpretation=f"meaning {id_}",
        route="product-ui",
        asset=Path(asset or f"assets/{id_}.mp4"),
        kind=kind,  # type: ignore[arg-type]
        source_in=source_in,
        status="approved",
        credit="Example",
    )


def make_manifest(*beats: Beat) -> Manifest:
    return Manifest(
        path=Path("KINO-MANIFEST.json"),
        base=Path("base.mp4"),
        output=Path("out.mp4"),
        beats=beats,
        size=(1280, 720),
        fps=24,
    )


def test_manifest_to_graph_preserves_cutaway_timeline_with_known_base_duration():
    manifest = make_manifest(
        make_beat("b001", 1.0, 2.0, source_in=0.25),
        make_beat("b002", 4.0, 5.5, asset="assets/b002.jpg", kind="still", source_in=12.0),
    )

    graph = manifest_to_graph(manifest, base_duration=8.0)

    assert [source.to_dict() for source in graph.sources] == [
        {"id": "base", "path": "base.mp4", "media_type": "video", "role": "base"},
        {"id": "cutaway:b001", "path": "assets/b001.mp4", "media_type": "video", "role": "cutaway"},
        {"id": "cutaway:b002", "path": "assets/b002.jpg", "media_type": "image", "role": "cutaway"},
    ]

    picture = graph.tracks[0]
    assert picture.id == "picture"
    assert [(clip.id, clip.source_id, clip.timeline_start, clip.source_start, clip.duration) for clip in picture.clips] == [
        ("base:0", "base", 0.0, 0.0, 1.0),
        ("cutaway:b001", "cutaway:b001", 1.0, 0.25, 1.0),
        ("base:1", "base", 2.0, 2.0, 2.0),
        ("cutaway:b002", "cutaway:b002", 4.0, 0.0, 1.5),
        ("base:2", "base", 5.5, 5.5, 2.5),
    ]
    assert [clip.operation for clip in picture.clips] == ["base", "replace", "base", "replace", "base"]
    assert [clip.audio_policy for clip in picture.clips] == ["none", "muted", "none", "muted", "none"]

    base_audio = graph.tracks[1]
    assert base_audio.clips == (
        RenderClip(
            id="audio:base",
            source_id="base",
            timeline_start=0.0,
            source_start=0.0,
            duration=8.0,
            operation="base",
            fit="none",
            audio_policy="preserve",
        ),
    )
    assert graph.outputs == (
        RenderOutput(id="main", path=Path("out.mp4"), width=1280, height=720, fps=24),
    )
    assert graph.validation.output_duration == 8.0
    assert graph.validation.output_duration_source_id == "base"


def test_manifest_to_graph_uses_open_ended_base_tail_when_duration_is_unknown():
    manifest = make_manifest(make_beat("b001", 1.0, 2.0))

    graph = manifest_to_graph(manifest)

    assert graph.tracks[0].clips[-1] == RenderClip(
        id="base:1",
        source_id="base",
        timeline_start=2.0,
        source_start=2.0,
        duration=None,
        duration_mode="to_source_end",
        operation="base",
        fit="cover",
        audio_policy="none",
    )
    assert graph.tracks[1].clips[0].duration is None
    assert graph.tracks[1].clips[0].duration_mode == "to_source_end"
    assert graph.validation.output_duration is None


def test_graph_serialization_and_hash_are_canonical():
    manifest = make_manifest(make_beat("b001", 1.0, 2.0))
    graph = manifest_to_graph(manifest, base_duration=4.0)

    assert graph.to_json() == manifest_to_graph(manifest, base_duration=4.0).to_json()
    assert graph.stable_hash() == manifest_to_graph(manifest, base_duration=4.0).stable_hash()
    assert graph.to_dict()["outputs"][0]["path"] == "out.mp4"


def test_graph_validation_rejects_unknown_sources():
    with pytest.raises(GraphError, match="unknown source id"):
        RenderGraph(
            sources=(RenderSource(id="base", path=Path("base.mp4"), media_type="video", role="base"),),
            tracks=(
                RenderTrack(
                    id="picture",
                    media_type="video",
                    clips=(
                        RenderClip(id="clip", source_id="missing", timeline_start=0.0, duration=1.0),
                    ),
                ),
            ),
            outputs=(RenderOutput(id="main", path=Path("out.mp4"), width=1280, height=720, fps=24),),
            validation=ValidationExpectations(output_width=1280, output_height=720, output_fps=24),
        )


def test_graph_validation_rejects_overlapping_track_clips():
    with pytest.raises(GraphError, match="sorted and non-overlapping"):
        RenderGraph(
            sources=(RenderSource(id="base", path=Path("base.mp4"), media_type="video", role="base"),),
            tracks=(
                RenderTrack(
                    id="picture",
                    media_type="video",
                    clips=(
                        RenderClip(id="a", source_id="base", timeline_start=0.0, duration=2.0),
                        RenderClip(id="b", source_id="base", timeline_start=1.0, duration=2.0),
                    ),
                ),
            ),
            outputs=(RenderOutput(id="main", path=Path("out.mp4"), width=1280, height=720, fps=24),),
            validation=ValidationExpectations(output_width=1280, output_height=720, output_fps=24),
        )


def test_manifest_to_graph_validation_points_match_current_cutaway_checks():
    manifest = make_manifest(make_beat("b001", 1.0, 2.0), make_beat("b002", 2.02, 3.0))

    graph = manifest_to_graph(manifest, base_duration=4.0)

    assert [(point.id, point.time, point.kind, point.beat_ids) for point in graph.validation.points] == [
        ("b001-start", 1.0, "beat_start", ("b001",)),
        ("b001-mid", 1.5, "beat_mid", ("b001",)),
        ("b001-end", 2.0, "beat_end", ("b001",)),
        ("b002-start", 2.02, "beat_start", ("b002",)),
        ("b002-mid", 2.51, "beat_mid", ("b002",)),
        ("b002-end", 3.0, "beat_end", ("b002",)),
        ("b001-b002-joint", 2.02, "joint", ("b001", "b002")),
    ]


def test_manifest_to_graph_rejects_base_duration_shorter_than_cutaways():
    manifest = make_manifest(make_beat("b001", 1.0, 4.0))

    with pytest.raises(GraphError, match="cover the final cutaway"):
        manifest_to_graph(manifest, base_duration=3.0)

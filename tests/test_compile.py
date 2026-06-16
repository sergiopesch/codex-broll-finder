import json
from pathlib import Path

import pytest

from kino.compile import CompileError, compile_edit_to_manifest, write_manifest_json
from kino.edit import AssetCandidate, BeatCandidate, KinoEdit, SourceReceipt, Transcript, WordToken
from kino.manifest import load_manifest


def token(id_, text, start, end):
    return WordToken(id=id_, text=text, start=start, end=end)


def edit_with_beats(*beats, assets=None):
    return KinoEdit(
        id="edit001",
        transcript=Transcript(
            id="tx001",
            source="source.mp4",
            words=(
                token("w001", "Kino", 0.0, 0.25),
                token("w002", "plans", 0.25, 0.6),
                token("w003", "receipt", 0.6, 1.2),
                token("w004", "cutaways", 1.2, 2.0),
            ),
        ),
        sources=(
            SourceReceipt(
                id="src001",
                kind="url",
                locator="https://example.com/post",
                title="Example post",
                author="Ada",
                publisher="Example",
                license="CC-BY",
            ),
        ),
        assets=tuple(
            assets
            if assets is not None
            else (
                AssetCandidate(
                    id="asset001",
                    source_id="src001",
                    kind="web",
                    uri="captures/post.png",
                    credit="Screenshot by Kino",
                ),
                AssetCandidate(
                    id="asset002",
                    source_id="src001",
                    kind="video",
                    uri="clips/demo.mp4",
                    start=4.5,
                ),
            )
        ),
        beats=tuple(beats),
    )


def beat(id_, token_start, token_end, asset_id, *, status="approved"):
    return BeatCandidate(
        id=id_,
        token_start=token_start,
        token_end=token_end,
        route="receipt",
        interpretation=f"Interpretation for {id_}",
        source_plan="Use selected evidence.",
        source_ids=("src001",),
        asset_ids=(asset_id,),
        selected_asset_id=asset_id,
        status=status,
        rejection_reason="Not a fit." if status == "rejected" else None,
    )


def test_compiles_only_approved_beats_with_selected_assets():
    edit = edit_with_beats(
        beat("beat002", 2, 4, "asset002", status="proposed"),
        beat("beat001", 0, 2, "asset001"),
        beat("beat003", 2, 4, "asset002", status="rejected"),
    )

    manifest = compile_edit_to_manifest(edit, "input.mp4", "out.mp4", (1080, 1920), 24)

    assert manifest.base == Path("input.mp4")
    assert manifest.output == Path("out.mp4")
    assert manifest.size == (1080, 1920)
    assert manifest.fps == 24
    assert [beat.id for beat in manifest.beats] == ["beat001"]


def test_uses_transcript_token_timing_line_asset_path_and_credit():
    edit = edit_with_beats(beat("beat001", 1, 3, "asset001"))

    manifest = compile_edit_to_manifest(edit, "input.mp4", "out.mp4", (1920, 1080), 30)
    compiled = manifest.beats[0]

    assert compiled.start == 0.25
    assert compiled.end == 1.2
    assert compiled.line == "plans receipt"
    assert compiled.asset == Path("captures/post.png")
    assert compiled.kind == "still"
    assert compiled.credit == "Screenshot by Kino; Example post; Ada; Example; CC-BY; https://example.com/post"


def test_maps_video_assets_to_manifest_video_with_source_in():
    edit = edit_with_beats(beat("beat001", 0, 2, "asset002"))

    manifest = compile_edit_to_manifest(edit, "input.mp4", "out.mp4", (1920, 1080), 30)
    compiled = manifest.beats[0]

    assert compiled.asset == Path("clips/demo.mp4")
    assert compiled.kind == "video"
    assert compiled.source_in == 4.5


@pytest.mark.parametrize("asset_kind", ["still", "image", "web", "document"])
def test_maps_static_asset_choices_to_manifest_still(asset_kind):
    asset = AssetCandidate(id="asset001", source_id="src001", kind=asset_kind, uri=f"assets/{asset_kind}.png")
    edit = edit_with_beats(beat("beat001", 0, 1, "asset001"), assets=(asset,))

    manifest = compile_edit_to_manifest(edit, "input.mp4", "out.mp4", (1920, 1080), 30)

    assert manifest.beats[0].kind == "still"


def test_write_manifest_json_round_trips_through_existing_loader(tmp_path):
    edit = edit_with_beats(beat("beat001", 0, 2, "asset001"))
    manifest = compile_edit_to_manifest(edit, "input.mp4", "out.mp4", (1080, 1920), 24)

    path = tmp_path / "KINO-MANIFEST.json"
    assert write_manifest_json(manifest, path) == path

    data = json.loads(path.read_text())
    assert data["beats"][0]["asset"] == "captures/post.png"
    assert data["beats"][0]["kind"] == "still"

    loaded = load_manifest(path)
    assert loaded.base == tmp_path / "input.mp4"
    assert loaded.output == tmp_path / "out.mp4"
    assert loaded.beats[0].asset == tmp_path / "captures/post.png"


def test_rejects_selected_asset_kinds_manifest_cannot_represent():
    asset = AssetCandidate(id="asset001", source_id="src001", kind="audio", uri="audio/source.wav")
    edit = edit_with_beats(beat("beat001", 0, 1, "asset001"), assets=(asset,))

    with pytest.raises(CompileError, match="unsupported selected asset kind"):
        compile_edit_to_manifest(edit, "input.mp4", "out.mp4", (1920, 1080), 30)

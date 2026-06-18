import json

import pytest

from kino.edit import (
    AssetCandidate,
    BeatCandidate,
    EditError,
    KinoEdit,
    SourceReceipt,
    Transcript,
    WordToken,
    load_edit,
    validate_edit,
    write_edit_json,
)


def token(id_, text, start, end):
    return WordToken(id=id_, text=text, start=start, end=end)


def valid_edit(**overrides):
    edit = KinoEdit(
        id="edit001",
        transcript=Transcript(
            id="tx001",
            language="en",
            source="source.mp4",
            words=(
                token("w001", "Kino", 0.0, 0.25),
                token("w002", "plans", 0.25, 0.6),
                token("w003", "cutaways", 0.6, 1.1),
            ),
        ),
        sources=(
            SourceReceipt(
                id="src001",
                kind="url",
                locator="https://example.com/post",
                title="Example receipt",
                publisher="Example",
            ),
        ),
        assets=(
            AssetCandidate(
                id="asset001",
                source_id="src001",
                kind="web",
                uri="captures/example.png",
                width=1080,
                height=1920,
                score=0.92,
            ),
        ),
        beats=(
            BeatCandidate(
                id="beat001",
                token_start=0,
                token_end=2,
                route="receipt",
                interpretation="Show the original source while the claim is spoken.",
                source_plan="Capture the canonical source page.",
                source_ids=("src001",),
                asset_ids=("asset001",),
                selected_asset_id="asset001",
                status="approved",
            ),
        ),
    )
    data = edit.to_dict()
    data.update(overrides)
    return KinoEdit.from_dict(data)


def test_edit_round_trips_through_canonical_json(tmp_path):
    edit = valid_edit()

    text = edit.to_json()
    assert text.endswith("\n")
    assert json.loads(text)["version"] == 2
    assert KinoEdit.from_json(text) == edit

    path = tmp_path / "KINO-EDIT.json"
    write_edit_json(edit, path)
    assert load_edit(path) == edit


def test_rejects_duplicate_ids():
    data = valid_edit().to_dict()
    data["sources"].append(data["sources"][0])

    with pytest.raises(EditError, match="duplicate source id"):
        KinoEdit.from_dict(data)


def test_rejects_duplicate_word_token_ids():
    data = valid_edit().to_dict()
    data["transcript"]["words"][1]["id"] = "w001"

    with pytest.raises(EditError, match="duplicate word token id"):
        KinoEdit.from_dict(data)


def test_rejects_unstable_ids():
    data = valid_edit().to_dict()
    data["beats"][0]["id"] = "beat 001"

    with pytest.raises(EditError, match="stable id"):
        KinoEdit.from_dict(data)


def test_rejects_invalid_token_ranges():
    data = valid_edit().to_dict()
    data["beats"][0]["token_end"] = 99

    with pytest.raises(EditError, match="token range exceeds transcript length"):
        KinoEdit.from_dict(data)


def test_rejects_asset_source_reference_to_unknown_source():
    data = valid_edit().to_dict()
    data["assets"][0]["source_id"] = "src404"

    with pytest.raises(EditError, match="source_id references unknown source"):
        KinoEdit.from_dict(data)


def test_rejects_beat_references_to_unknown_sources_and_assets():
    data = valid_edit().to_dict()
    data["beats"][0]["source_ids"] = ["src404"]

    with pytest.raises(EditError, match="source_ids references unknown source"):
        KinoEdit.from_dict(data)

    data = valid_edit().to_dict()
    data["beats"][0]["asset_ids"] = ["asset404"]

    with pytest.raises(EditError, match="asset_ids references unknown asset"):
        KinoEdit.from_dict(data)


def test_rejects_selected_asset_not_listed_on_beat():
    data = valid_edit().to_dict()
    data["beats"][0]["asset_ids"] = []

    with pytest.raises(EditError, match="selected_asset_id must also be listed"):
        KinoEdit.from_dict(data)


def test_rejects_duplicate_beat_references():
    data = valid_edit().to_dict()
    data["beats"][0]["source_ids"] = ["src001", "src001"]

    with pytest.raises(EditError, match="duplicate beat001 source reference id"):
        KinoEdit.from_dict(data)


def test_rejects_beat_asset_from_unlisted_source():
    data = valid_edit().to_dict()
    data["sources"].append(
        {
            "id": "src002",
            "kind": "url",
            "locator": "https://example.com/other",
            "title": None,
            "author": None,
            "publisher": None,
            "license": None,
            "captured_at": None,
            "notes": None,
        }
    )
    data["assets"].append(
        {
            "id": "asset002",
            "source_id": "src002",
            "kind": "web",
            "uri": "captures/other.png",
            "start": None,
            "end": None,
            "width": None,
            "height": None,
            "score": None,
            "credit": None,
            "notes": None,
        }
    )
    data["beats"][0]["asset_ids"] = ["asset002"]
    data["beats"][0]["selected_asset_id"] = "asset002"

    with pytest.raises(EditError, match="references source not listed in source_ids"):
        KinoEdit.from_dict(data)


def test_enforces_approval_and_rejection_state_requirements():
    data = valid_edit().to_dict()
    data["beats"][0]["selected_asset_id"] = None

    with pytest.raises(EditError, match="approved beats require selected_asset_id"):
        KinoEdit.from_dict(data)

    data = valid_edit().to_dict()
    data["beats"][0]["status"] = "rejected"
    data["beats"][0]["selected_asset_id"] = None

    with pytest.raises(EditError, match="rejected beats require rejection_reason"):
        KinoEdit.from_dict(data)


def test_validate_edit_accepts_direct_dataclass_instances():
    edit = KinoEdit(
        id="edit002",
        transcript=Transcript(id="tx002", words=[token("w001", "hello", 0.0, 0.5)]),
        beats=[
            BeatCandidate(
                id="beat001",
                token_start=0,
                token_end=1,
                route="concept",
                interpretation="A simple concept beat.",
                source_plan="Use generated visual language only if approved later.",
            )
        ],
    )

    validate_edit(edit)
    assert edit.transcript.words[0].id == "w001"
    assert edit.beats[0].status == "proposed"

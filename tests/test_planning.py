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
)
from kino.planning import (
    add_beat_candidates,
    add_proposed_beat_candidates,
    approve_beat,
    initialize_edit_from_transcript_dict,
    initialize_edit_from_transcript_json,
    load_edit_from_transcript_json,
    load_transcript_json,
    reject_beat,
    transcript_from_dict,
    transcript_from_json,
)


def token(id_, text, start, end):
    return WordToken(id=id_, text=text, start=start, end=end)


def transcript_data():
    return {
        "id": "tx001",
        "language": "en",
        "source": "source.mp4",
        "words": [
            {"id": "w001", "text": "Kino", "start": 0.0, "end": 0.25},
            {"id": "w002", "text": "plans", "start": 0.25, "end": 0.6},
        ],
    }


def edit_with_asset():
    return KinoEdit(
        id="edit001",
        transcript=Transcript(id="tx001", words=(token("w001", "Kino", 0.0, 0.25),)),
        sources=(SourceReceipt(id="src001", kind="url", locator="https://example.com/source"),),
        assets=(AssetCandidate(id="asset001", source_id="src001", kind="web", uri="assets/source.png"),),
        beats=(
            BeatCandidate(
                id="beat001",
                token_start=0,
                token_end=1,
                route="receipt",
                interpretation="Show the source.",
                source_plan="Capture the source page.",
                source_ids=("src001",),
                asset_ids=("asset001",),
            ),
        ),
    )


def test_loads_transcript_shape_into_transcript_and_edit(tmp_path):
    path = tmp_path / "transcript.json"
    path.write_text(
        """
        {
          "id": "tx001",
          "language": "en",
          "source": "source.mp4",
          "words": [
            {"id": "w001", "text": "Kino", "start": 0.0, "end": 0.25},
            {"id": "w002", "text": "plans", "start": 0.25, "end": 0.6}
          ]
        }
        """
    )

    transcript = load_transcript_json(path)
    edit = load_edit_from_transcript_json(path, edit_id="edit001")

    assert transcript == transcript_from_dict(transcript_data())
    assert edit.id == "edit001"
    assert edit.transcript == transcript
    assert edit.sources == ()
    assert edit.assets == ()
    assert edit.beats == ()


def test_initializes_edit_from_top_level_transcript_payload():
    payload = {"id": "edit001", "transcript": transcript_data()}

    transcript = transcript_from_json(json.dumps({"transcript": transcript_data()}))
    edit = initialize_edit_from_transcript_dict(payload)

    assert transcript.id == "tx001"
    assert edit.id == "edit001"
    assert edit.transcript.id == "tx001"


def test_initializes_edit_from_transcript_json_with_override_id():
    edit = initialize_edit_from_transcript_json(
        '{"id": "ignored", "transcript": {"id": "tx001", "words": [{"id": "w001", "text": "Hi", "start": 0.0, "end": 0.1}]}}',
        edit_id="edit001",
    )

    assert edit.id == "edit001"
    assert edit.transcript.id == "tx001"


def test_add_beat_candidates_appends_proposed_beats_without_mutating_original():
    edit = KinoEdit(
        id="edit001",
        transcript=Transcript(id="tx001", words=(token("w001", "Kino", 0.0, 0.25),)),
    )

    updated = add_beat_candidates(
        edit,
        [
            {
                "id": "beat001",
                "token_start": 0,
                "token_end": 1,
                "route": "concept",
                "interpretation": "Show a concept visual.",
                "source_plan": "Generate after approval.",
                "status": "rejected",
                "rejection_reason": "old state is cleared",
            }
        ],
    )

    assert edit.beats == ()
    assert updated.beats[0].status == "proposed"
    assert updated.beats[0].rejection_reason is None
    assert updated.beats[0].selected_asset_id is None


def test_add_proposed_beat_candidates_alias_uses_same_behavior():
    edit = KinoEdit(
        id="edit001",
        transcript=Transcript(id="tx001", words=(token("w001", "Kino", 0.0, 0.25),)),
    )

    updated = add_proposed_beat_candidates(
        edit,
        BeatCandidate(
            id="beat001",
            token_start=0,
            token_end=1,
            route="concept",
            interpretation="Show a concept visual.",
            source_plan="Generate after approval.",
        ),
    )

    assert updated.beats[0].status == "proposed"


def test_add_beat_candidates_validates_resulting_edit():
    edit = KinoEdit(
        id="edit001",
        transcript=Transcript(id="tx001", words=(token("w001", "Kino", 0.0, 0.25),)),
    )

    with pytest.raises(EditError, match="token range exceeds transcript length"):
        add_beat_candidates(
            edit,
            {
                "id": "beat001",
                "token_start": 0,
                "token_end": 2,
                "route": "concept",
                "interpretation": "Show a concept visual.",
                "source_plan": "Generate after approval.",
            },
        )


def test_approve_beat_returns_updated_edit_and_preserves_original():
    edit = edit_with_asset()

    updated = approve_beat(edit, "beat001", "asset001")

    assert edit.beats[0].status == "proposed"
    assert edit.beats[0].selected_asset_id is None
    assert updated.beats[0].status == "approved"
    assert updated.beats[0].selected_asset_id == "asset001"
    assert updated.beats[0].rejection_reason is None


def test_approve_beat_rejects_unknown_or_unlisted_asset():
    edit = edit_with_asset()

    with pytest.raises(EditError, match="selected_asset_id references unknown asset"):
        approve_beat(edit, "beat001", "asset404")


def test_reject_beat_returns_updated_edit_and_clears_selection():
    approved = approve_beat(edit_with_asset(), "beat001", "asset001")

    updated = reject_beat(approved, "beat001", "Not the right source.")

    assert approved.beats[0].status == "approved"
    assert approved.beats[0].selected_asset_id == "asset001"
    assert updated.beats[0].status == "rejected"
    assert updated.beats[0].selected_asset_id is None
    assert updated.beats[0].rejection_reason == "Not the right source."


def test_reject_beat_requires_reason_and_known_beat():
    edit = edit_with_asset()

    with pytest.raises(EditError, match="unknown beat id"):
        reject_beat(edit, "beat404", "No.")

    with pytest.raises(EditError, match="rejected beats require rejection_reason"):
        reject_beat(edit, "beat001", "")

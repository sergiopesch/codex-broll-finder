import json
from dataclasses import replace

import pytest

from kino.edit import AssetCandidate, KinoEdit, SourceReceipt, Transcript, WordToken
from kino.plan import KinoPlan, PlanError, apply_plan_to_edit, plan_edit


def token(id_, text, start, end):
    return WordToken(id=id_, text=text, start=start, end=end)


def edit_with_assets():
    return KinoEdit(
        id="edit001",
        transcript=Transcript(
            id="tx001",
            words=(
                token("w001", "This", 0.0, 0.2),
                token("w002", "mistake", 0.2, 0.5),
                token("w003", "cost", 0.5, 0.8),
                token("w004", "us", 0.8, 1.0),
                token("w005", "a", 1.0, 1.1),
                token("w006", "week", 1.1, 1.3),
                token("w007", "watch", 1.3, 1.5),
                token("w008", "the", 1.5, 1.6),
                token("w009", "product", 1.6, 1.9),
                token("w010", "demo", 1.9, 2.2),
                token("w011", "proof", 2.2, 2.5),
                token("w012", "now", 2.5, 2.8),
            ),
        ),
        sources=(
            SourceReceipt(id="src001", kind="generated", locator="fixture://ui-proof", title="Product UI"),
            SourceReceipt(id="src002", kind="generated", locator="fixture://talking-head", title="Founder shot"),
        ),
        assets=(
            AssetCandidate(
                id="asset001",
                source_id="src001",
                kind="image",
                uri="assets/ui-proof.png",
                width=1080,
                height=1920,
                score=0.9,
                notes="product UI demo proof",
            ),
            AssetCandidate(
                id="asset002",
                source_id="src002",
                kind="video",
                uri="assets/founder.mp4",
                score=0.5,
                notes="talking head founder camera",
            ),
        ),
    )


def test_plan_edit_creates_reviewable_timeline_free_contract():
    plan = plan_edit(edit_with_assets(), archetype_id="social-short")
    data = plan.to_dict()

    assert data["schema"] == "kino.plan.v1"
    assert data["version"] == 1
    assert data["id"] == "edit001:social-short:plan"
    assert data["transcript_hash"].startswith("sha256:")
    assert data["summary"]["beat_count"] == len(data["beats"])
    assert data["summary"]["average_confidence"] > 0
    assert "duration" not in json.dumps(data)
    assert "start_ratio" not in json.dumps(data)
    assert "end_ratio" not in json.dumps(data)
    assert all(0 <= beat["confidence"] <= 1 for beat in data["beats"])
    assert all(beat["reasons"] for beat in data["beats"])
    assert all(beat["anchor"]["word_start_id"] for beat in data["beats"])
    assert all(beat["anchor"]["quote"] for beat in data["beats"])

    loaded = KinoPlan.from_json(plan.to_json())
    assert loaded == plan


def test_plan_edit_is_deterministic_and_does_not_fabricate_assets():
    edit = edit_with_assets()
    first = plan_edit(edit, archetype_id="founder-product-explainer")
    second = plan_edit(edit, archetype_id="founder-product-explainer")

    assert first.to_dict() == second.to_dict()
    asset_ids = {asset.id for asset in edit.assets}
    source_ids = {source.id for source in edit.sources}
    for beat in first.beats:
        for fit in beat.asset_fits:
            assert fit.asset_id in asset_ids
            assert fit.source_id in source_ids


def test_apply_plan_imports_proposed_beats_with_rationale_metadata():
    edit = edit_with_assets()
    plan = plan_edit(edit, archetype_id="social-short")

    updated = apply_plan_to_edit(edit, plan)

    assert edit.beats == ()
    assert len(updated.beats) == len(plan.beats)
    assert all(beat.status == "proposed" for beat in updated.beats)
    assert all(beat.selected_asset_id is None for beat in updated.beats)
    assert all(beat.plan_id == plan.id for beat in updated.beats)
    assert all(beat.role for beat in updated.beats)
    assert all(beat.confidence is not None and 0 <= beat.confidence <= 1 for beat in updated.beats)
    assert all(beat.reasons for beat in updated.beats)


def test_apply_plan_rejects_transcript_drift():
    edit = edit_with_assets()
    plan = plan_edit(edit, archetype_id="social-short")
    drifted = replace(
        edit,
        transcript=replace(
            edit.transcript,
            words=(*edit.transcript.words[:-1], token("w012", "later", 2.5, 2.8)),
        ),
    )

    with pytest.raises(PlanError, match="transcript_hash"):
        apply_plan_to_edit(drifted, plan)


def test_plan_validation_rejects_timeline_keys_in_json():
    data = plan_edit(edit_with_assets(), archetype_id="social-short").to_dict()
    data["beats"][0]["duration"] = 1.25

    with pytest.raises(PlanError, match="must not expose timeline"):
        KinoPlan.from_dict(data)


def test_empty_asset_inventory_still_produces_actionable_source_requests():
    edit = replace(edit_with_assets(), sources=(), assets=())
    plan = plan_edit(edit, archetype_id="social-short")

    assert plan.beats
    assert all(not beat.asset_fits for beat in plan.beats)
    assert any("No assets are attached" in note for note in plan.summary.review_notes)
    assert all(beat.source_plan.startswith("Source or generate") for beat in plan.beats)

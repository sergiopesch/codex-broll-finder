import json
from dataclasses import replace

import pytest

from kino.captions import plan_captions
from kino.edit import AssetCandidate, KinoEdit, SourceReceipt, Transcript, WordToken
from kino.eval import (
    EvalError,
    KinoEval,
    evaluate_artifacts,
    evaluate_captions,
    evaluate_plan,
    evaluate_status_report,
    write_eval_json,
    write_eval_markdown,
)
from kino.plan import plan_edit


def token(id_, text, start, end, confidence=None):
    return WordToken(id=id_, text=text, start=start, end=end, confidence=confidence)


def edit_with_assets():
    return KinoEdit(
        id="edit001",
        transcript=Transcript(
            id="tx001",
            words=(
                token("w001", "This", 0.0, 0.2, 0.9),
                token("w002", "mistake", 0.2, 0.5, 0.9),
                token("w003", "cost", 0.5, 0.8, 0.9),
                token("w004", "a", 0.8, 0.9, 0.9),
                token("w005", "week", 0.9, 1.2, 0.9),
                token("w006", "watch", 1.2, 1.5, 0.9),
                token("w007", "the", 1.5, 1.6, 0.9),
                token("w008", "demo", 1.6, 2.0, 0.9),
                token("w009", "proof", 2.0, 2.4, 0.9),
                token("w010", "now", 2.4, 2.7, 0.9),
            ),
        ),
        sources=(SourceReceipt(id="src001", kind="generated", locator="fixture://ui-proof"),),
        assets=(
            AssetCandidate(
                id="asset001",
                source_id="src001",
                kind="image",
                uri="assets/ui-proof.png",
                score=0.95,
                notes="product UI demo proof",
            ),
        ),
    )


def report(overall, checks):
    return {
        "overall": overall,
        "checks": [
            {
                "name": name,
                "status": status,
                "expected": "expected",
                "observed": "observed",
                "message": message,
            }
            for name, status, message in checks
        ],
    }


def test_evaluate_plan_scores_confidence_and_asset_coverage():
    plan = plan_edit(edit_with_assets(), archetype_id="social-short")

    checks = evaluate_plan(plan)

    assert {check.name for check in checks} == {
        "plan_average_confidence",
        "plan_asset_coverage",
        "plan_low_confidence_beats",
    }
    assert all(check.status == "pass" for check in checks)
    assert all(0 <= check.score <= 1 for check in checks)


def test_evaluate_captions_warns_on_low_confidence_segments():
    captions = plan_captions(edit_with_assets(), archetype_id="social-short")
    low = replace(captions.segments[0], confidence=0.5)
    captions = replace(captions, segments=(low, *captions.segments[1:]))

    checks = evaluate_captions(captions)

    assert any(check.name == "caption_low_confidence_segments" and check.status == "warning" for check in checks)
    assert any(check.recommendation for check in checks)


def test_evaluate_status_report_normalizes_existing_qc_shape():
    checks = evaluate_status_report(
        "export-validation",
        report(
            "manual-review-required",
            [
                ("dimensions", "pass", "Video dimensions match preset."),
                ("faststart", "manual-review-required", "Faststart needs manual review."),
            ],
        ),
    )

    assert checks[0].status == "manual-review-required"
    assert checks[1].status == "warning"
    assert checks[0].score < 1


def test_evaluate_artifacts_writes_roundtrippable_json_and_markdown(tmp_path):
    edit = edit_with_assets()
    plan_path = tmp_path / "KINO-PLAN.json"
    captions_path = tmp_path / "KINO-CAPTIONS.json"
    frame_path = tmp_path / "KINO-FRAME-QC.json"
    audio_path = tmp_path / "KINO-AUDIO-QC.json"
    export_path = tmp_path / "KINO-VALIDATION.json"
    plan_path.write_text(plan_edit(edit, archetype_id="social-short").to_json())
    captions_path.write_text(plan_captions(edit, archetype_id="social-short").to_json())
    frame_path.write_text(json.dumps(report("pass", [("frames", "pass", "Frames are readable.")])) + "\n")
    audio_path.write_text(json.dumps(report("warning", [("silence", "warning", "Review silence gap.")])) + "\n")
    export_path.write_text(json.dumps(report("pass", [("dimensions", "pass", "Dimensions match.")])) + "\n")

    evaluation = evaluate_artifacts(
        eval_id="eval001",
        plan_path=plan_path,
        captions_path=captions_path,
        frame_qc_path=frame_path,
        audio_qc_path=audio_path,
        export_validation_path=export_path,
    )
    json_out = write_eval_json(evaluation, tmp_path / "KINO-EVAL.json")
    md_out = write_eval_markdown(evaluation, tmp_path / "KINO-EVAL.md")

    assert evaluation.overall == "warning"
    assert evaluation.decision == "revise-before-handoff"
    assert evaluation.recommendations
    assert KinoEval.from_json(json_out.read_text()) == evaluation
    assert md_out.read_text().startswith("# Kino Evaluation Report")


def test_eval_validation_rejects_mismatched_score(tmp_path):
    plan_path = tmp_path / "KINO-PLAN.json"
    plan_path.write_text(plan_edit(edit_with_assets(), archetype_id="social-short").to_json())
    evaluation = evaluate_artifacts(
        plan_path=plan_path,
    )
    data = evaluation.to_dict()
    data["score"] = 0.0

    with pytest.raises(EvalError, match="score does not match"):
        KinoEval.from_dict(data)

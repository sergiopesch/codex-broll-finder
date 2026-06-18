import pytest

from kino.archetypes import (
    ArchetypeDefinition,
    ArchetypeError,
    BeatTemplate,
    ReferenceAnalysis,
    ReplicaBeatPlan,
    TranscriptCue,
    classify_archetype,
    default_archetype_definitions,
    get_archetype_definition,
    plan_replica_beats,
)


def cue(id_, kind, text, token_start=0, token_end=4, confidence=1.0):
    return TranscriptCue(
        id=id_,
        token_start=token_start,
        token_end=token_end,
        text=text,
        kind=kind,
        confidence=confidence,
    )


def social_analysis():
    return ReferenceAnalysis(
        id="ref-short",
        duration=28.0,
        platforms=("TikTok", "YouTube Shorts"),
        aspect_ratio="9:16",
        pacing="fast",
        primary_spine="talking head",
        visual_signals=("burned-in captions", "hard cuts", "product UI inserts"),
        proof_signals=("site montage",),
        cta="Visit the site.",
        transcript_cues=(
            cue("c001", "hook", "This mistake cost us a week", 0, 5, 0.98),
            cue("c002", "problem", "The workflow had too much dead air", 5, 12, 0.8),
            cue("c003", "claim", "The new agent fixes it", 12, 18, 0.85),
            cue("c004", "proof", "Here is the product doing it", 18, 26, 0.9),
            cue("c005", "cta", "Try it today", 26, 30, 0.7),
        ),
    )


def founder_analysis():
    return ReferenceAnalysis(
        id="ref-founder",
        duration=82.0,
        platforms=("YouTube", "Product Hunt"),
        aspect_ratio="16:9",
        pacing="medium",
        primary_spine="founder-led explanation",
        visual_signals=("screen recording", "product UI", "picture-in-picture workflow"),
        proof_signals=("customer result",),
        cta="Join the launch.",
        notes=("Founder origin story for a launch video.",),
        transcript_cues=(
            cue("c001", "hook", "We got a surprising result", 0, 6, 0.9),
            cue("c002", "problem", "Customers could not finish the workflow", 6, 20, 0.95),
            cue("c003", "claim", "Our product automates the hard part", 20, 30, 0.85),
            cue("c004", "demo", "Let me walk through the product", 30, 50, 0.9),
            cue("c005", "proof", "This customer shipped in one day", 50, 70, 0.8),
            cue("c006", "cta", "Join the waitlist", 70, 80, 0.75),
        ),
    )


def test_default_archetype_definitions_are_valid_and_serializable():
    definitions = default_archetype_definitions()

    assert set(definitions) == {"social-short", "founder-product-explainer"}
    assert get_archetype_definition("social-short").duration_range == (15.0, 60.0)
    assert ArchetypeDefinition.from_dict(definitions["founder-product-explainer"].to_dict()) == definitions[
        "founder-product-explainer"
    ]


def test_classifies_social_short_from_structured_reference_signals():
    match = classify_archetype(social_analysis())

    assert match.archetype_id == "social-short"
    assert match.confidence > 0.55
    assert match.scores["social-short"] > match.scores["founder-product-explainer"]
    assert "duration fits the 15-60s short format" in match.reasons


def test_classifies_founder_product_explainer_from_mapping_input():
    match = classify_archetype(founder_analysis().to_dict())

    assert match.archetype_id == "founder-product-explainer"
    assert match.confidence > 0.55
    assert match.scores["founder-product-explainer"] > match.scores["social-short"]
    assert "product walkthrough cue" in match.reasons


def test_plan_replica_beats_uses_selected_archetype_template_and_cues():
    plan = plan_replica_beats(social_analysis())

    assert plan.id == "ref-short:social-short:plan"
    assert plan.aspect_ratio == "9:16"
    assert plan.target_duration == 28.0
    assert [(beat.id, beat.role, beat.start, beat.end) for beat in plan.beats] == [
        ("beat:hook", "hook", 0.0, 2.24),
        ("beat:problem", "problem", 2.24, 8.96),
        ("beat:claim", "fix_or_claim", 8.96, 15.4),
        ("beat:proof", "proof_demo", 15.4, 22.96),
        ("beat:cta", "payoff_cta", 22.96, 28.0),
    ]
    assert plan.beats[0].cue_ids == ("c001", "c003")
    assert plan.beats[0].source_text == "This mistake cost us a week The new agent fixes it"
    assert plan.beats[-1].caption_style == "cta-emphasis"


def test_plan_replica_beats_can_force_archetype_and_clamps_default_duration():
    plan = plan_replica_beats(social_analysis(), archetype_id="founder-product-explainer")

    assert plan.archetype_id == "founder-product-explainer"
    assert plan.match.archetype_id == "social-short"
    assert plan.target_duration == 60.0
    assert plan.aspect_ratio == "16:9"
    assert [beat.role for beat in plan.beats] == [
        "cold_open",
        "origin_problem",
        "product_positioning",
        "live_walkthrough",
        "proof_validation",
        "cta",
    ]


def test_reference_analysis_validation_rejects_bad_cues():
    with pytest.raises(ArchetypeError, match="duplicate transcript cue id"):
        ReferenceAnalysis(
            id="bad-ref",
            duration=20.0,
            transcript_cues=(
                cue("c001", "hook", "first"),
                cue("c001", "proof", "second"),
            ),
        )

    with pytest.raises(ArchetypeError, match="confidence must be between 0 and 1"):
        ReferenceAnalysis(
            id="bad-ref",
            duration=20.0,
            transcript_cues=(cue("c001", "hook", "first", confidence=1.5),),
        )


def test_archetype_definition_validation_rejects_overlapping_template_ratios():
    with pytest.raises(ArchetypeError, match="sorted and non-overlapping"):
        ArchetypeDefinition(
            id="social-short",
            name="Bad",
            summary="Bad template",
            target_platforms=("TikTok",),
            duration_range=(15.0, 60.0),
            aspect_ratios=("9:16",),
            primary_spine="talking head",
            grammar=("bad",),
            beat_templates=(
                BeatTemplate(
                    id="a",
                    role="a",
                    start_ratio=0.0,
                    end_ratio=0.8,
                    intent="A",
                    visual_plan="A",
                ),
                BeatTemplate(
                    id="b",
                    role="b",
                    start_ratio=0.7,
                    end_ratio=1.0,
                    intent="B",
                    visual_plan="B",
                ),
            ),
        )


def test_plan_serializes_to_simple_cli_friendly_dict():
    plan = plan_replica_beats(founder_analysis())
    data = plan.to_dict()

    assert data["source_analysis_id"] == "ref-founder"
    assert data["archetype_id"] == "founder-product-explainer"
    assert data["beats"][3]["role"] == "live_walkthrough"
    assert data["beats"][3]["cue_ids"] == ["c004"]
    assert data["match"]["archetype_id"] == "founder-product-explainer"
    assert ReplicaBeatPlan.from_dict(data) == plan

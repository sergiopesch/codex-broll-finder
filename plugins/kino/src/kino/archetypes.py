from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

ArchetypeId = Literal["social-short", "founder-product-explainer"]
CueKind = Literal["hook", "problem", "claim", "proof", "demo", "cta", "caption", "transition", "filler", "other"]
Pacing = Literal["fast", "medium", "slow", "unknown"]


class ArchetypeError(ValueError):
    pass


@dataclass(frozen=True)
class BeatTemplate:
    id: str
    role: str
    start_ratio: float
    end_ratio: float
    intent: str
    visual_plan: str
    preferred_cue_kinds: tuple[CueKind, ...] = ()
    caption_style: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "preferred_cue_kinds", tuple(_cue_kind(kind) for kind in self.preferred_cue_kinds))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> BeatTemplate:
        return cls(
            id=_required_str(data, "id"),
            role=_required_str(data, "role"),
            start_ratio=_required_float(data, "start_ratio"),
            end_ratio=_required_float(data, "end_ratio"),
            intent=_required_str(data, "intent"),
            visual_plan=_required_str(data, "visual_plan"),
            preferred_cue_kinds=_cue_kind_tuple(data.get("preferred_cue_kinds", ()), "preferred_cue_kinds"),
            caption_style=_optional_str(data, "caption_style"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "role": self.role,
            "start_ratio": self.start_ratio,
            "end_ratio": self.end_ratio,
            "intent": self.intent,
            "visual_plan": self.visual_plan,
            "preferred_cue_kinds": list(self.preferred_cue_kinds),
            "caption_style": self.caption_style,
        }


@dataclass(frozen=True)
class ArchetypeDefinition:
    id: ArchetypeId
    name: str
    summary: str
    target_platforms: tuple[str, ...]
    duration_range: tuple[float, float]
    aspect_ratios: tuple[str, ...]
    primary_spine: str
    grammar: tuple[str, ...]
    beat_templates: tuple[BeatTemplate, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_platforms", tuple(self.target_platforms))
        object.__setattr__(self, "duration_range", _float_pair(self.duration_range, "duration_range"))
        object.__setattr__(self, "aspect_ratios", tuple(self.aspect_ratios))
        object.__setattr__(self, "grammar", tuple(self.grammar))
        object.__setattr__(self, "beat_templates", tuple(self.beat_templates))
        validate_archetype_definition(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ArchetypeDefinition:
        return cls(
            id=_archetype_id(_required_str(data, "id")),
            name=_required_str(data, "name"),
            summary=_required_str(data, "summary"),
            target_platforms=_str_tuple(data.get("target_platforms", ()), "target_platforms"),
            duration_range=_float_pair(_sequence(data.get("duration_range", ()), "duration_range"), "duration_range"),
            aspect_ratios=_str_tuple(data.get("aspect_ratios", ()), "aspect_ratios"),
            primary_spine=_required_str(data, "primary_spine"),
            grammar=_str_tuple(data.get("grammar", ()), "grammar"),
            beat_templates=tuple(
                BeatTemplate.from_dict(_mapping(item, "beat template"))
                for item in _sequence(data.get("beat_templates", ()), "beat_templates")
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "summary": self.summary,
            "target_platforms": list(self.target_platforms),
            "duration_range": list(self.duration_range),
            "aspect_ratios": list(self.aspect_ratios),
            "primary_spine": self.primary_spine,
            "grammar": list(self.grammar),
            "beat_templates": [template.to_dict() for template in self.beat_templates],
        }


@dataclass(frozen=True)
class TranscriptCue:
    id: str
    token_start: int
    token_end: int
    text: str
    kind: CueKind
    confidence: float = 1.0
    note: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _cue_kind(self.kind))
        object.__setattr__(self, "confidence", _bounded(float(self.confidence), "confidence"))
        if self.token_start < 0:
            raise ArchetypeError(f"{self.id}: token_start must be >= 0")
        if self.token_end <= self.token_start:
            raise ArchetypeError(f"{self.id}: token_end must be after token_start")
        if self.text == "":
            raise ArchetypeError(f"{self.id}: text must not be empty")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> TranscriptCue:
        return cls(
            id=_required_str(data, "id"),
            token_start=_required_int(data, "token_start"),
            token_end=_required_int(data, "token_end"),
            text=_required_str(data, "text"),
            kind=_cue_kind(_required_str(data, "kind")),
            confidence=_optional_float(data, "confidence", default=1.0),
            note=_optional_str(data, "note"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "token_start": self.token_start,
            "token_end": self.token_end,
            "text": self.text,
            "kind": self.kind,
            "confidence": self.confidence,
            "note": self.note,
        }


@dataclass(frozen=True)
class ReferenceAnalysis:
    id: str
    duration: float
    transcript_cues: tuple[TranscriptCue, ...]
    platforms: tuple[str, ...] = ()
    aspect_ratio: str | None = None
    pacing: Pacing = "unknown"
    primary_spine: str | None = None
    visual_signals: tuple[str, ...] = ()
    proof_signals: tuple[str, ...] = ()
    cta: str | None = None
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "duration", _seconds(self.duration, "duration"))
        object.__setattr__(self, "transcript_cues", tuple(self.transcript_cues))
        object.__setattr__(self, "platforms", tuple(self.platforms))
        object.__setattr__(self, "pacing", _pacing(self.pacing))
        object.__setattr__(self, "visual_signals", tuple(self.visual_signals))
        object.__setattr__(self, "proof_signals", tuple(self.proof_signals))
        object.__setattr__(self, "notes", tuple(self.notes))
        validate_reference_analysis(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ReferenceAnalysis:
        return cls(
            id=_required_str(data, "id"),
            duration=_required_float(data, "duration"),
            transcript_cues=tuple(
                TranscriptCue.from_dict(_mapping(item, "transcript cue"))
                for item in _sequence(data.get("transcript_cues", ()), "transcript_cues")
            ),
            platforms=_str_tuple(data.get("platforms", ()), "platforms"),
            aspect_ratio=_optional_str(data, "aspect_ratio"),
            pacing=_pacing(str(data.get("pacing", "unknown"))),
            primary_spine=_optional_str(data, "primary_spine"),
            visual_signals=_str_tuple(data.get("visual_signals", ()), "visual_signals"),
            proof_signals=_str_tuple(data.get("proof_signals", ()), "proof_signals"),
            cta=_optional_str(data, "cta"),
            notes=_str_tuple(data.get("notes", ()), "notes"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "duration": self.duration,
            "transcript_cues": [cue.to_dict() for cue in self.transcript_cues],
            "platforms": list(self.platforms),
            "aspect_ratio": self.aspect_ratio,
            "pacing": self.pacing,
            "primary_spine": self.primary_spine,
            "visual_signals": list(self.visual_signals),
            "proof_signals": list(self.proof_signals),
            "cta": self.cta,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class ArchetypeMatch:
    archetype_id: ArchetypeId
    confidence: float
    scores: dict[ArchetypeId, float]
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "archetype_id", _archetype_id(self.archetype_id))
        object.__setattr__(self, "confidence", _bounded(self.confidence, "confidence"))
        object.__setattr__(self, "scores", dict(self.scores))
        object.__setattr__(self, "reasons", tuple(self.reasons))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ArchetypeMatch:
        return cls(
            archetype_id=_archetype_id(_required_str(data, "archetype_id")),
            confidence=_required_float(data, "confidence"),
            scores=_score_dict(_mapping(data.get("scores"), "scores")),
            reasons=_str_tuple(data.get("reasons", ()), "reasons"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "archetype_id": self.archetype_id,
            "confidence": self.confidence,
            "scores": dict(self.scores),
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class ReplicaBeat:
    id: str
    role: str
    start: float
    end: float
    intent: str
    visual_plan: str
    cue_ids: tuple[str, ...] = ()
    source_text: str | None = None
    caption_style: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "start", _seconds(self.start, "start"))
        object.__setattr__(self, "end", _seconds(self.end, "end"))
        object.__setattr__(self, "cue_ids", tuple(self.cue_ids))
        if self.end <= self.start:
            raise ArchetypeError(f"{self.id}: end must be after start")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ReplicaBeat:
        return cls(
            id=_required_str(data, "id"),
            role=_required_str(data, "role"),
            start=_required_float(data, "start"),
            end=_required_float(data, "end"),
            intent=_required_str(data, "intent"),
            visual_plan=_required_str(data, "visual_plan"),
            cue_ids=_str_tuple(data.get("cue_ids", ()), "cue_ids"),
            source_text=_optional_str(data, "source_text"),
            caption_style=_optional_str(data, "caption_style"),
        )

    @property
    def duration(self) -> float:
        return _seconds(self.end - self.start, "duration")

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "role": self.role,
            "start": self.start,
            "end": self.end,
            "duration": self.duration,
            "intent": self.intent,
            "visual_plan": self.visual_plan,
            "cue_ids": list(self.cue_ids),
            "source_text": self.source_text,
            "caption_style": self.caption_style,
        }


@dataclass(frozen=True)
class ReplicaBeatPlan:
    id: str
    source_analysis_id: str
    archetype_id: ArchetypeId
    target_duration: float
    aspect_ratio: str
    beats: tuple[ReplicaBeat, ...]
    match: ArchetypeMatch

    def __post_init__(self) -> None:
        object.__setattr__(self, "archetype_id", _archetype_id(self.archetype_id))
        object.__setattr__(self, "target_duration", _seconds(self.target_duration, "target_duration"))
        object.__setattr__(self, "beats", tuple(self.beats))
        validate_replica_beat_plan(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ReplicaBeatPlan:
        return cls(
            id=_required_str(data, "id"),
            source_analysis_id=_required_str(data, "source_analysis_id"),
            archetype_id=_archetype_id(_required_str(data, "archetype_id")),
            target_duration=_required_float(data, "target_duration"),
            aspect_ratio=_required_str(data, "aspect_ratio"),
            beats=tuple(
                ReplicaBeat.from_dict(_mapping(item, "replica beat"))
                for item in _sequence(data.get("beats", ()), "beats")
            ),
            match=ArchetypeMatch.from_dict(_mapping(data.get("match"), "match")),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "source_analysis_id": self.source_analysis_id,
            "archetype_id": self.archetype_id,
            "target_duration": self.target_duration,
            "aspect_ratio": self.aspect_ratio,
            "beats": [beat.to_dict() for beat in self.beats],
            "match": self.match.to_dict(),
        }


def default_archetype_definitions() -> dict[ArchetypeId, ArchetypeDefinition]:
    return {
        "social-short": ArchetypeDefinition(
            id="social-short",
            name="Social Short",
            summary="A compact vertical edit optimized for retention, clarity, proof, and fast payoff.",
            target_platforms=("YouTube Shorts", "TikTok", "Instagram Reels", "LinkedIn", "X"),
            duration_range=(15.0, 60.0),
            aspect_ratios=("9:16",),
            primary_spine="talking head or voiceover",
            grammar=(
                "Open with a provocative hook.",
                "Compress speech and remove dead air.",
                "Tie proof visuals to concrete claims every 2-4 seconds.",
                "Use bold burned-in captions with short emphasized phrases.",
                "End with a CTA or proof montage.",
            ),
            beat_templates=(
                BeatTemplate(
                    id="hook",
                    role="hook",
                    start_ratio=0.0,
                    end_ratio=0.08,
                    intent="Create immediate curiosity or tension.",
                    visual_plan="Start on the strongest talking-head moment or proof visual.",
                    preferred_cue_kinds=("hook", "claim"),
                    caption_style="bold-emphasis",
                ),
                BeatTemplate(
                    id="problem",
                    role="problem",
                    start_ratio=0.08,
                    end_ratio=0.32,
                    intent="Frame the problem, confession, or setup quickly.",
                    visual_plan="Use tight talking-head cuts with captions and minimal dead air.",
                    preferred_cue_kinds=("problem", "caption"),
                    caption_style="bold-emphasis",
                ),
                BeatTemplate(
                    id="claim",
                    role="fix_or_claim",
                    start_ratio=0.32,
                    end_ratio=0.55,
                    intent="State the fix, upgrade, or core product claim.",
                    visual_plan="Introduce product, UI, or object inserts tied to the claim.",
                    preferred_cue_kinds=("claim", "demo"),
                    caption_style="bold-emphasis",
                ),
                BeatTemplate(
                    id="proof",
                    role="proof_demo",
                    start_ratio=0.55,
                    end_ratio=0.82,
                    intent="Make the claim visible with concrete proof or demo footage.",
                    visual_plan="Cut between proof inserts, UI details, and the narrative spine.",
                    preferred_cue_kinds=("proof", "demo"),
                    caption_style="selective-proof-labels",
                ),
                BeatTemplate(
                    id="cta",
                    role="payoff_cta",
                    start_ratio=0.82,
                    end_ratio=1.0,
                    intent="Deliver payoff and a clear next action.",
                    visual_plan="Finish with product/site CTA or a fast proof montage.",
                    preferred_cue_kinds=("cta", "proof"),
                    caption_style="cta-emphasis",
                ),
            ),
        ),
        "founder-product-explainer": ArchetypeDefinition(
            id="founder-product-explainer",
            name="Founder Product Explainer",
            summary="A founder-led launch or demo edit that makes the problem, product promise, proof, and CTA clear.",
            target_platforms=("YouTube", "Landing Page", "Product Hunt", "Investor Update", "Customer Update"),
            duration_range=(60.0, 120.0),
            aspect_ratios=("16:9", "9:16"),
            primary_spine="founder-led explanation",
            grammar=(
                "Open with a surprising result.",
                "Explain the origin story and user problem.",
                "Position the product before the walkthrough.",
                "Show UI long enough to understand the workflow.",
                "Use proof shots to validate the product claim.",
                "Close with a clean explicit CTA.",
            ),
            beat_templates=(
                BeatTemplate(
                    id="cold-open",
                    role="cold_open",
                    start_ratio=0.0,
                    end_ratio=0.08,
                    intent="Open with the result, promise, or surprising outcome.",
                    visual_plan="Use founder camera, result footage, or the product end-state.",
                    preferred_cue_kinds=("hook", "claim"),
                    caption_style="clarity-caption",
                ),
                BeatTemplate(
                    id="problem",
                    role="origin_problem",
                    start_ratio=0.08,
                    end_ratio=0.30,
                    intent="Explain the origin story and the user problem.",
                    visual_plan="Keep founder-led context on screen with restrained supporting captions.",
                    preferred_cue_kinds=("problem",),
                    caption_style="clarity-caption",
                ),
                BeatTemplate(
                    id="positioning",
                    role="product_positioning",
                    start_ratio=0.30,
                    end_ratio=0.45,
                    intent="Define what the product is and why it matters.",
                    visual_plan="Introduce product UI or object shots with enough scale to understand.",
                    preferred_cue_kinds=("claim",),
                    caption_style="clarity-caption",
                ),
                BeatTemplate(
                    id="walkthrough",
                    role="live_walkthrough",
                    start_ratio=0.45,
                    end_ratio=0.70,
                    intent="Walk through the core workflow or demo sequence.",
                    visual_plan="Show screen recordings, UI states, and optional face-camera picture-in-picture.",
                    preferred_cue_kinds=("demo",),
                    caption_style="workflow-labels",
                ),
                BeatTemplate(
                    id="proof",
                    role="proof_validation",
                    start_ratio=0.70,
                    end_ratio=0.88,
                    intent="Validate the product claim with physical, customer, or result proof.",
                    visual_plan="Use proof shots, outcome footage, or before/after evidence.",
                    preferred_cue_kinds=("proof",),
                    caption_style="proof-labels",
                ),
                BeatTemplate(
                    id="cta",
                    role="cta",
                    start_ratio=0.88,
                    end_ratio=1.0,
                    intent="Close with a clean next step.",
                    visual_plan="Return to founder or product end card with explicit CTA.",
                    preferred_cue_kinds=("cta",),
                    caption_style="clean-cta",
                ),
            ),
        ),
    }


def get_archetype_definition(archetype_id: ArchetypeId) -> ArchetypeDefinition:
    return default_archetype_definitions()[_archetype_id(archetype_id)]


def reference_analysis_from_json(text: str) -> ReferenceAnalysis:
    data = json.loads(text)
    if not isinstance(data, Mapping):
        raise ArchetypeError("reference analysis JSON must be an object")
    return ReferenceAnalysis.from_dict(data)


def load_reference_analysis_json(path: str | Path) -> ReferenceAnalysis:
    return reference_analysis_from_json(Path(path).read_text())


def classify_archetype(analysis: ReferenceAnalysis | Mapping[str, Any]) -> ArchetypeMatch:
    reference = _analysis(analysis)
    social_score, social_reasons = _social_short_score(reference)
    founder_score, founder_reasons = _founder_explainer_score(reference)
    scores: dict[ArchetypeId, float] = {
        "social-short": round(social_score, 3),
        "founder-product-explainer": round(founder_score, 3),
    }
    if social_score >= founder_score:
        archetype_id: ArchetypeId = "social-short"
        reasons = social_reasons
    else:
        archetype_id = "founder-product-explainer"
        reasons = founder_reasons

    total = social_score + founder_score
    confidence = 0.5 if total == 0 else max(social_score, founder_score) / total
    return ArchetypeMatch(
        archetype_id=archetype_id,
        confidence=round(confidence, 3),
        scores=scores,
        reasons=tuple(reasons),
    )


def plan_replica_beats(
    analysis: ReferenceAnalysis | Mapping[str, Any],
    *,
    archetype_id: ArchetypeId | None = None,
    target_duration: float | None = None,
) -> ReplicaBeatPlan:
    reference = _analysis(analysis)
    match = classify_archetype(reference)
    selected_id = _archetype_id(archetype_id) if archetype_id is not None else match.archetype_id
    definition = get_archetype_definition(selected_id)
    duration = _target_duration(reference, definition, target_duration)
    beats = tuple(_replica_beat(template, reference, duration) for template in definition.beat_templates)
    aspect_ratio = _target_aspect_ratio(reference, definition, forced=archetype_id is not None)
    return ReplicaBeatPlan(
        id=f"{reference.id}:{selected_id}:plan",
        source_analysis_id=reference.id,
        archetype_id=selected_id,
        target_duration=duration,
        aspect_ratio=aspect_ratio,
        beats=beats,
        match=match,
    )


def validate_archetype_definition(definition: ArchetypeDefinition) -> None:
    if definition.duration_range[0] <= 0 or definition.duration_range[1] < definition.duration_range[0]:
        raise ArchetypeError(f"{definition.id}: duration_range must be positive and ordered")
    if not definition.aspect_ratios:
        raise ArchetypeError(f"{definition.id}: at least one aspect ratio is required")
    if not definition.beat_templates:
        raise ArchetypeError(f"{definition.id}: at least one beat template is required")

    last_end = 0.0
    seen: set[str] = set()
    for template in definition.beat_templates:
        if template.id in seen:
            raise ArchetypeError(f"{definition.id}: duplicate beat template id: {template.id}")
        seen.add(template.id)
        if template.start_ratio < 0 or template.end_ratio > 1:
            raise ArchetypeError(f"{template.id}: beat template ratios must be within 0..1")
        if template.end_ratio <= template.start_ratio:
            raise ArchetypeError(f"{template.id}: end_ratio must be after start_ratio")
        if template.start_ratio < last_end:
            raise ArchetypeError(f"{template.id}: beat templates must be sorted and non-overlapping")
        last_end = template.end_ratio


def validate_reference_analysis(analysis: ReferenceAnalysis) -> None:
    if analysis.duration <= 0:
        raise ArchetypeError(f"{analysis.id}: duration must be positive")
    seen: set[str] = set()
    for cue in analysis.transcript_cues:
        if cue.id in seen:
            raise ArchetypeError(f"{analysis.id}: duplicate transcript cue id: {cue.id}")
        seen.add(cue.id)
        _cue_kind(cue.kind)
        _bounded(cue.confidence, "confidence")


def validate_replica_beat_plan(plan: ReplicaBeatPlan) -> None:
    if plan.target_duration <= 0:
        raise ArchetypeError(f"{plan.id}: target_duration must be positive")
    seen: set[str] = set()
    last_end = 0.0
    for beat in plan.beats:
        if beat.id in seen:
            raise ArchetypeError(f"{plan.id}: duplicate beat id: {beat.id}")
        seen.add(beat.id)
        if beat.start < last_end:
            raise ArchetypeError(f"{beat.id}: beats must be sorted and non-overlapping")
        if beat.end > plan.target_duration:
            raise ArchetypeError(f"{beat.id}: beat ends after target_duration")
        last_end = beat.end


def _analysis(value: ReferenceAnalysis | Mapping[str, Any]) -> ReferenceAnalysis:
    if isinstance(value, ReferenceAnalysis):
        return value
    return ReferenceAnalysis.from_dict(value)


def _replica_beat(template: BeatTemplate, analysis: ReferenceAnalysis, duration: float) -> ReplicaBeat:
    cues = _matching_cues(template, analysis.transcript_cues)
    cue_ids = tuple(cue.id for cue in cues)
    return ReplicaBeat(
        id=f"beat:{template.id}",
        role=template.role,
        start=duration * template.start_ratio,
        end=duration * template.end_ratio,
        intent=template.intent,
        visual_plan=template.visual_plan,
        cue_ids=cue_ids,
        source_text=_source_text(cues),
        caption_style=template.caption_style,
    )


def _matching_cues(template: BeatTemplate, cues: tuple[TranscriptCue, ...]) -> tuple[TranscriptCue, ...]:
    if not template.preferred_cue_kinds:
        return ()
    matched = [cue for cue in cues if cue.kind in template.preferred_cue_kinds]
    return tuple(sorted(matched, key=lambda cue: (-cue.confidence, cue.token_start, cue.id))[:2])


def _source_text(cues: tuple[TranscriptCue, ...]) -> str | None:
    if not cues:
        return None
    return " ".join(cue.text for cue in sorted(cues, key=lambda cue: cue.token_start))


def _target_duration(
    analysis: ReferenceAnalysis,
    definition: ArchetypeDefinition,
    requested: float | None,
) -> float:
    if requested is not None:
        return _seconds(requested, "target_duration")
    low, high = definition.duration_range
    return _seconds(min(max(analysis.duration, low), high), "target_duration")


def _target_aspect_ratio(
    analysis: ReferenceAnalysis,
    definition: ArchetypeDefinition,
    *,
    forced: bool,
) -> str:
    if not forced and analysis.aspect_ratio in definition.aspect_ratios:
        return str(analysis.aspect_ratio)
    return definition.aspect_ratios[0]


def _social_short_score(analysis: ReferenceAnalysis) -> tuple[float, list[str]]:
    text = _search_text(analysis)
    score = 0.0
    reasons: list[str] = []
    if analysis.duration <= 60:
        score += 2.0
        reasons.append("duration fits the 15-60s short format")
    elif analysis.duration <= 90:
        score += 1.0
        reasons.append("duration is close to short-form pacing")
    if analysis.aspect_ratio == "9:16" or _contains_any(text, ("shorts", "tiktok", "reels", "vertical")):
        score += 1.5
        reasons.append("vertical/social platform signal")
    if analysis.pacing == "fast":
        score += 1.25
        reasons.append("fast pacing signal")
    if _has_cue(analysis, "hook"):
        score += 1.0
        reasons.append("explicit hook cue")
    if _has_cue(analysis, "cta"):
        score += 0.75
        reasons.append("CTA/payoff cue")
    if _contains_any(text, ("caption", "burned-in", "emphasis", "hard cut", "dead air", "montage")):
        score += 1.0
        reasons.append("short-form caption or hard-cut grammar")
    if _has_cue(analysis, "proof") or analysis.proof_signals:
        score += 0.75
        reasons.append("proof visual signal")
    return score, reasons or ["no strong structured signal"]


def _founder_explainer_score(analysis: ReferenceAnalysis) -> tuple[float, list[str]]:
    text = _search_text(analysis)
    score = 0.0
    reasons: list[str] = []
    if 60 <= analysis.duration <= 140:
        score += 2.0
        reasons.append("duration fits the 60-120s explainer range")
    elif analysis.duration > 45:
        score += 0.75
        reasons.append("duration supports a fuller explanation")
    if analysis.aspect_ratio == "16:9" or _contains_any(text, ("youtube", "landing page", "product hunt", "launch")):
        score += 1.25
        reasons.append("horizontal launch/demo platform signal")
    if _contains_any(text, ("founder", "origin", "customer", "investor")):
        score += 1.25
        reasons.append("founder or launch narrative signal")
    if _has_cue(analysis, "problem"):
        score += 1.0
        reasons.append("problem cue")
    if _has_cue(analysis, "demo"):
        score += 1.0
        reasons.append("product walkthrough cue")
    if _has_cue(analysis, "proof") or analysis.proof_signals:
        score += 0.75
        reasons.append("proof or validation cue")
    if analysis.pacing in ("medium", "slow"):
        score += 0.75
        reasons.append("explainer pacing signal")
    if _contains_any(text, ("screen recording", "walkthrough", "picture-in-picture", "workflow", "product ui")):
        score += 1.0
        reasons.append("product UI walkthrough signal")
    return score, reasons or ["no strong structured signal"]


def _search_text(analysis: ReferenceAnalysis) -> str:
    parts = [
        *analysis.platforms,
        analysis.aspect_ratio or "",
        analysis.pacing,
        analysis.primary_spine or "",
        *analysis.visual_signals,
        *analysis.proof_signals,
        analysis.cta or "",
        *analysis.notes,
        *(cue.kind for cue in analysis.transcript_cues),
        *(cue.text for cue in analysis.transcript_cues),
    ]
    return " ".join(parts).lower()


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _has_cue(analysis: ReferenceAnalysis, kind: CueKind) -> bool:
    return any(cue.kind == kind for cue in analysis.transcript_cues)


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ArchetypeError(f"{label} must be an object")
    return value


def _sequence(value: object, key: str) -> tuple[object, ...]:
    if not isinstance(value, list | tuple):
        raise ArchetypeError(f"{key} must be a list")
    return tuple(value)


def _required_str(data: Mapping[str, Any], key: str) -> str:
    if key not in data:
        raise ArchetypeError(f"missing required key: {key}")
    value = data[key]
    if not isinstance(value, str):
        raise ArchetypeError(f"{key} must be a string")
    return value


def _optional_str(data: Mapping[str, Any], key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ArchetypeError(f"{key} must be a string")
    return value


def _required_float(data: Mapping[str, Any], key: str) -> float:
    if key not in data:
        raise ArchetypeError(f"missing required key: {key}")
    return _number(data[key], key)


def _optional_float(data: Mapping[str, Any], key: str, *, default: float | None = None) -> float:
    value = data.get(key, default)
    if value is None:
        raise ArchetypeError(f"{key} must be a number")
    return _number(value, key)


def _number(value: object, key: str) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ArchetypeError(f"{key} must be a number")
    return float(value)


def _required_int(data: Mapping[str, Any], key: str) -> int:
    if key not in data:
        raise ArchetypeError(f"missing required key: {key}")
    value = data[key]
    if not isinstance(value, int) or isinstance(value, bool):
        raise ArchetypeError(f"{key} must be an integer")
    return value


def _str_tuple(value: object, key: str) -> tuple[str, ...]:
    items = _sequence(value, key)
    for item in items:
        if not isinstance(item, str):
            raise ArchetypeError(f"{key} values must be strings")
    return tuple(items)


def _score_dict(data: Mapping[str, Any]) -> dict[ArchetypeId, float]:
    scores: dict[ArchetypeId, float] = {}
    for key, value in data.items():
        if not isinstance(key, str):
            raise ArchetypeError("score keys must be strings")
        scores[_archetype_id(key)] = _number(value, f"scores.{key}")
    return scores


def _cue_kind(value: str) -> CueKind:
    if value not in ("hook", "problem", "claim", "proof", "demo", "cta", "caption", "transition", "filler", "other"):
        raise ArchetypeError(f"unsupported cue kind: {value}")
    return value  # type: ignore[return-value]


def _cue_kind_tuple(value: object, key: str) -> tuple[CueKind, ...]:
    return tuple(_cue_kind(item) for item in _str_tuple(value, key))


def _archetype_id(value: str) -> ArchetypeId:
    if value not in ("social-short", "founder-product-explainer"):
        raise ArchetypeError(f"unsupported archetype id: {value}")
    return value  # type: ignore[return-value]


def _pacing(value: str) -> Pacing:
    if value not in ("fast", "medium", "slow", "unknown"):
        raise ArchetypeError(f"unsupported pacing: {value}")
    return value  # type: ignore[return-value]


def _float_pair(value: object, key: str) -> tuple[float, float]:
    items = _sequence(value, key)
    if len(items) != 2:
        raise ArchetypeError(f"{key} must contain exactly two numbers")
    return (_number(items[0], key), _number(items[1], key))


def _seconds(value: float, key: str) -> float:
    if value < 0:
        raise ArchetypeError(f"{key} must be >= 0")
    return round(float(value), 3)


def _bounded(value: float, key: str) -> float:
    if not 0 <= value <= 1:
        raise ArchetypeError(f"{key} must be between 0 and 1")
    return value


__all__ = [
    "ArchetypeDefinition",
    "ArchetypeError",
    "ArchetypeId",
    "ArchetypeMatch",
    "BeatTemplate",
    "CueKind",
    "Pacing",
    "ReferenceAnalysis",
    "ReplicaBeat",
    "ReplicaBeatPlan",
    "TranscriptCue",
    "classify_archetype",
    "default_archetype_definitions",
    "get_archetype_definition",
    "load_reference_analysis_json",
    "plan_replica_beats",
    "reference_analysis_from_json",
    "validate_archetype_definition",
    "validate_reference_analysis",
    "validate_replica_beat_plan",
]

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, Mapping

from .archetypes import ArchetypeId, BeatTemplate, get_archetype_definition
from .edit import AssetCandidate, BeatCandidate, KinoEdit, SourceReceipt, WordToken, validate_edit

KINO_PLAN_VERSION = 1
KINO_PLAN_SCHEMA = "kino.plan.v1"

PlanCueKind = Literal["hook", "problem", "claim", "proof", "demo", "cta", "transition", "filler", "other"]


class PlanError(ValueError):
    pass


@dataclass(frozen=True)
class PlanCue:
    id: str
    kind: PlanCueKind
    token_start: int
    token_end: int
    text: str
    confidence: float
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _cue_kind(self.kind))
        object.__setattr__(self, "confidence", _bounded(self.confidence, "confidence"))
        object.__setattr__(self, "reasons", tuple(self.reasons))
        if self.token_start < 0:
            raise PlanError(f"{self.id}: token_start must be >= 0")
        if self.token_end <= self.token_start:
            raise PlanError(f"{self.id}: token_end must be after token_start")
        if not self.text:
            raise PlanError(f"{self.id}: text must not be empty")
        if not self.reasons:
            raise PlanError(f"{self.id}: at least one cue reason is required")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PlanCue:
        return cls(
            id=_required_str(data, "id"),
            kind=_cue_kind(_required_str(data, "kind")),
            token_start=_required_int(data, "token_start"),
            token_end=_required_int(data, "token_end"),
            text=_required_str(data, "text"),
            confidence=_required_float(data, "confidence"),
            reasons=_str_tuple(data.get("reasons", ()), "reasons"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "kind": self.kind,
            "token_start": self.token_start,
            "token_end": self.token_end,
            "text": self.text,
            "confidence": self.confidence,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class AssetFit:
    asset_id: str
    source_id: str
    role: str
    score: float
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "score", _bounded(self.score, "score"))
        object.__setattr__(self, "reasons", tuple(self.reasons))
        if not self.asset_id:
            raise PlanError("asset_id must not be empty")
        if not self.source_id:
            raise PlanError(f"{self.asset_id}: source_id must not be empty")
        if not self.role:
            raise PlanError(f"{self.asset_id}: role must not be empty")
        if not self.reasons:
            raise PlanError(f"{self.asset_id}: at least one asset-fit reason is required")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AssetFit:
        return cls(
            asset_id=_required_str(data, "asset_id"),
            source_id=_required_str(data, "source_id"),
            role=_required_str(data, "role"),
            score=_required_float(data, "score"),
            reasons=_str_tuple(data.get("reasons", ()), "reasons"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "asset_id": self.asset_id,
            "source_id": self.source_id,
            "role": self.role,
            "score": self.score,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class PlannedBeat:
    id: str
    role: str
    token_start: int
    token_end: int
    word_start_id: str
    word_end_id: str
    quote: str
    route: str
    interpretation: str
    source_plan: str
    confidence: float
    reasons: tuple[str, ...]
    cue_ids: tuple[str, ...] = ()
    asset_fits: tuple[AssetFit, ...] = ()
    caption_style: str | None = None
    fallback: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "confidence", _bounded(self.confidence, "confidence"))
        object.__setattr__(self, "reasons", tuple(self.reasons))
        object.__setattr__(self, "cue_ids", tuple(self.cue_ids))
        object.__setattr__(self, "asset_fits", tuple(self.asset_fits))
        if self.token_start < 0:
            raise PlanError(f"{self.id}: token_start must be >= 0")
        if self.token_end <= self.token_start:
            raise PlanError(f"{self.id}: token_end must be after token_start")
        if not self.word_start_id:
            raise PlanError(f"{self.id}: word_start_id must not be empty")
        if not self.word_end_id:
            raise PlanError(f"{self.id}: word_end_id must not be empty")
        if not self.quote:
            raise PlanError(f"{self.id}: quote must not be empty")
        if not self.role:
            raise PlanError(f"{self.id}: role must not be empty")
        if not self.route:
            raise PlanError(f"{self.id}: route must not be empty")
        if not self.interpretation:
            raise PlanError(f"{self.id}: interpretation must not be empty")
        if not self.source_plan:
            raise PlanError(f"{self.id}: source_plan must not be empty")
        if not self.reasons:
            raise PlanError(f"{self.id}: at least one planning reason is required")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PlannedBeat:
        anchor = _mapping(data.get("anchor"), "anchor") if "anchor" in data else data
        return cls(
            id=_required_str(data, "id"),
            role=_required_str(data, "role"),
            token_start=_required_int(anchor, "token_start"),
            token_end=_required_int(anchor, "token_end"),
            word_start_id=_required_str(anchor, "word_start_id"),
            word_end_id=_required_str(anchor, "word_end_id"),
            quote=_required_str(anchor, "quote"),
            route=_required_str(data, "route"),
            interpretation=_required_str(data, "interpretation"),
            source_plan=_required_str(data, "source_plan"),
            confidence=_required_float(data, "confidence"),
            reasons=_str_tuple(data.get("reasons", ()), "reasons"),
            cue_ids=_str_tuple(data.get("cue_ids", ()), "cue_ids"),
            asset_fits=tuple(
                AssetFit.from_dict(_mapping(item, "asset fit"))
                for item in _sequence(data.get("asset_fits", ()), "asset_fits")
            ),
            caption_style=_optional_str(data, "caption_style"),
            fallback=_optional_str(data, "fallback"),
        )

    def to_beat_candidate(self, *, plan_id: str | None = None) -> BeatCandidate:
        source_ids = _unique_tuple(fit.source_id for fit in self.asset_fits)
        asset_ids = _unique_tuple(fit.asset_id for fit in self.asset_fits)
        return BeatCandidate(
            id=self.id,
            token_start=self.token_start,
            token_end=self.token_end,
            route=self.route,
            interpretation=self.interpretation,
            source_plan=self.source_plan,
            fallback=self.fallback,
            source_ids=source_ids,
            asset_ids=asset_ids,
            status="proposed",
            plan_id=plan_id,
            role=self.role,
            confidence=self.confidence,
            reasons=self.reasons,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "role": self.role,
            "anchor": {
                "token_start": self.token_start,
                "token_end": self.token_end,
                "word_start_id": self.word_start_id,
                "word_end_id": self.word_end_id,
                "quote": self.quote,
            },
            "route": self.route,
            "interpretation": self.interpretation,
            "source_plan": self.source_plan,
            "confidence": self.confidence,
            "reasons": list(self.reasons),
            "cue_ids": list(self.cue_ids),
            "asset_fits": [fit.to_dict() for fit in self.asset_fits],
            "caption_style": self.caption_style,
            "fallback": self.fallback,
        }


@dataclass(frozen=True)
class PlanSummary:
    asset_count: int
    cue_count: int
    beat_count: int
    average_confidence: float
    review_notes: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "average_confidence", _bounded(self.average_confidence, "average_confidence"))
        object.__setattr__(self, "review_notes", tuple(self.review_notes))
        if self.asset_count < 0:
            raise PlanError("asset_count must be >= 0")
        if self.cue_count < 0:
            raise PlanError("cue_count must be >= 0")
        if self.beat_count <= 0:
            raise PlanError("beat_count must be positive")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PlanSummary:
        return cls(
            asset_count=_required_int(data, "asset_count"),
            cue_count=_required_int(data, "cue_count"),
            beat_count=_required_int(data, "beat_count"),
            average_confidence=_required_float(data, "average_confidence"),
            review_notes=_str_tuple(data.get("review_notes", ()), "review_notes"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "asset_count": self.asset_count,
            "cue_count": self.cue_count,
            "beat_count": self.beat_count,
            "average_confidence": self.average_confidence,
            "review_notes": list(self.review_notes),
        }


@dataclass(frozen=True)
class KinoPlan:
    id: str
    edit_id: str
    transcript_id: str
    transcript_hash: str
    archetype_id: ArchetypeId
    aspect_ratio: str
    summary: PlanSummary
    cues: tuple[PlanCue, ...]
    beats: tuple[PlannedBeat, ...]
    version: int = KINO_PLAN_VERSION
    schema: str = KINO_PLAN_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "cues", tuple(self.cues))
        object.__setattr__(self, "beats", tuple(self.beats))
        validate_plan(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> KinoPlan:
        _reject_forbidden_timeline_keys(data)
        return cls(
            version=_required_int(data, "version") if "version" in data else KINO_PLAN_VERSION,
            schema=_required_str(data, "schema") if "schema" in data else KINO_PLAN_SCHEMA,
            id=_required_str(data, "id"),
            edit_id=_required_str(data, "edit_id"),
            transcript_id=_required_str(data, "transcript_id"),
            transcript_hash=_required_str(data, "transcript_hash"),
            archetype_id=_archetype_id(_required_str(data, "archetype_id")),
            aspect_ratio=_required_str(data, "aspect_ratio"),
            summary=PlanSummary.from_dict(_mapping(data.get("summary"), "summary")),
            cues=tuple(PlanCue.from_dict(_mapping(item, "cue")) for item in _sequence(data.get("cues", ()), "cues")),
            beats=tuple(
                PlannedBeat.from_dict(_mapping(item, "planned beat"))
                for item in _sequence(data.get("beats", ()), "beats")
            ),
        )

    @classmethod
    def from_json(cls, text: str) -> KinoPlan:
        return cls.from_dict(_mapping(json.loads(text), "KINO-PLAN document"))

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "schema": self.schema,
            "id": self.id,
            "edit_id": self.edit_id,
            "transcript_id": self.transcript_id,
            "transcript_hash": self.transcript_hash,
            "archetype_id": self.archetype_id,
            "aspect_ratio": self.aspect_ratio,
            "summary": self.summary.to_dict(),
            "cues": [cue.to_dict() for cue in self.cues],
            "beats": [beat.to_dict() for beat in self.beats],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"


def load_plan(path: str | Path) -> KinoPlan:
    return KinoPlan.from_json(Path(path).read_text())


def write_plan_json(plan: KinoPlan, path: str | Path) -> Path:
    validate_plan(plan)
    out = Path(path)
    out.write_text(plan.to_json())
    return out


def plan_edit(
    edit: KinoEdit,
    *,
    archetype_id: ArchetypeId,
    target_duration: float | None = None,
) -> KinoPlan:
    validate_edit(edit)
    definition = get_archetype_definition(archetype_id)
    duration = target_duration if target_duration is not None else _transcript_duration(edit.transcript.words)
    if duration <= 0:
        low, _ = definition.duration_range
        duration = low

    cues = _detect_cues(edit.transcript.words)
    beats = tuple(
        _planned_beat(index, template, edit, cues, duration)
        for index, template in enumerate(definition.beat_templates, start=1)
    )
    confidence = sum(beat.confidence for beat in beats) / len(beats)
    summary = PlanSummary(
        asset_count=len(edit.assets),
        cue_count=len(cues),
        beat_count=len(beats),
        average_confidence=round(confidence, 3),
        review_notes=_review_notes(edit, beats),
    )
    return KinoPlan(
        id=f"{edit.id}:{archetype_id}:plan",
        edit_id=edit.id,
        transcript_id=edit.transcript.id,
        transcript_hash=_transcript_hash(edit),
        archetype_id=archetype_id,
        aspect_ratio=definition.aspect_ratios[0],
        summary=summary,
        cues=cues,
        beats=beats,
    )


def apply_plan_to_edit(edit: KinoEdit, plan: KinoPlan) -> KinoEdit:
    validate_edit(edit)
    validate_plan(plan)
    if plan.edit_id != edit.id:
        raise PlanError(f"{plan.id}: plan edit_id does not match edit id: {edit.id}")
    if plan.transcript_id != edit.transcript.id:
        raise PlanError(f"{plan.id}: plan transcript_id does not match edit transcript id: {edit.transcript.id}")
    if plan.transcript_hash != _transcript_hash(edit):
        raise PlanError(f"{plan.id}: plan transcript_hash does not match edit transcript")

    existing_ids = {beat.id for beat in edit.beats}
    candidates = tuple(beat.to_beat_candidate(plan_id=plan.id) for beat in plan.beats if beat.id not in existing_ids)
    updated = replace(edit, beats=(*edit.beats, *candidates))
    validate_edit(updated)
    return updated


def validate_plan(plan: KinoPlan) -> None:
    if plan.version != KINO_PLAN_VERSION:
        raise PlanError(f"unsupported KINO-PLAN version: {plan.version}")
    if plan.schema != KINO_PLAN_SCHEMA:
        raise PlanError(f"unsupported KINO-PLAN schema: {plan.schema}")
    if not plan.id:
        raise PlanError("plan id must not be empty")
    if not plan.edit_id:
        raise PlanError(f"{plan.id}: edit_id must not be empty")
    if not plan.transcript_id:
        raise PlanError(f"{plan.id}: transcript_id must not be empty")
    if not plan.transcript_hash.startswith("sha256:"):
        raise PlanError(f"{plan.id}: transcript_hash must be a sha256 digest")
    if not plan.aspect_ratio:
        raise PlanError(f"{plan.id}: aspect_ratio must not be empty")
    if plan.summary.beat_count != len(plan.beats):
        raise PlanError(f"{plan.id}: summary beat_count does not match beats")
    if plan.summary.cue_count != len(plan.cues):
        raise PlanError(f"{plan.id}: summary cue_count does not match cues")

    cue_ids = _unique_ids((cue.id for cue in plan.cues), "cue")
    beat_ids = _unique_ids((beat.id for beat in plan.beats), "planned beat")
    if len(beat_ids) != len(plan.beats):
        raise PlanError(f"{plan.id}: duplicate planned beat id")
    for beat in plan.beats:
        for cue_id in beat.cue_ids:
            if cue_id not in cue_ids:
                raise PlanError(f"{beat.id}: unknown cue id: {cue_id}")


def _detect_cues(words: tuple[WordToken, ...]) -> tuple[PlanCue, ...]:
    if not words:
        return ()

    cues: list[PlanCue] = []
    total = len(words)
    windows = (
        ("hook", 0, max(1, min(total, round(total * 0.16))), "opening words carry the retention hook"),
        (
            "problem",
            max(0, round(total * 0.16)),
            max(1, round(total * 0.36)),
            "early-middle words usually frame the viewer problem",
        ),
        (
            "proof",
            max(0, round(total * 0.36)),
            max(1, round(total * 0.76)),
            "middle section needs visual evidence or demo support",
        ),
        ("cta", max(0, round(total * 0.76)), total, "closing words should resolve or ask for action"),
    )
    for index, (kind, start, end, reason) in enumerate(windows, start=1):
        start = min(start, total - 1)
        end = min(max(end, start + 1), total)
        text = _line(words[start:end])
        cue_kind = _infer_cue_kind(kind, text)
        cues.append(
            PlanCue(
                id=f"cue:{index:02d}:{cue_kind}",
                kind=cue_kind,
                token_start=start,
                token_end=end,
                text=text,
                confidence=_cue_confidence(cue_kind, text, index),
                reasons=(reason, *_keyword_reasons(cue_kind, text)),
            )
        )
    return tuple(cues)


def _planned_beat(
    index: int,
    template: BeatTemplate,
    edit: KinoEdit,
    cues: tuple[PlanCue, ...],
    target_duration: float,
) -> PlannedBeat:
    words = edit.transcript.words
    token_start, token_end = _template_token_range(template, words, target_duration)
    text = _line(words[token_start:token_end])
    matched_cues = _matching_plan_cues(template, cues)
    asset_fits = _asset_fits(template, edit.assets, edit.sources)
    route = _route_for_template(template, asset_fits)
    confidence = _beat_confidence(template, matched_cues, asset_fits)
    reasons = (
        f"Uses archetype section '{template.role}' from template '{template.id}'.",
        f"Supports transcript range {token_start}:{token_end}: {text}",
        template.intent,
    )
    if matched_cues:
        reasons = (*reasons, f"Matched cue(s): {', '.join(cue.id for cue in matched_cues)}.")
    if asset_fits:
        reasons = (*reasons, f"Best asset fit: {asset_fits[0].asset_id} ({asset_fits[0].score:.2f}).")
    else:
        reasons = (*reasons, "No asset was available, so this beat remains a sourcing/generation request.")

    return PlannedBeat(
        id=f"planbeat:{index:02d}:{_slug(template.role)}",
        role=template.role,
        token_start=token_start,
        token_end=token_end,
        word_start_id=words[token_start].id,
        word_end_id=words[token_end - 1].id,
        quote=text,
        route=route,
        interpretation=f"{template.intent} Transcript: {text}",
        source_plan=_source_plan_for_template(template, asset_fits),
        confidence=confidence,
        reasons=reasons,
        cue_ids=tuple(cue.id for cue in matched_cues),
        asset_fits=asset_fits,
        caption_style=template.caption_style,
        fallback="Use generated brand-safe visual language if no approved source exists.",
    )


def _template_token_range(
    template: BeatTemplate,
    words: tuple[WordToken, ...],
    target_duration: float,
) -> tuple[int, int]:
    if not words:
        raise PlanError("cannot plan beats without transcript words")
    if target_duration <= 0:
        return _ratio_token_range(template, len(words))

    start_time = target_duration * template.start_ratio
    end_time = target_duration * template.end_ratio
    overlapping = [
        index for index, word in enumerate(words) if word.end > start_time and word.start < end_time
    ]
    if overlapping:
        return overlapping[0], overlapping[-1] + 1
    return _ratio_token_range(template, len(words))


def _ratio_token_range(template: BeatTemplate, token_count: int) -> tuple[int, int]:
    start = min(max(0, int(token_count * template.start_ratio)), token_count - 1)
    end = min(max(start + 1, round(token_count * template.end_ratio)), token_count)
    return start, end


def _matching_plan_cues(template: BeatTemplate, cues: tuple[PlanCue, ...]) -> tuple[PlanCue, ...]:
    preferred = set(template.preferred_cue_kinds)
    if not preferred:
        return ()
    matched = [cue for cue in cues if cue.kind in preferred]
    return tuple(sorted(matched, key=lambda cue: (-cue.confidence, cue.token_start, cue.id))[:2])


def _asset_fits(
    template: BeatTemplate,
    assets: tuple[AssetCandidate, ...],
    sources: tuple[SourceReceipt, ...],
) -> tuple[AssetFit, ...]:
    sources_by_id = {source.id: source for source in sources}
    scored = [_score_asset(template, asset, sources_by_id.get(asset.source_id)) for asset in assets]
    scored = [fit for fit in scored if fit.score >= 0.34]
    return tuple(sorted(scored, key=lambda fit: (-fit.score, fit.asset_id))[:3])


def _score_asset(template: BeatTemplate, asset: AssetCandidate, source: SourceReceipt | None) -> AssetFit:
    haystack = " ".join(
        part
        for part in (
            asset.id,
            asset.kind,
            asset.uri,
            asset.credit or "",
            asset.notes or "",
            source.title if source else "",
            source.notes if source else "",
            template.role,
            template.intent,
            template.visual_plan,
        )
        if part
    ).lower()
    role = _asset_role(asset, haystack)
    score = 0.25
    reasons = [f"asset is available as {asset.kind}"]

    if asset.score is not None:
        score += asset.score * 0.24
        reasons.append(f"asset candidate score contributes {asset.score:.2f}")
    if asset.kind in ("video", "still", "image", "web", "document"):
        score += 0.12
        reasons.append("asset kind can support a visual beat")
    if role in _preferred_asset_roles(template):
        score += 0.28
        reasons.append(f"asset role '{role}' matches beat role '{template.role}'")
    if _contains_any(haystack, ("proof", "receipt", "result", "before", "after")) and _role_needs_proof(template.role):
        score += 0.12
        reasons.append("proof language supports this section")
    if _contains_any(haystack, ("ui", "screen", "demo", "walkthrough", "product")) and _role_needs_demo(template.role):
        score += 0.12
        reasons.append("demo/product language supports this section")
    if asset.width and asset.height:
        score += 0.04
        reasons.append("asset has dimensions for layout planning")

    return AssetFit(
        asset_id=asset.id,
        source_id=asset.source_id,
        role=role,
        score=round(min(score, 1.0), 3),
        reasons=tuple(reasons),
    )


def _route_for_template(template: BeatTemplate, asset_fits: tuple[AssetFit, ...]) -> str:
    role = template.role.lower()
    if any(word in role for word in ("proof", "demo", "walkthrough", "product", "cta")):
        return "asset-match" if asset_fits else "source-request"
    if "hook" in role:
        return "hook"
    if "problem" in role:
        return "concept"
    return "story-support"


def _source_plan_for_template(template: BeatTemplate, asset_fits: tuple[AssetFit, ...]) -> str:
    if asset_fits:
        best = asset_fits[0]
        return f"Use candidate asset {best.asset_id} as the first option; keep alternates ranked by fit score."
    return f"Source or generate a visual for: {template.visual_plan}"


def _beat_confidence(
    template: BeatTemplate,
    cues: tuple[PlanCue, ...],
    asset_fits: tuple[AssetFit, ...],
) -> float:
    score = 0.42
    if cues:
        score += min(sum(cue.confidence for cue in cues) / len(cues), 1.0) * 0.24
    if asset_fits:
        score += asset_fits[0].score * 0.24
    if template.caption_style:
        score += 0.04
    return round(min(score, 0.98), 3)


def _review_notes(edit: KinoEdit, beats: tuple[PlannedBeat, ...]) -> tuple[str, ...]:
    notes: list[str] = []
    if not edit.assets:
        notes.append("No assets are attached, so planned beats require sourcing before approval.")
    if any(not beat.asset_fits for beat in beats):
        notes.append("Some beats have no matching asset and should be sourced or generated before render.")
    low_confidence = [beat.id for beat in beats if beat.confidence < 0.62]
    if low_confidence:
        notes.append(f"Review low-confidence beats: {', '.join(low_confidence)}.")
    return tuple(notes)


def _transcript_duration(words: tuple[WordToken, ...]) -> float:
    if not words:
        return 0.0
    return max(word.end for word in words)


def _transcript_hash(edit: KinoEdit) -> str:
    payload = json.dumps(edit.transcript.to_dict(), sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{sha256(payload).hexdigest()}"


def _infer_cue_kind(default: str, text: str) -> PlanCueKind:
    lowered = text.lower()
    if _contains_any(lowered, ("follow", "subscribe", "sign up", "try", "download", "buy", "visit")):
        return "cta"
    if _contains_any(lowered, ("proof", "result", "receipt", "evidence", "show", "demo", "watch")):
        return "proof"
    if _contains_any(lowered, ("problem", "mistake", "wrong", "cost", "broken", "hard", "failed")):
        return "problem"
    if _contains_any(lowered, ("new", "better", "built", "we made", "this is")):
        return "claim"
    return _cue_kind(default)


def _cue_confidence(kind: PlanCueKind, text: str, index: int) -> float:
    score = 0.58
    if _keyword_reasons(kind, text):
        score += 0.22
    if kind == "hook" and index == 1:
        score += 0.1
    if kind == "cta" and index == 4:
        score += 0.1
    return round(min(score, 0.95), 3)


def _keyword_reasons(kind: PlanCueKind, text: str) -> tuple[str, ...]:
    lowered = text.lower()
    reasons: list[str] = []
    if kind == "cta" and _contains_any(lowered, ("follow", "subscribe", "sign up", "try", "download", "visit")):
        reasons.append("CTA language appears in the transcript.")
    if kind == "proof" and _contains_any(lowered, ("proof", "result", "receipt", "evidence", "show", "demo")):
        reasons.append("Proof/demo language appears in the transcript.")
    if kind == "problem" and _contains_any(lowered, ("problem", "mistake", "wrong", "cost", "broken", "hard")):
        reasons.append("Problem language appears in the transcript.")
    if kind == "claim" and _contains_any(lowered, ("new", "better", "built", "made")):
        reasons.append("Claim language appears in the transcript.")
    return tuple(reasons)


def _asset_role(asset: AssetCandidate, haystack: str) -> str:
    if asset.kind == "web" or _contains_any(haystack, ("receipt", "source", "article", "page")):
        return "receipt"
    if _contains_any(haystack, ("ui", "screen", "app", "product", "dashboard")):
        return "product-ui"
    if _contains_any(haystack, ("demo", "walkthrough", "recording")):
        return "demo"
    if _contains_any(haystack, ("proof", "result", "before", "after", "evidence")):
        return "proof"
    if _contains_any(haystack, ("face", "founder", "talking")):
        return "talking-head"
    if asset.kind == "video":
        return "motion"
    return "visual"


def _preferred_asset_roles(template: BeatTemplate) -> set[str]:
    role = template.role.lower()
    if _role_needs_demo(role):
        return {"product-ui", "demo", "motion", "receipt"}
    if _role_needs_proof(role):
        return {"proof", "receipt", "product-ui", "demo", "motion"}
    if "hook" in role:
        return {"motion", "talking-head", "product-ui", "proof"}
    if "cta" in role:
        return {"product-ui", "receipt", "visual", "motion"}
    return {"visual", "talking-head", "product-ui", "motion"}


def _role_needs_demo(role: str) -> bool:
    return any(word in role.lower() for word in ("demo", "walkthrough", "product", "claim"))


def _role_needs_proof(role: str) -> bool:
    return any(word in role.lower() for word in ("proof", "result", "cta", "hook"))


def _line(words: tuple[WordToken, ...]) -> str:
    return " ".join(word.text for word in words)


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "beat"


def _unique_tuple(values: Any) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return tuple(out)


def _unique_ids(values: Any, label: str) -> set[str]:
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str) or value == "":
            raise PlanError(f"{label} id must be a non-empty string")
        if value in seen:
            raise PlanError(f"duplicate {label} id: {value}")
        seen.add(value)
    return seen


def _reject_forbidden_timeline_keys(value: object, path: str = "$") -> None:
    forbidden = {"start", "end", "duration", "target_duration", "start_ratio", "end_ratio", "time_range"}
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in forbidden:
                raise PlanError(f"{path}.{key}: KINO-PLAN must not expose timeline timing fields")
            _reject_forbidden_timeline_keys(item, f"{path}.{key}")
    elif isinstance(value, list | tuple):
        for index, item in enumerate(value):
            _reject_forbidden_timeline_keys(item, f"{path}[{index}]")


def _archetype_id(value: str) -> ArchetypeId:
    if value not in ("social-short", "founder-product-explainer"):
        raise PlanError(f"unsupported archetype id: {value}")
    return value  # type: ignore[return-value]


def _cue_kind(value: str) -> PlanCueKind:
    if value not in ("hook", "problem", "claim", "proof", "demo", "cta", "transition", "filler", "other"):
        raise PlanError(f"unsupported cue kind: {value}")
    return value  # type: ignore[return-value]


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PlanError(f"{label} must be an object")
    return value


def _sequence(value: object, key: str) -> tuple[object, ...]:
    if not isinstance(value, list | tuple):
        raise PlanError(f"{key} must be a list")
    return tuple(value)


def _required_str(data: Mapping[str, Any], key: str) -> str:
    if key not in data:
        raise PlanError(f"missing required key: {key}")
    value = data[key]
    if not isinstance(value, str):
        raise PlanError(f"{key} must be a string")
    return value


def _optional_str(data: Mapping[str, Any], key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise PlanError(f"{key} must be a string")
    return value


def _required_int(data: Mapping[str, Any], key: str) -> int:
    if key not in data:
        raise PlanError(f"missing required key: {key}")
    value = data[key]
    if not isinstance(value, int) or isinstance(value, bool):
        raise PlanError(f"{key} must be an integer")
    return value


def _required_float(data: Mapping[str, Any], key: str) -> float:
    if key not in data:
        raise PlanError(f"missing required key: {key}")
    return _number(data[key], key)


def _positive_float(value: object, key: str) -> float:
    number = _number(value, key)
    if number <= 0:
        raise PlanError(f"{key} must be positive")
    return number


def _number(value: object, key: str) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise PlanError(f"{key} must be a number")
    return float(value)


def _bounded(value: float, key: str) -> float:
    if not 0 <= value <= 1:
        raise PlanError(f"{key} must be between 0 and 1")
    return value


def _str_tuple(value: object, key: str) -> tuple[str, ...]:
    items = _sequence(value, key)
    for item in items:
        if not isinstance(item, str):
            raise PlanError(f"{key} values must be strings")
    return tuple(items)


__all__ = [
    "AssetFit",
    "KINO_PLAN_SCHEMA",
    "KINO_PLAN_VERSION",
    "KinoPlan",
    "PlanCue",
    "PlanCueKind",
    "PlanError",
    "PlanSummary",
    "PlannedBeat",
    "apply_plan_to_edit",
    "load_plan",
    "plan_edit",
    "validate_plan",
    "write_plan_json",
]

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

from .captions import KinoCaptions, load_captions
from .plan import KinoPlan, load_plan

KINO_EVAL_VERSION = 1
KINO_EVAL_SCHEMA = "kino.eval.v1"

EvalStatus = Literal["pass", "manual-review-required", "warning", "fail"]
EvalDecision = Literal["approve-release", "approve-with-review-items", "revise-before-handoff", "reject-replan"]

_STATUS_SCORES: dict[EvalStatus, float] = {
    "pass": 1.0,
    "manual-review-required": 0.82,
    "warning": 0.65,
    "fail": 0.0,
}


class EvalError(ValueError):
    pass


@dataclass(frozen=True)
class EvalCheck:
    name: str
    category: str
    status: EvalStatus
    score: float
    message: str
    recommendation: str | None = None
    artifact: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", _status(self.status))
        object.__setattr__(self, "score", _bounded(self.score, "score"))
        if not self.name:
            raise EvalError("eval check name must not be empty")
        if not self.category:
            raise EvalError(f"{self.name}: category must not be empty")
        if not self.message:
            raise EvalError(f"{self.name}: message must not be empty")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> EvalCheck:
        return cls(
            name=_required_str(data, "name"),
            category=_required_str(data, "category"),
            status=_status(_required_str(data, "status")),
            score=_required_float(data, "score"),
            message=_required_str(data, "message"),
            recommendation=_optional_str(data, "recommendation"),
            artifact=_optional_str(data, "artifact"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "category": self.category,
            "status": self.status,
            "score": self.score,
            "message": self.message,
            "recommendation": self.recommendation,
            "artifact": self.artifact,
        }


@dataclass(frozen=True)
class EvalArtifact:
    kind: str
    path: str
    status: EvalStatus
    score: float
    summary: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", _status(self.status))
        object.__setattr__(self, "score", _bounded(self.score, "score"))
        if not self.kind:
            raise EvalError("artifact kind must not be empty")
        if not self.path:
            raise EvalError(f"{self.kind}: artifact path must not be empty")
        if not self.summary:
            raise EvalError(f"{self.kind}: artifact summary must not be empty")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> EvalArtifact:
        return cls(
            kind=_required_str(data, "kind"),
            path=_required_str(data, "path"),
            status=_status(_required_str(data, "status")),
            score=_required_float(data, "score"),
            summary=_required_str(data, "summary"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "path": self.path,
            "status": self.status,
            "score": self.score,
            "summary": self.summary,
        }


@dataclass(frozen=True)
class KinoEval:
    id: str
    checks: tuple[EvalCheck, ...]
    artifacts: tuple[EvalArtifact, ...] = ()
    overall: EvalStatus = "pass"
    score: float = 1.0
    decision: EvalDecision = "approve-release"
    recommendations: tuple[str, ...] = ()
    version: int = KINO_EVAL_VERSION
    schema: str = KINO_EVAL_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "checks", tuple(self.checks))
        object.__setattr__(self, "artifacts", tuple(self.artifacts))
        object.__setattr__(self, "recommendations", tuple(self.recommendations))
        validate_eval(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> KinoEval:
        return cls(
            version=_required_int(data, "version") if "version" in data else KINO_EVAL_VERSION,
            schema=_required_str(data, "schema") if "schema" in data else KINO_EVAL_SCHEMA,
            id=_required_str(data, "id"),
            checks=tuple(EvalCheck.from_dict(_mapping(item, "eval check")) for item in _sequence(data.get("checks", ()), "checks")),
            artifacts=tuple(
                EvalArtifact.from_dict(_mapping(item, "eval artifact"))
                for item in _sequence(data.get("artifacts", ()), "artifacts")
            ),
            overall=_status(_required_str(data, "overall")),
            score=_required_float(data, "score"),
            decision=_decision(_required_str(data, "decision")),
            recommendations=_str_tuple(data.get("recommendations", ()), "recommendations"),
        )

    @classmethod
    def from_json(cls, text: str) -> KinoEval:
        return cls.from_dict(_mapping(json.loads(text), "KINO-EVAL document"))

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "schema": self.schema,
            "id": self.id,
            "overall": self.overall,
            "score": self.score,
            "decision": self.decision,
            "recommendations": list(self.recommendations),
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "checks": [check.to_dict() for check in self.checks],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"


def evaluate_artifacts(
    *,
    eval_id: str = "kino-eval",
    plan_path: str | Path | None = None,
    captions_path: str | Path | None = None,
    review_path: str | Path | None = None,
    frame_qc_path: str | Path | None = None,
    audio_qc_path: str | Path | None = None,
    export_validation_path: str | Path | None = None,
) -> KinoEval:
    checks: list[EvalCheck] = []
    artifacts: list[EvalArtifact] = []

    if plan_path is not None:
        path = Path(plan_path)
        plan = load_plan(path)
        plan_checks = evaluate_plan(plan, artifact=str(path))
        checks.extend(plan_checks)
        artifacts.append(_artifact("plan", path, plan_checks, f"{len(plan.beats)} planned beat(s)"))

    if captions_path is not None:
        path = Path(captions_path)
        captions = load_captions(path)
        caption_checks = evaluate_captions(captions, artifact=str(path))
        checks.extend(caption_checks)
        artifacts.append(_artifact("captions", path, caption_checks, f"{len(captions.segments)} caption segment(s)"))

    for kind, path_like in (
        ("media-review", review_path),
        ("frame-qc", frame_qc_path),
        ("audio-qc", audio_qc_path),
        ("export-validation", export_validation_path),
    ):
        if path_like is None:
            continue
        path = Path(path_like)
        report = _load_json(path)
        report_checks = evaluate_status_report(kind, report, artifact=str(path))
        checks.extend(report_checks)
        artifacts.append(_artifact(kind, path, report_checks, _report_summary(kind, report)))

    if not checks:
        raise EvalError("at least one artifact is required for evaluation")

    overall = _overall(checks)
    score = round(sum(check.score for check in checks) / len(checks), 3)
    recommendations = tuple(dict.fromkeys(check.recommendation for check in checks if check.recommendation))
    return KinoEval(
        id=eval_id,
        checks=tuple(checks),
        artifacts=tuple(artifacts),
        overall=overall,
        score=score,
        decision=_decision_for(overall, score),
        recommendations=recommendations,
    )


def evaluate_plan(plan: KinoPlan, *, artifact: str | None = None) -> tuple[EvalCheck, ...]:
    checks: list[EvalCheck] = []
    low_confidence = [beat.id for beat in plan.beats if beat.confidence < 0.62]
    missing_assets = [beat.id for beat in plan.beats if not beat.asset_fits]
    average_confidence = plan.summary.average_confidence

    checks.append(
        EvalCheck(
            name="plan_average_confidence",
            category="plan",
            status="pass" if average_confidence >= 0.7 else "warning",
            score=_confidence_score(average_confidence),
            message=f"Plan average confidence is {average_confidence:.2f}.",
            recommendation="Review low-confidence planned beats before sourcing." if average_confidence < 0.7 else None,
            artifact=artifact,
        )
    )
    checks.append(
        EvalCheck(
            name="plan_asset_coverage",
            category="plan",
            status="pass" if not missing_assets else "warning",
            score=round((len(plan.beats) - len(missing_assets)) / len(plan.beats), 3),
            message=(
                "Every planned beat has at least one asset fit."
                if not missing_assets
                else f"{len(missing_assets)} planned beat(s) need sourcing: {', '.join(missing_assets)}."
            ),
            recommendation="Run sourcing or generate assets for beats with no asset_fits." if missing_assets else None,
            artifact=artifact,
        )
    )
    checks.append(
        EvalCheck(
            name="plan_low_confidence_beats",
            category="plan",
            status="pass" if not low_confidence else "warning",
            score=round((len(plan.beats) - len(low_confidence)) / len(plan.beats), 3),
            message=(
                "No low-confidence planned beats."
                if not low_confidence
                else f"Low-confidence beat(s): {', '.join(low_confidence)}."
            ),
            recommendation="Revise or replace low-confidence beat plans." if low_confidence else None,
            artifact=artifact,
        )
    )
    return tuple(checks)


def evaluate_captions(captions: KinoCaptions, *, artifact: str | None = None) -> tuple[EvalCheck, ...]:
    low_confidence = [segment.id for segment in captions.segments if segment.confidence < 0.7]
    long_segments = [segment.id for segment in captions.segments if segment.duration > 2.8]
    density = len(captions.segments)
    average_confidence = sum(segment.confidence for segment in captions.segments) / len(captions.segments)

    return (
        EvalCheck(
            name="caption_average_confidence",
            category="captions",
            status="pass" if average_confidence >= 0.72 else "warning",
            score=_confidence_score(average_confidence),
            message=f"Caption average confidence is {average_confidence:.2f}.",
            recommendation="Review transcript alignment for low-confidence captions." if average_confidence < 0.72 else None,
            artifact=artifact,
        ),
        EvalCheck(
            name="caption_low_confidence_segments",
            category="captions",
            status="pass" if not low_confidence else "warning",
            score=round((len(captions.segments) - len(low_confidence)) / len(captions.segments), 3),
            message=(
                "No low-confidence caption segments."
                if not low_confidence
                else f"Low-confidence caption segment(s): {', '.join(low_confidence)}."
            ),
            recommendation="Regenerate or manually review low-confidence caption segments." if low_confidence else None,
            artifact=artifact,
        ),
        EvalCheck(
            name="caption_reading_pace",
            category="captions",
            status="pass" if not long_segments else "warning",
            score=round((density - len(long_segments)) / density, 3),
            message=(
                "Caption segment durations are within the preferred reading window."
                if not long_segments
                else f"Long caption segment(s): {', '.join(long_segments)}."
            ),
            recommendation="Run a caption tightening pass for long segments." if long_segments else None,
            artifact=artifact,
        ),
    )


def evaluate_status_report(kind: str, report: Mapping[str, Any], *, artifact: str | None = None) -> tuple[EvalCheck, ...]:
    overall = _status(str(report.get("overall", "fail")))
    checks = _sequence(report.get("checks", ()), "checks")
    fail_count = _count_status(checks, "fail")
    warning_count = _count_status(checks, "warning") + _count_status(checks, "manual-review-required")
    total = max(len(checks), 1)
    score = round(sum(_STATUS_SCORES[_status(str(_mapping(check, "check").get("status", "fail")))] for check in checks) / total, 3)
    if not checks:
        score = _STATUS_SCORES[overall]

    return (
        EvalCheck(
            name=f"{kind}_overall",
            category=kind,
            status=overall,
            score=score,
            message=f"{kind} report overall is {overall}.",
            recommendation=_status_recommendation(kind, overall),
            artifact=artifact,
        ),
        EvalCheck(
            name=f"{kind}_issue_count",
            category=kind,
            status="pass" if fail_count == 0 and warning_count == 0 else ("fail" if fail_count else "warning"),
            score=round(max(total - fail_count - warning_count * 0.5, 0) / total, 3),
            message=f"{kind} report has {fail_count} fail(s) and {warning_count} warning/manual-review item(s).",
            recommendation=_issue_recommendation(kind, fail_count, warning_count),
            artifact=artifact,
        ),
    )


def load_eval(path: str | Path) -> KinoEval:
    return KinoEval.from_json(Path(path).read_text())


def write_eval_json(report: KinoEval, path: str | Path) -> Path:
    validate_eval(report)
    out = Path(path)
    out.write_text(report.to_json())
    return out


def write_eval_markdown(report: KinoEval, path: str | Path) -> Path:
    validate_eval(report)
    out = Path(path)
    lines = [
        "# Kino Evaluation Report",
        "",
        f"Overall: `{report.overall}`",
        f"Score: `{report.score:.3f}`",
        f"Decision: `{report.decision}`",
        "",
        "## Recommendations",
        "",
    ]
    if report.recommendations:
        lines.extend(f"- {recommendation}" for recommendation in report.recommendations)
    else:
        lines.append("- No blocking recommendations.")
    lines.extend(
        [
            "",
            "## Checks",
            "",
            "| Check | Category | Status | Score | Message | Recommendation |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for check in report.checks:
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(check.name),
                    _md_cell(check.category),
                    f"`{check.status}`",
                    f"`{check.score:.3f}`",
                    _md_cell(check.message),
                    _md_cell(check.recommendation or ""),
                ]
            )
            + " |"
        )
    out.write_text("\n".join(lines) + "\n")
    return out


def validate_eval(report: KinoEval) -> None:
    if report.version != KINO_EVAL_VERSION:
        raise EvalError(f"unsupported KINO-EVAL version: {report.version}")
    if report.schema != KINO_EVAL_SCHEMA:
        raise EvalError(f"unsupported KINO-EVAL schema: {report.schema}")
    if not report.id:
        raise EvalError("eval id must not be empty")
    if not report.checks:
        raise EvalError(f"{report.id}: at least one eval check is required")
    if report.overall != _overall(report.checks):
        raise EvalError(f"{report.id}: overall does not match checks")
    expected_score = round(sum(check.score for check in report.checks) / len(report.checks), 3)
    if abs(report.score - expected_score) > 0.001:
        raise EvalError(f"{report.id}: score does not match checks")
    if report.decision != _decision_for(report.overall, report.score):
        raise EvalError(f"{report.id}: decision does not match overall/score")


def _artifact(kind: str, path: Path, checks: tuple[EvalCheck, ...], summary: str) -> EvalArtifact:
    return EvalArtifact(
        kind=kind,
        path=str(path),
        status=_overall(checks),
        score=round(sum(check.score for check in checks) / len(checks), 3),
        summary=summary,
    )


def _overall(checks: tuple[EvalCheck, ...] | list[EvalCheck]) -> EvalStatus:
    statuses = {check.status for check in checks}
    if "fail" in statuses:
        return "fail"
    if "warning" in statuses:
        return "warning"
    if "manual-review-required" in statuses:
        return "manual-review-required"
    return "pass"


def _decision_for(overall: EvalStatus, score: float) -> EvalDecision:
    if overall == "fail" or score < 0.7:
        return "reject-replan"
    if overall == "warning" or score < 0.8:
        return "revise-before-handoff"
    if overall == "manual-review-required" or score < 0.9:
        return "approve-with-review-items"
    return "approve-release"


def _confidence_score(value: float) -> float:
    return round(max(0.0, min(value, 1.0)), 3)


def _count_status(checks: tuple[object, ...], status: EvalStatus) -> int:
    count = 0
    for check in checks:
        check_data = _mapping(check, "check")
        if _status(str(check_data.get("status", "fail"))) == status:
            count += 1
    return count


def _status_recommendation(kind: str, overall: EvalStatus) -> str | None:
    if overall == "pass":
        return None
    if kind == "frame-qc":
        return "Inspect verification frames/contact sheet and rerender rejected frames."
    if kind == "audio-qc":
        return "Normalize audio or fix clipping/silence before export."
    if kind == "media-review":
        return "Fix direct media review issues before handoff."
    if kind == "export-validation":
        return "Re-export with the target preset and rerun validate-export."
    return f"Resolve {kind} report warnings before delivery."


def _issue_recommendation(kind: str, fail_count: int, warning_count: int) -> str | None:
    if fail_count:
        return f"Fix {fail_count} failing {kind} check(s) before delivery."
    if warning_count:
        return f"Review {warning_count} {kind} warning/manual-review item(s)."
    return None


def _report_summary(kind: str, report: Mapping[str, Any]) -> str:
    checks = _sequence(report.get("checks", ()), "checks")
    return f"{kind} overall {report.get('overall', 'unknown')} with {len(checks)} check(s)"


def _load_json(path: Path) -> Mapping[str, Any]:
    return _mapping(json.loads(path.read_text()), str(path))


def _status(value: str) -> EvalStatus:
    if value not in ("pass", "manual-review-required", "warning", "fail"):
        raise EvalError(f"unsupported eval status: {value}")
    return value  # type: ignore[return-value]


def _decision(value: str) -> EvalDecision:
    if value not in ("approve-release", "approve-with-review-items", "revise-before-handoff", "reject-replan"):
        raise EvalError(f"unsupported eval decision: {value}")
    return value  # type: ignore[return-value]


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise EvalError(f"{label} must be an object")
    return value


def _sequence(value: object, key: str) -> tuple[object, ...]:
    if not isinstance(value, list | tuple):
        raise EvalError(f"{key} must be a list")
    return tuple(value)


def _required_str(data: Mapping[str, Any], key: str) -> str:
    if key not in data:
        raise EvalError(f"missing required key: {key}")
    value = data[key]
    if not isinstance(value, str):
        raise EvalError(f"{key} must be a string")
    return value


def _optional_str(data: Mapping[str, Any], key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise EvalError(f"{key} must be a string")
    return value


def _required_int(data: Mapping[str, Any], key: str) -> int:
    if key not in data:
        raise EvalError(f"missing required key: {key}")
    value = data[key]
    if not isinstance(value, int) or isinstance(value, bool):
        raise EvalError(f"{key} must be an integer")
    return value


def _required_float(data: Mapping[str, Any], key: str) -> float:
    if key not in data:
        raise EvalError(f"missing required key: {key}")
    value = data[key]
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise EvalError(f"{key} must be a number")
    return float(value)


def _bounded(value: float, key: str) -> float:
    if not 0 <= value <= 1:
        raise EvalError(f"{key} must be between 0 and 1")
    return value


def _str_tuple(value: object, key: str) -> tuple[str, ...]:
    items = _sequence(value, key)
    for item in items:
        if not isinstance(item, str):
            raise EvalError(f"{key} values must be strings")
    return tuple(items)


def _md_cell(value: object) -> str:
    return str(value).replace("|", r"\|").replace("\n", "<br>")


__all__ = [
    "EvalArtifact",
    "EvalCheck",
    "EvalError",
    "EvalDecision",
    "EvalStatus",
    "KINO_EVAL_SCHEMA",
    "KINO_EVAL_VERSION",
    "KinoEval",
    "evaluate_artifacts",
    "evaluate_captions",
    "evaluate_plan",
    "evaluate_status_report",
    "load_eval",
    "validate_eval",
    "write_eval_json",
    "write_eval_markdown",
]

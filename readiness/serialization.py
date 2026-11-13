"""JSON persistence for M7 readiness reports."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
import json
from pathlib import Path
from typing import Any

from readiness.models import (
    AssessmentFinding, BackendStatus, ClarificationItem, FitLevel, Paradigm,
    ParadigmAssessment, QuestionPriority, ReadinessReport, ReadinessStatus,
)


class ReadinessSerializationError(ValueError):
    """Raised when a readiness report is invalid or incompatible JSON."""


def _primitive(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {item.name: _primitive(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, tuple):
        return [_primitive(item) for item in value]
    return value


def report_to_dict(report: ReadinessReport) -> dict[str, Any]:
    if not isinstance(report, ReadinessReport):
        raise TypeError("report must be a ReadinessReport")
    return _primitive(report)


def dumps_report(report: ReadinessReport, *, indent: int = 2) -> str:
    return json.dumps(report_to_dict(report), ensure_ascii=False, indent=indent, allow_nan=False)


def _object(raw: Any, cls, path: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ReadinessSerializationError(f"{path} must be a JSON object")
    allowed = {item.name for item in fields(cls)}
    unknown = set(raw) - allowed
    missing = allowed - set(raw)
    if unknown:
        raise ReadinessSerializationError(f"{path} contains unknown field(s): {', '.join(sorted(unknown))}")
    if missing:
        raise ReadinessSerializationError(f"{path} is missing field(s): {', '.join(sorted(missing))}")
    return raw


def _string_tuple(value: Any, path: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ReadinessSerializationError(f"{path} must be an array of strings")
    return tuple(value)


def _finding(raw: Any, path: str) -> AssessmentFinding:
    raw = _object(raw, AssessmentFinding, path)
    try:
        return AssessmentFinding(
            code=raw["code"], title=raw["title"], explanation=raw["explanation"],
            element_ids=_string_tuple(raw["element_ids"], f"{path}.element_ids"),
        )
    except (TypeError, ValueError) as error:
        raise ReadinessSerializationError(f"{path} is invalid: {error}") from error


def _clarification(raw: Any, path: str) -> ClarificationItem:
    raw = _object(raw, ClarificationItem, path)
    try:
        return ClarificationItem(
            id=raw["id"], question=raw["question"], reason=raw["reason"],
            priority=QuestionPriority(raw["priority"]),
            related_element_ids=_string_tuple(raw["related_element_ids"], f"{path}.related_element_ids"),
            blocking=raw["blocking"],
        )
    except (TypeError, ValueError) as error:
        raise ReadinessSerializationError(f"{path} is invalid: {error}") from error


def _paradigm_assessment(raw: Any, path: str) -> ParadigmAssessment:
    raw = _object(raw, ParadigmAssessment, path)
    if not isinstance(raw["supporting_findings"], list) or not isinstance(raw["limitations"], list):
        raise ReadinessSerializationError(f"{path} findings and limitations must be arrays")
    try:
        return ParadigmAssessment(
            paradigm=Paradigm(raw["paradigm"]), fit=FitLevel(raw["fit"]),
            backend_status=BackendStatus(raw["backend_status"]),
            supporting_findings=tuple(_finding(item, f"{path}.supporting_findings[{index}]") for index, item in enumerate(raw["supporting_findings"])),
            limitations=tuple(_finding(item, f"{path}.limitations[{index}]") for index, item in enumerate(raw["limitations"])),
            missing_requirements=_string_tuple(raw["missing_requirements"], f"{path}.missing_requirements"),
            summary=raw["summary"],
        )
    except (TypeError, ValueError) as error:
        raise ReadinessSerializationError(f"{path} is invalid: {error}") from error


def report_from_dict(raw: Any) -> ReadinessReport:
    raw = _object(raw, ReadinessReport, "readiness_report")
    if not isinstance(raw["paradigm_assessments"], list):
        raise ReadinessSerializationError("paradigm_assessments must be an array")
    if not isinstance(raw["recommended_paradigms"], list):
        raise ReadinessSerializationError("recommended_paradigms must be an array")
    if not isinstance(raw["clarification_items"], list):
        raise ReadinessSerializationError("clarification_items must be an array")
    try:
        return ReadinessReport(
            schema_version=raw["schema_version"], project_id=raw["project_id"],
            project_title=raw["project_title"], revision_id=raw["revision_id"],
            revision_version=raw["revision_version"], assessed_at=raw["assessed_at"],
            status=ReadinessStatus(raw["status"]),
            validation_errors=_string_tuple(raw["validation_errors"], "validation_errors"),
            validation_warnings=_string_tuple(raw["validation_warnings"], "validation_warnings"),
            paradigm_assessments=tuple(_paradigm_assessment(item, f"paradigm_assessments[{index}]") for index, item in enumerate(raw["paradigm_assessments"])),
            recommended_paradigms=tuple(Paradigm(item) for item in raw["recommended_paradigms"]),
            selected_paradigm=Paradigm(raw["selected_paradigm"]) if raw["selected_paradigm"] is not None else None,
            clarification_items=tuple(_clarification(item, f"clarification_items[{index}]") for index, item in enumerate(raw["clarification_items"])),
            explanation=raw["explanation"],
        )
    except (TypeError, ValueError) as error:
        raise ReadinessSerializationError(f"readiness_report is invalid: {error}") from error


def loads_report(content: str) -> ReadinessReport:
    try:
        raw = json.loads(content)
    except (TypeError, json.JSONDecodeError) as error:
        raise ReadinessSerializationError(f"Invalid readiness JSON: {error}") from error
    return report_from_dict(raw)


def save_report(report: ReadinessReport, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(dumps_report(report), encoding="utf-8")
    return destination


def load_report(path: str | Path) -> ReadinessReport:
    source = Path(path)
    try:
        return loads_report(source.read_text(encoding="utf-8"))
    except OSError as error:
        raise OSError(f"Could not read readiness report at {source}: {error}") from error

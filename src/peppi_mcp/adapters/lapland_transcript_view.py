"""Normalize the observed Finnish transcript UI; no browser or authentication I/O.

Input is a minimal projection of one visible study-right section, not page HTML.
The eventual browser adapter must bind that section to its authenticated session
and supply a fresh retrieval time. This parser is not exposed as an MCP tool and
does not enable live mode. Never pass a saved observation off as a fresh read.
"""

import hashlib
import json
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from peppi_mcp.errors import PeppiError
from peppi_mcp.models import Achievement, Identifier, Provenance, Snapshot, StudyRight

TRANSCRIPT_URL = "https://opiskelija-lay.peppi4.lapit.csc.fi/group/opiskelijan-tyopoyta-yo/suoritusote"
MAX_VIEW_BYTES = 1024 * 1024
PARSER_VERSION = "lapland-fi-transcript-view-v1"
_NUMBER = re.compile(r"(?:0|[1-9][0-9]{0,4})(?:[,.][0-9]{1,4})?\Z")
_DATE = re.compile(r"([0-9]{2})\.([0-9]{2})\.([0-9]{4})\Z")


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class _Row(_Input):
    row_type: Literal["course_unit"]
    visible: bool
    source_status: Literal["Suoritettu"]
    course_code: Identifier
    title: str = Field(min_length=1, max_length=500)
    credits: str = Field(min_length=1, max_length=20)
    grade: str = Field(min_length=1, max_length=50)
    assessment_date: str = Field(min_length=1, max_length=10)
    additional_info: str = Field(max_length=500)


class _View(_Input):
    url: Literal[TRANSCRIPT_URL]
    # The source section ID is a study-right key, not proof of account identity.
    study_right_id: Identifier
    visible: bool
    reported_count: int = Field(ge=0, le=1000)
    reported_credits: str = Field(min_length=1, max_length=20)
    rows: Annotated[list[_Row], Field(max_length=1000)]


def _clean(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def _credits(text: str) -> Decimal:
    if not _NUMBER.fullmatch(text):
        raise ValueError
    value = Decimal(text.replace(",", "."))
    if value > 10000:
        raise ValueError
    return value


def _date(text: str) -> date:
    match = _DATE.fullmatch(text)
    if not match:
        raise ValueError
    day, month, year = map(int, match.groups())
    return date(year, month, day)


def normalize_transcript_view(raw_json: str, *, expected_study_right: str,
                              retrieved_at: datetime) -> Snapshot:
    """Require a complete, reconciled completed-course view for one explicit right.

    Other statuses, hidden rows, modules, transfer/correction annotations and
    missing date/grade values require further source investigation. Do not flatten
    or strip those cases to make this input contract accept them. Empty success is
    possible only with an explicit visible zero-count, zero-credit source summary.

    IDs below are derived observation IDs, not upstream achievement identifiers.
    Duplicate course codes remain distinct rows and the existing credit service
    withholds an overall total when replacement/equivalence evidence is missing.
    """
    try:
        invalid_size = (not isinstance(raw_json, str) or len(raw_json) > MAX_VIEW_BYTES
                        or len(raw_json.encode("utf-8")) > MAX_VIEW_BYTES)
    except UnicodeError:
        invalid_size = True
    if invalid_size:
        raise PeppiError("PERSONAL_VIEW_INVALID", "Transcript observation is missing or exceeds its size limit.")
    if (not isinstance(retrieved_at, datetime) or retrieved_at.tzinfo is None
            or retrieved_at.utcoffset() is None):
        raise PeppiError("PERSONAL_VIEW_INVALID", "A timezone-aware retrieval timestamp is required.")
    try:
        view = _View.model_validate_json(raw_json)
        if not view.visible or any(not row.visible for row in view.rows):
            raise ValueError
        if view.study_right_id != expected_study_right:
            raise PeppiError("STUDY_CONTEXT_CHANGED", "The visible study right does not match the requested context. No records were accepted.")
        official = _credits(view.reported_credits)
        normalized = []
        for row in view.rows:
            title, grade = _clean(row.title), _clean(row.grade)
            if not title or not grade or _clean(row.additional_info) not in {"", "-"}:
                raise ValueError
            normalized.append({
                "course_code": row.course_code, "title": title,
                "credits": format(_credits(row.credits).normalize(), "f"),
                "grade": grade, "assessment_date": _date(row.assessment_date).isoformat(),
            })
        if len(normalized) != view.reported_count or sum(
                (Decimal(row["credits"]) for row in normalized), Decimal("0")) != official:
            raise PeppiError("PERSONAL_VIEW_INCOMPLETE", "Completed rows do not reconcile with the visible source count and credits. Reload the view; no total was accepted.")
        # Canonical ordering makes DOM reorderings immaterial while preserving duplicates.
        normalized.sort(key=lambda row: json.dumps(row, sort_keys=True, ensure_ascii=False))
        canonical = json.dumps([PARSER_VERSION, view.study_right_id, normalized,
                                format(official.normalize(), "f")],
                               sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        identity = "ui:" + hashlib.sha256(canonical.encode()).hexdigest()
        # Avoid returning student numbers, names or raw section identifiers.
        right_id = "ui-right:" + hashlib.sha256(view.study_right_id.encode()).hexdigest()
        provenance = Provenance(
            source_id=identity, institution_id="ulapland", study_right_id=right_id,
            source_mode="live", retrieved_at=retrieved_at, completeness="complete",
            warnings=(
                "Coverage is the observed completed-course view for one study right; other statuses are not included.",
                "Observation IDs are derived; stable upstream achievement IDs, grading scales and replacement relationships are not established.",
                "This normalization does not establish an authenticated MCP connection or account identity.",
            ),
        )
        records = tuple(Achievement(
            id=f"ui-row:{index}", course_id=row["course_code"], title=row["title"],
            status="completed", source_status="Suoritettu", kind="course",
            credits=Decimal(row["credits"]), completed_on=date.fromisoformat(row["assessment_date"]),
            grade=row["grade"], grading_scale=None, credit_group_id=row["course_code"],
            provenance=provenance,
        ) for index, row in enumerate(normalized))
        return Snapshot(id=identity, study_rights=(StudyRight(
            id=right_id, programme="Selected Peppi study right", official_total=official,
            provenance=provenance),), achievements=records)
    except PeppiError:
        raise
    except ValidationError as exc:
        # Only fixed schema field names can enter a diagnostic, never source
        # values, unexpected keys, input fragments, or validation contexts.
        fields = {"row_type", "visible", "source_status", "course_code", "title", "credits",
                  "grade", "assessment_date", "additional_info", "reported_count", "reported_credits", "url"}
        invalid = sorted({part for error in exc.errors(include_input=False, include_context=False)
                          for part in error["loc"] if isinstance(part, str) and part in fields})
        detail = ", ".join(invalid) if invalid else "schema"
        raise PeppiError("PERSONAL_VIEW_INVALID", "The transcript has unsupported fields: " + detail + ". No records were accepted.") from None
    except (ValueError, TypeError, OverflowError):
        # Source values and Pydantic diagnostics may contain private data.
        raise PeppiError("PERSONAL_VIEW_INVALID", "The transcript view has an unsupported or malformed layout, row, status or annotation. No records were accepted.") from None

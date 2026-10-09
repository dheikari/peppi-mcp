"""Small validated model; source values and calculated results stay separate."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.:-]+$")]
Credits = Annotated[Decimal, Field(ge=0, le=10000, max_digits=9, decimal_places=4, allow_inf_nan=False)]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Provenance(Record):
    source_id: Identifier
    institution_id: Identifier
    study_right_id: Identifier | None = None
    source_mode: Literal["live", "cached", "imported", "synthetic"]
    retrieved_at: AwareDatetime
    source_updated_at: AwareDatetime | None = None
    source_issued_on: date | None = None
    source_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    source_page: int | None = Field(default=None, ge=1, le=50)
    source_line: int | None = Field(default=None, ge=1, le=10000)
    completeness: Literal["complete", "partial", "unknown"]
    warnings: tuple[str, ...] = ()


class StudyRight(Record):
    id: Identifier
    programme: str = Field(max_length=300)
    official_total: Credits | None = None
    provenance: Provenance


class Achievement(Record):
    id: Identifier
    course_id: Identifier
    title: str = Field(min_length=1, max_length=500)
    status: Literal["completed", "failed", "incomplete", "planned", "unknown"]
    source_status: str = Field(max_length=100)
    kind: Literal["course", "module", "transfer"] = "course"
    credits: Credits | None
    completed_on: date | None = None
    grade: str | None = Field(default=None, max_length=50)
    grading_scale: str | None = Field(default=None, max_length=100)
    # Set only from explicit source evidence; never infer from matching titles.
    credit_group_id: Identifier
    replaces_ids: tuple[Identifier, ...] = ()
    component_ids: tuple[Identifier, ...] | None = None
    provenance: Provenance


class SourceGroup(Record):
    """An ungraded printed subtotal, not another credited achievement."""
    id: Identifier
    title: str = Field(min_length=1, max_length=500)
    credits: Credits
    component_ids: tuple[Identifier, ...] = Field(max_length=1000)
    provenance: Provenance


class Snapshot(Record):
    id: Identifier
    study_rights: tuple[StudyRight, ...] = Field(max_length=100)
    achievements: tuple[Achievement, ...] = Field(max_length=1000)
    source_groups: tuple[SourceGroup, ...] = Field(default=(), max_length=200)

    @model_validator(mode="after")
    def contexts_are_consistent(self):
        rights = {right.id: right for right in self.study_rights}
        if len(rights) != len(self.study_rights):
            raise ValueError("Study-right identifiers must be unique")
        for right in self.study_rights:
            if right.provenance.study_right_id != right.id:
                raise ValueError("Study-right provenance does not match")
        for record in self.achievements:
            right = rights.get(record.provenance.study_right_id)
            if right is None or record.provenance.institution_id != right.provenance.institution_id:
                raise ValueError("Achievement has an unknown study context")
            if record.provenance.source_mode != right.provenance.source_mode:
                raise ValueError("Mixed source modes require separate snapshots")
        groups = {row.id for row in self.achievements}
        for group in self.source_groups:
            right = rights.get(group.provenance.study_right_id)
            if group.id in groups or right is None or group.provenance.institution_id != right.provenance.institution_id or group.provenance.source_mode != right.provenance.source_mode:
                raise ValueError("Source group has a duplicate ID or inconsistent context")
            groups.add(group.id)
        return self


class CreditDecision(Record):
    achievement_id: str
    disposition: Literal["counted", "excluded", "unresolved"]
    reason: str
    credits: Credits | None


class CreditSummary(Record):
    study_right_id: str
    basis: Literal["computed_from_records"] = "computed_from_records"
    status: Literal["complete", "partial", "unresolved"]
    known_subtotal: Credits
    total_credits: Credits | None
    source_reported_total: Credits | None
    difference_from_source_total: Decimal | None
    decisions: tuple[CreditDecision, ...]
    source_groups: tuple[SourceGroup, ...] = ()
    provenance: Provenance
    warnings: tuple[str, ...]


class NoArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ScopedArguments(NoArguments):
    study_right_id: Identifier


class AchievementArguments(ScopedArguments):
    status: Literal["completed", "failed", "incomplete", "planned", "unknown", "all"] = "completed"
    limit: int = Field(default=25, ge=1, le=100)
    cursor: str | None = Field(default=None, min_length=1, max_length=512)

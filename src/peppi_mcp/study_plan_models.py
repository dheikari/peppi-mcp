"""Recorded HOPS versions and source requirements; never a degree-eligibility model."""

from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from peppi_mcp.models import Credits, Identifier, Record, ScopedArguments


class PlanArguments(ScopedArguments):
    plan_id: Identifier | None = None


class ProgressArguments(ScopedArguments):
    plan_id: Identifier


class CreditRange(Record):
    minimum: Credits
    maximum: Credits

    @model_validator(mode="after")
    def ordered(self):
        if self.minimum > self.maximum:
            raise ValueError("Invalid range")
        return self


class PlanVersion(Record):
    id: Identifier
    version: int = Field(ge=1, le=10000)
    source_status: str = Field(min_length=1, max_length=100)


class PlanListing(Record):
    study_right_key: Identifier
    current_plan_id: Identifier
    current_plan_name: str = Field(min_length=1, max_length=300)
    versions: tuple[PlanVersion, ...] = Field(min_length=1, max_length=100)
    retrieved_at: AwareDatetime

    @model_validator(mode="after")
    def unique(self):
        ids = [v.id for v in self.versions]
        if len(set(ids)) != len(ids) or self.current_plan_id not in ids:
            raise ValueError("Ambiguous plan versions")
        return self


class PlanNode(Record):
    id: Identifier
    parent_id: Identifier | None
    course_code: Identifier
    title: str = Field(min_length=1, max_length=500)
    kind: Literal["course", "module", "category", "offering"]
    source_relation: Literal["ordinary", "study_agreement"] = "ordinary"
    requirement: Literal["mandatory", "optional", "alternative", "unknown"]
    source_status: str = Field(max_length=100)
    completed: bool
    outside_plan: bool
    planned_credits: CreditRange
    target_credits: CreditRange | None = None
    source_completed_credits: Credits | None = None
    grade: str | None = Field(default=None, max_length=50)


class PlanSnapshot(Record):
    id: Identifier
    listing: PlanListing
    nodes: tuple[PlanNode, ...] = Field(min_length=1, max_length=1000)
    source_completed_credits: Credits
    source_outside_credits: Credits
    planned_credits: CreditRange
    target_credits: CreditRange
    source_total_credits: Credits
    reconciliation_issues: tuple[Literal["inside_plan_groups", "outside_plan_groups", "headline_total"], ...] = ()

    @model_validator(mode="after")
    def tree(self):
        seen = set()
        for node in self.nodes:
            if node.id in seen or (node.parent_id is not None and node.parent_id not in seen):
                raise ValueError("Incomplete or cyclic plan tree")
            seen.add(node.id)
        return self

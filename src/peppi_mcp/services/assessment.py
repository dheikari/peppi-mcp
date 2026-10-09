"""Typed explanations of observed accounting; never curriculum decisions."""

from decimal import Decimal
from typing import Literal

from pydantic import Field

from peppi_mcp.models import Identifier, Record


class Quantity(Record):
    label: Identifier
    value: Decimal | None = Field(allow_inf_nan=False)
    basis: Literal["source", "calculated"]


class Discrepancy(Record):
    code: Identifier
    category: Literal["source_conflict", "matching_unresolved"]
    scope: Identifier
    node_id: Identifier | None = None
    quantities: tuple[Quantity, ...] = ()
    difference: Decimal | None = Field(default=None, allow_inf_nan=False)
    explanation: str


class Assessment(Record):
    summary: str
    source_consistency: Literal["consistent", "conflicting"]
    comparison_status: Literal["not_requested", "reconciled", "unresolved"]
    limitations: tuple[str, ...]
    quantities: tuple[Quantity, ...]
    discrepancies: tuple[Discrepancy, ...]


EXPLANATIONS = {
    "source_completion_status_unverified": "The source completion label has not been verified.",
    "study_agreement_equivalence_unverified": "An agreement is present, but its equivalence has not been verified.",
    "course_occurs_in_multiple_plan_rows": "The same course code appears in multiple plan rows; allocation is unresolved.",
    "ambiguous_transcript_records": "More than one transcript record has this course code.",
    "transfer_module_or_replacement_relationship_unverified": "The transfer, module or replacement relationship is unverified.",
    "transcript_and_plan_completion_disagree": "The transcript and selected plan disagree about completion.",
    "completed_credits_disagree_or_have_a_range": "Course credits differ or the plan specifies a range.",
    "grade_disagrees": "The transcript and plan grades differ.",
    "source_completion_has_no_exact_course_code_match": "A completed plan row has no unique exact transcript match.",
    "group_completion_does_not_reconcile_with_matched_courses": "The source group total differs from matched descendant courses.",
    "transcript_total_and_plan_total_do_not_reconcile": "The transcript total is unavailable or differs from the HOPS headline.",
}


def assess(plan, progress, node_ids):
    quantities = {
        "hops_sidebar_inside": (plan.source_completed_credits, "calculated"),
        "hops_sidebar_outside": (plan.source_outside_credits, "source"),
        "hops_sidebar_total": (plan.source_completed_credits + plan.source_outside_credits, "source"),
        "hops_headline_total": (plan.source_total_credits, "source"),
        "root_groups_inside": (sum((n.source_completed_credits for n in plan.nodes if n.parent_id is None and not n.outside_plan), Decimal(0)), "calculated"),
        "root_groups_outside": (sum((n.source_completed_credits for n in plan.nodes if n.parent_id is None and n.outside_plan), Decimal(0)), "calculated"),
    }
    discrepancies = []

    def quantity(label):
        value, basis = quantities[label]
        return Quantity(label=label, value=value, basis=basis)

    comparisons = {
        "inside_plan_groups": ("root_groups_inside", "hops_sidebar_inside"),
        "outside_plan_groups": ("root_groups_outside", "hops_sidebar_outside"),
        "headline_total": ("hops_headline_total", "hops_sidebar_total"),
    }
    for code in plan.reconciliation_issues:
        left, right = map(quantity, comparisons[code])
        discrepancies.append(Discrepancy(code=code, category="source_conflict", scope="selected_plan",
            quantities=(left, right), difference=left.value-right.value,
            explanation="These HOPS figures conflict. The difference is first quantity minus second; its cause is not established."))
    comparison = "not_requested"
    if progress is not None:
        comparison = "reconciled" if progress["status"] == "source_credits_reconciled" else "unresolved"
        quantities.update({"transcript_total": (progress["transcript_total_credits"], "calculated"),
            "matched_inside": (Decimal(progress["matched_credits"]["in_plan"]), "calculated"),
            "matched_outside": (Decimal(progress["matched_credits"]["outside_plan"]), "calculated")})
        groups = {g["node_id"]: g for g in progress["groups"]}
        nodes = {n.id: n for n in plan.nodes}
        for issue in progress["issues"]:
            for reason in issue["reasons"]:
                if reason.startswith("hops_source_discrepancy:"):
                    continue
                values = ()
                if reason == "transcript_total_and_plan_total_do_not_reconcile":
                    values = (quantity("transcript_total"), quantity("hops_headline_total"))
                elif reason == "group_completion_does_not_reconcile_with_matched_courses":
                    group = groups[issue["node_id"]]
                    values = (Quantity(label="matched_descendants", value=Decimal(group["matched_course_credits"]), basis="calculated"),
                              Quantity(label="source_group", value=Decimal(group["source_completed_credits"]), basis="source"))
                elif reason == "completed_credits_disagree_or_have_a_range":
                    node = nodes[issue["node_id"]]
                    candidates = [r for r in progress["unmapped_achievements"] if r["course_code"] == node.course_code]
                    if len(candidates) == 1:
                        values = (Quantity(label="transcript_candidate_credits", value=candidates[0]["credits"], basis="source"),
                                  Quantity(label="plan_course_minimum", value=node.planned_credits.minimum, basis="source"))
                        if node.planned_credits.minimum != node.planned_credits.maximum:
                            values += (Quantity(label="plan_course_maximum", value=node.planned_credits.maximum, basis="source"),)
                difference = values[0].value-values[1].value if len(values) == 2 and all(q.value is not None for q in values) else None
                discrepancies.append(Discrepancy(code=reason, category="matching_unresolved", scope="course_or_group" if issue["node_id"] else "selected_plan",
                    node_id=node_ids.get(issue["node_id"]), quantities=values, difference=difference,
                    explanation=EXPLANATIONS[reason]))
        if progress["unmapped_achievements"]:
            discrepancies.append(Discrepancy(code="unmapped_achievements", category="matching_unresolved", scope="transcript",
                explanation="Some transcript records lack a verified allocation in this selected version. Absence does not establish outside-plan status; inspect their individual credits."))
    conflicting = bool(plan.reconciliation_issues)
    summary = ("Partial HOPS evidence: source totals conflict. " if conflicting else "The checked HOPS source totals agree. ")
    summary += {"not_requested":"Transcript comparison was not requested.", "reconciled":"Transcript credit accounting reconciles; degree requirements remain unverified.",
                "unresolved":"Transcript comparison has unresolved items; inspect the discrepancies."}[comparison]
    return Assessment(summary=summary, source_consistency="conflicting" if conflicting else "consistent", comparison_status=comparison,
        limitations=("Coverage is the selected rendered HOPS version, not all curriculum rules.",
            "Elective, alternative, agreement and equivalence rules remain unverified; no graduation decision is possible.",
            "Displayed HOPS targets are not verified degree requirements. Source GPA and degree-credit requirements are not provided."),
        quantities=tuple(quantity(label) for label in quantities), discrepancies=tuple(discrepancies))

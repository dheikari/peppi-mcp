"""Conservative comparison of a recorded plan with a fresh scoped transcript."""

from collections import Counter, defaultdict
from decimal import Decimal

from peppi_mcp.services.achievements import credit_summary


def study_progress(plan, transcript):
    summary = credit_summary(transcript, transcript.study_rights[0].id)
    rows = defaultdict(list)
    for row in transcript.achievements:
        rows[row.course_id].append(row)
    courses = [n for n in plan.nodes if n.kind == "course"]
    uses = Counter(n.course_code for n in courses)
    matched, allocations, issues, requirements = set(), {}, [], []
    if plan.reconciliation_issues:
        issues.append({"node_id":None,"reasons":["hops_source_discrepancy:" + reason for reason in plan.reconciliation_issues]})
    for node in courses:
        candidates = rows[node.course_code]
        reasons, achievement = [], None
        if node.source_status not in {"Suoritettu", "Ei arvioitu", "Ilmoittautuminen hyväksytty",
                "Ilmoittautuminen käynnissä", "Ilmoittautuminen odottaa hyväksyntää", "Ajoitettu HOPSiin"}:
            reasons.append("source_completion_status_unverified")
        if node.source_relation == "study_agreement":
            reasons.append("study_agreement_equivalence_unverified")
        if uses[node.course_code] > 1:
            reasons.append("course_occurs_in_multiple_plan_rows")
        if len(candidates) > 1:
            reasons.append("ambiguous_transcript_records")
        elif candidates:
            achievement = candidates[0]
            if achievement.kind != "course" or achievement.replaces_ids or achievement.component_ids:
                reasons.append("transfer_module_or_replacement_relationship_unverified")
            if not node.completed:
                reasons.append("transcript_and_plan_completion_disagree")
            if (achievement.credits != node.planned_credits.minimum
                    or node.planned_credits.minimum != node.planned_credits.maximum):
                reasons.append("completed_credits_disagree_or_have_a_range")
            if node.grade != achievement.grade:
                reasons.append("grade_disagrees")
        elif node.completed:
            reasons.append("source_completion_has_no_exact_course_code_match")
        verified = node.completed and achievement is not None and not reasons
        if verified:
            matched.add(achievement.id)
            allocations[node.id] = achievement.credits
        if reasons:
            issues.append({"node_id": node.id, "reasons": reasons})
        requirements.append({"node_id": node.id, "course_code": node.course_code, "title": node.title,
            "requirement": node.requirement, "outside_plan": node.outside_plan,
            "status": "unresolved" if reasons else "source_completed_and_matched" if verified else "not_source_completed",
            "achievement_id": achievement.id if verified else None, "reasons": reasons})
    by_id = {n.id: n for n in plan.nodes}
    groups = []
    for group in (n for n in plan.nodes if n.kind != "course"):
        descendants = []
        for course in courses:
            parent = course.parent_id
            while parent is not None:
                if parent == group.id:
                    descendants.append(course)
                    break
                parent = by_id[parent].parent_id
        confirmed = sum((allocations.get(n.id, Decimal(0)) for n in descendants), Decimal(0))
        reconciled = confirmed == group.source_completed_credits
        # A target alone does not say which elective/alternative combinations count.
        reasons = ["group_choice_and_equivalence_rules_not_exposed"]
        if not reconciled:
            reasons.append("group_completion_does_not_reconcile_with_matched_courses")
            issues.append({"node_id": group.id, "reasons": reasons[1:]})
        groups.append({"node_id": group.id, "title": group.title, "outside_plan": group.outside_plan,
            "source_completed_credits": str(group.source_completed_credits),
            "matched_course_credits": str(confirmed), "credits_reconciled": reconciled,
            "requirement_satisfaction": "unresolved", "reasons": reasons})
    unmatched = [r for r in transcript.achievements if r.id not in matched]
    if summary.status != "complete" or summary.total_credits != plan.source_total_credits:
        issues.append({"node_id": None, "reasons": ["transcript_total_and_plan_total_do_not_reconcile"]})
    in_plan = sum((amount for key, amount in allocations.items() if not by_id[key].outside_plan), Decimal(0))
    outside = sum((amount for key, amount in allocations.items() if by_id[key].outside_plan), Decimal(0))
    return {"basis": "selected_recorded_hops_version_and_fresh_transcript",
        "status": "unresolved" if issues or unmatched else "source_credits_reconciled",
        "degree_requirements_satisfied": None, "graduation_eligibility": None,
        "transcript_total_credits": str(summary.total_credits) if summary.total_credits is not None else None,
        "source_reported": {"completed_in_plan": str(plan.source_completed_credits),
            "completed_outside_plan": str(plan.source_outside_credits), "total_credits": str(plan.source_total_credits),
            "target_credits": plan.target_credits.model_dump(mode="json")},
        "source_root_group_credits": {"in_plan":str(sum((n.source_completed_credits for n in plan.nodes if n.parent_id is None and not n.outside_plan),Decimal(0))),
            "outside_plan":str(sum((n.source_completed_credits for n in plan.nodes if n.parent_id is None and n.outside_plan),Decimal(0)))},
        "source_reconciliation_issues": list(plan.reconciliation_issues),
        "matched_credits": {"in_plan": str(in_plan), "outside_plan": str(outside)},
        "requirements": requirements, "groups": groups, "issues": issues,
        "unmapped_achievements": [{"achievement_id": r.id, "course_code": r.course_id, "title": r.title,
                                   "credits": str(r.credits) if r.credits is not None else None} for r in unmatched],
        "equivalences_applied": [],
        "warnings": ["Group targets do not establish elective, alternative, substitution or transfer rules; requirement satisfaction remains unresolved.",
                     "Only unique exact course codes with agreeing completion, grade and credits are matched. Titles never establish equivalence.",
                     "Studies outside HOPS are reported separately and do not satisfy a plan requirement automatically."]}

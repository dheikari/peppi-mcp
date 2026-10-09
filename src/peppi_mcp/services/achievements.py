"""Conservative counting. Unsupported relationships remain unresolved."""

import base64
import hashlib
import json
from collections import defaultdict
from decimal import Decimal

from peppi_mcp.errors import PeppiError
from peppi_mcp.models import AchievementArguments, CreditDecision, CreditSummary, Snapshot


def study_right(snapshot: Snapshot, right_id: str):
    for right in snapshot.study_rights:
        if right.id == right_id:
            return right
    raise PeppiError("STUDY_RIGHT_NOT_FOUND", "Select a study right returned by list_study_rights.")


def list_achievements(snapshot: Snapshot, args: AchievementArguments) -> dict:
    right = study_right(snapshot, args.study_right_id)
    # A cursor is bound to both the exact snapshot and filters, never a file path.
    signature = hashlib.sha256(
        (snapshot.model_dump_json() + args.study_right_id + ":" + args.status).encode()
    ).hexdigest()
    rows = sorted(
        (r for r in snapshot.achievements if r.provenance.study_right_id == args.study_right_id
         and (args.status == "all" or r.status == args.status)),
        key=lambda r: (r.id, r.model_dump_json()),
    )
    offset = 0
    if args.cursor is not None:
        try:
            token = json.loads(base64.b64decode(args.cursor, altchars=b"-_", validate=True))
            if set(token) != {"signature", "offset"} or token["signature"] != signature:
                raise ValueError
            offset = token["offset"]
            if type(offset) is not int or not 0 < offset < len(rows):
                raise ValueError
        except (ValueError, TypeError, KeyError, UnicodeError):
            raise PeppiError("INVALID_CURSOR", "Cursor is invalid for this snapshot and filter.") from None
    end = offset + args.limit
    cursor = None
    if end < len(rows):
        cursor = base64.urlsafe_b64encode(json.dumps({"signature": signature, "offset": end}).encode()).decode()
    return {
        "study_right_id": right.id,
        "items": [r.model_dump(mode="json") for r in rows[offset:end]],
        "matching_records": len(rows), "next_cursor": cursor,
        "provenance": right.provenance.model_dump(mode="json"),
        "warnings": ["Raw source rows are not a credit total; use get_credit_summary."],
    }


def credit_summary(snapshot: Snapshot, right_id: str) -> CreditSummary:
    right = study_right(snapshot, right_id)
    rows = [r for r in snapshot.achievements if r.provenance.study_right_id == right_id]
    by_id = defaultdict(list)
    for row in rows:
        by_id[row.id].append(row)
    unique = {key: group[0] for key, group in by_id.items()}
    unresolved: dict[str, str] = {}
    excluded: dict[str, str] = {}
    notes = ["Synthetic demonstration; not official student records."] if right.provenance.source_mode == "synthetic" else []
    for key, group in by_id.items():
        if any(row != group[0] for row in group):
            unresolved[key] = "Conflicting rows have the same source identifier."
        elif len(group) > 1:
            notes.append(f"Identical duplicate source rows collapsed: {key}.")
    for key, row in unique.items():
        if row.status != "completed":
            excluded[key] = "Source does not mark this record completed."
        if row.status == "unknown":
            unresolved[key] = "Completion status is unknown; this row cannot support a total."
        elif row.status == "completed" and row.credits is None:
            unresolved[key] = "Completed record has no credit value."
        if row.status == "completed" and (row.completed_on is None or row.grade is None or row.grading_scale is None):
            notes.append(f"Missing completion date, grade or grading scale: {key}.")

    # Replacements are supported only within an explicit credit group and context.
    for key, row in unique.items():
        if not row.replaces_ids:
            continue
        targets = [unique.get(target) for target in row.replaces_ids]
        invalid = (key in unresolved or row.status != "completed" or
                   any(target is None or target.id == key or target.credit_group_id != row.credit_group_id
                       or target.id in unresolved for target in targets))
        # Chains/cycles and branching need a richer source-specific policy.
        invalid = invalid or any(target and target.replaces_ids for target in targets)
        invalid = invalid or any(key in other.replaces_ids for other in unique.values())
        if invalid:
            unresolved[key] = "Replacement relationship is missing, conflicting or unsupported."
            for target in row.replaces_ids:
                if target in unique:
                    unresolved[target] = "Unresolved replacement relationship."
        else:
            for target in row.replaces_ids:
                excluded[target] = f"Explicitly replaced by {key}."

    represented_modules = set()
    for key, row in unique.items():
        if row.kind != "module" or row.status != "completed" or key in excluded:
            continue
        ids = row.component_ids
        components = [unique.get(child) for child in ids or ()]
        valid = bool(ids) and len(ids) == len(set(ids)) and all(
            child and child.kind != "module" and child.status == "completed" and child.credits is not None
            and child.id not in unresolved and child.id not in excluded for child in components
        )
        if valid and row.credits == sum((child.credits for child in components), Decimal("0")):
            excluded[key] = "Module represented by explicitly linked components; counted once."
            represented_modules.add(key)
        else:
            unresolved[key] = "Module coverage or credit reconciliation is unresolved."
            for child in ids or ():
                if child in unique:
                    unresolved[child] = "Component belongs to an unresolved module."

    # Do not guess whether repeated/equivalent completions confer additional credit.
    groups = defaultdict(list)
    courses = defaultdict(list)
    for key, row in unique.items():
        if row.status == "completed" and key not in excluded:
            groups[row.credit_group_id].append(key)
            courses[row.course_id].append(key)
    for group in (*groups.values(), *courses.values()):
        if len(group) > 1:
            for key in group:
                unresolved[key] = "Multiple completions of one course or credit group; no unique replacement."

    group_decisions = []
    group_unresolved = False
    for group in snapshot.source_groups:
        if group.provenance.study_right_id != right_id:
            continue
        members = [unique.get(key) for key in group.component_ids]
        valid = len(group.component_ids) == len(set(group.component_ids)) and all(
            row is not None and (row.kind != "module" or (row.id in represented_modules and set(row.component_ids).issubset(group.component_ids)))
            and row.status != "unknown" and row.id not in unresolved
            and (row.status != "completed" or row.credits is not None) for row in members)
        amount = sum((row.credits for row in members if row is not None and row.status == "completed" and row.id not in excluded), Decimal("0")) if valid else None
        matched = valid and amount == group.credits
        group_unresolved = group_unresolved or not matched
        group_decisions.append(CreditDecision(achievement_id=group.id, disposition="excluded" if matched else "unresolved",
            reason="Printed subtotal reconciles with its linked rows; not counted again." if matched else "Printed subtotal does not reconcile with its linked rows; overall total withheld.", credits=group.credits))
    subtotal = Decimal("0")
    decisions = []
    for key in sorted(unique):
        row = unique[key]
        if key in unresolved:
            disposition, reason = "unresolved", unresolved[key]
        elif key in excluded:
            disposition, reason = "excluded", excluded[key]
        else:
            disposition, reason = "counted", "One completed achievement in an explicit credit group."
            subtotal += row.credits
        decisions.append(CreditDecision(achievement_id=key, disposition=disposition, reason=reason, credits=row.credits))
    decisions.extend(group_decisions)
    provenances = [right.provenance, *(row.provenance for row in rows), *(group.provenance for group in snapshot.source_groups if group.provenance.study_right_id == right_id)]
    complete = all(p.completeness == "complete" for p in provenances)
    for provenance in provenances:
        notes.extend(provenance.warnings)
    status = "unresolved" if unresolved or group_unresolved else "complete" if complete else "partial"
    total = subtotal if status == "complete" else None
    difference = total - right.official_total if total is not None and right.official_total is not None else None
    if unresolved:
        notes.append("The known subtotal excludes unresolved records and is not a trustworthy overall total.")
    if group_unresolved:
        notes.append("One or more printed source subtotals do not reconcile; no overall total is available.")
    if not complete:
        notes.append("Source coverage is incomplete or unknown; overall total withheld.")
    if difference is not None and difference != 0:
        notes.append("Computed total differs from the source-reported total; cause is not established.")
    notes.append("Credits alone do not establish graduation or enrolment eligibility.")
    return CreditSummary(
        study_right_id=right_id, status=status, known_subtotal=subtotal, total_credits=total,
        source_reported_total=right.official_total, difference_from_source_total=difference,
        decisions=tuple(decisions), provenance=right.provenance, warnings=tuple(dict.fromkeys(notes)),
        source_groups=tuple(group for group in snapshot.source_groups if group.provenance.study_right_id == right_id),
    )

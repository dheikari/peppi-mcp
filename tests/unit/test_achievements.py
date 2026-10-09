from decimal import Decimal

import pytest
from pydantic import ValidationError

from peppi_mcp.errors import PeppiError
from peppi_mcp.models import Achievement, AchievementArguments, Snapshot
from peppi_mcp.services.achievements import credit_summary, list_achievements


def changed(snapshot, key, **updates):
    raw = snapshot.model_dump(mode="json")
    for row in raw["achievements"]:
        if row["id"] == key:
            row.update(updates)
    return Snapshot.model_validate(raw)


def test_credit_basis_fraction_modules_transfers_and_replacements(snapshot):
    summary = credit_summary(snapshot, "demo-main")
    assert summary.total_credits == Decimal("15.5")
    assert summary.difference_from_source_total == 0
    decisions = {d.achievement_id: d.disposition for d in summary.decisions}
    assert {k for k, v in decisions.items() if v == "counted"} == {"a", "b", "revised", "transfer"}
    assert {k for k, v in decisions.items() if v == "excluded"} == {"module", "old", "failed", "planned"}
    assert summary.model_dump(mode="json")["total_credits"] == "15.5"


def test_contexts_are_never_combined(snapshot):
    assert credit_summary(snapshot, "demo-other").total_credits == 5
    with pytest.raises(PeppiError, match="Select a study right"):
        credit_summary(snapshot, "missing")


def test_ambiguous_empty_and_partial_are_different(snapshot):
    assert credit_summary(snapshot, "demo-ambiguous").status == "unresolved"
    assert credit_summary(snapshot, "demo-ambiguous").total_credits is None
    assert credit_summary(snapshot, "demo-empty").total_credits == 0
    partial = credit_summary(snapshot, "demo-partial")
    assert partial.status == "partial" and partial.total_credits is None
    assert partial.known_subtotal == 2


def test_identical_duplicate_does_not_double_count(snapshot):
    duplicated = snapshot.model_copy(update={"achievements": (*snapshot.achievements, snapshot.achievements[0])})
    assert credit_summary(duplicated, "demo-main").total_credits == Decimal("15.5")
    assert "duplicate" in " ".join(credit_summary(duplicated, "demo-main").warnings)


def test_conflicting_duplicate_is_unresolved(snapshot):
    bad = snapshot.achievements[0].model_copy(update={"credits": Decimal("6")})
    conflicted = snapshot.model_copy(update={"achievements": (*snapshot.achievements, bad)})
    assert credit_summary(conflicted, "demo-main").total_credits is None


@pytest.mark.parametrize("updates", [
    {"component_ids": None}, {"component_ids": ["missing"]},
    {"component_ids": ["a", "a"]}, {"credits": "8"},
    {"component_ids": ["module"]}, {"component_ids": ["other"]},
])
def test_invalid_module_relationship_withholds_total(snapshot, updates):
    assert credit_summary(changed(snapshot, "module", **updates), "demo-main").total_credits is None


@pytest.mark.parametrize("updates", [
    {"replaces_ids": ["missing"]}, {"replaces_ids": ["revised"]},
    {"replaces_ids": ["other"]}, {"credit_group_id": "different"},
    {"status": "failed"}, {"credits": None},
])
def test_invalid_replacement_withholds_total(snapshot, updates):
    assert credit_summary(changed(snapshot, "revised", **updates), "demo-main").total_credits is None


def test_replacement_cycle_is_unresolved(snapshot):
    modified = changed(snapshot, "old", replaces_ids=["revised"])
    assert credit_summary(modified, "demo-main").total_credits is None


def test_repeated_completion_without_replacement_is_unresolved(snapshot):
    assert credit_summary(changed(snapshot, "revised", replaces_ids=[]), "demo-main").total_credits is None


def test_equal_titles_do_not_establish_equivalence(snapshot):
    modified = changed(snapshot, "transfer", title=snapshot.achievements[0].title)
    assert credit_summary(modified, "demo-main").total_credits == Decimal("15.5")


def test_same_course_in_different_credit_groups_is_still_ambiguous(snapshot):
    modified = changed(snapshot, "transfer", course_id="DEMO-a")
    assert credit_summary(modified, "demo-main").total_credits is None


def test_missing_metadata_is_preserved_and_warned(snapshot):
    modified = changed(snapshot, "transfer", completed_on=None, grade=None, grading_scale=None)
    summary = credit_summary(modified, "demo-main")
    assert summary.total_credits == Decimal("15.5")
    assert any("Missing completion" in warning for warning in summary.warnings)


def test_total_mismatch_is_explained(snapshot):
    raw = snapshot.model_dump(mode="json")
    raw["study_rights"][0]["official_total"] = "20"
    summary = credit_summary(Snapshot.model_validate(raw), "demo-main")
    assert summary.difference_from_source_total == Decimal("-4.5")
    assert any("cause is not established" in warning for warning in summary.warnings)


@pytest.mark.parametrize("value", ["-1", "NaN", "Infinity", "1.23456"])
def test_bad_credit_values_are_rejected(snapshot, value):
    with pytest.raises(ValidationError):
        changed(snapshot, "a", credits=value)


def test_unknown_study_context_is_rejected(snapshot):
    row = snapshot.achievements[0].model_dump(mode="json")
    row["provenance"]["study_right_id"] = "unknown"
    with pytest.raises(ValidationError):
        snapshot.model_validate({**snapshot.model_dump(), "achievements": [Achievement.model_validate(row)]})


def test_pagination_recovers_every_matching_record(snapshot):
    cursor = None
    ids = []
    while True:
        page = list_achievements(snapshot, AchievementArguments(study_right_id="demo-main", limit=2, cursor=cursor))
        ids.extend(row["id"] for row in page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert ids == ["a", "b", "module", "old", "revised", "transfer"]
    assert page["matching_records"] == 6


def test_cursor_bound_to_snapshot_and_filter(snapshot):
    page = list_achievements(snapshot, AchievementArguments(study_right_id="demo-main", limit=1))
    cursor = page["next_cursor"]
    for source, right, status in [(snapshot, "demo-other", "completed"),
                                   (snapshot, "demo-main", "all"),
                                   (changed(snapshot, "a", grade="3"), "demo-main", "completed")]:
        with pytest.raises(PeppiError) as error:
            list_achievements(source, AchievementArguments(study_right_id=right, status=status, cursor=cursor))
        assert error.value.code == "INVALID_CURSOR"


@pytest.mark.parametrize("cursor", ["garbage", "e30=", "bnVsbA==", "W10="])
def test_malformed_cursor_is_a_clear_error(snapshot, cursor):
    with pytest.raises(PeppiError) as error:
        list_achievements(snapshot, AchievementArguments(study_right_id="demo-main", cursor=cursor))
    assert error.value.code == "INVALID_CURSOR"

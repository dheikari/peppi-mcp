"""Fictional UI projections: no saved personal page or account identifiers."""

import copy
import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from peppi_mcp.adapters.lapland_transcript_view import (
    MAX_VIEW_BYTES, TRANSCRIPT_URL, normalize_transcript_view,
)
from peppi_mcp.errors import PeppiError
from peppi_mcp.services.achievements import credit_summary

NOW = datetime(2026, 1, 10, tzinfo=timezone.utc)


def observation():
    return {
        "url": TRANSCRIPT_URL, "study_right_id": "fictional-right", "visible": True,
        "reported_count": 2, "reported_credits": "2,5",
        "rows": [
            {"row_type": "course_unit", "visible": True, "source_status": "Suoritettu",
             "course_code": "DEMO101", "title": "Fictional course Ä", "credits": "2",
             "grade": "HYV", "assessment_date": "02.01.2026", "additional_info": "-"},
            {"row_type": "course_unit", "visible": True, "source_status": "Suoritettu",
             "course_code": "DEMO102", "title": "Fictional fractional course", "credits": "0,5",
             "grade": "4", "assessment_date": "03.01.2026", "additional_info": ""},
        ],
    }


def parse(view, **kwargs):
    return normalize_transcript_view(json.dumps(view, ensure_ascii=False),
        expected_study_right=kwargs.get("expected_study_right", "fictional-right"),
        retrieved_at=kwargs.get("retrieved_at", NOW))


def test_fractional_completed_rows_reconcile_without_counting_headers():
    snapshot = parse(observation())
    summary = credit_summary(snapshot, snapshot.study_rights[0].id)
    assert summary.status == "complete"
    assert summary.total_credits == Decimal("2.5")
    assert summary.difference_from_source_total == 0
    assert snapshot.source_groups == ()
    assert {row.grade for row in snapshot.achievements} == {"HYV", "4"}
    assert all(row.grading_scale is None for row in snapshot.achievements)
    assert all(row.provenance.retrieved_at == NOW for row in snapshot.achievements)
    assert "fictional-right" not in snapshot.model_dump_json()


def test_missing_rows_with_visible_nonzero_summary_are_not_empty_success():
    view = observation()
    view["rows"] = []
    with pytest.raises(PeppiError, match="do not reconcile") as error:
        parse(view)
    assert error.value.code == "PERSONAL_VIEW_INCOMPLETE"


def test_zero_requires_an_explicit_zero_source_summary():
    view = observation()
    view.update(rows=[], reported_count=0, reported_credits="0")
    snapshot = parse(view)
    assert credit_summary(snapshot, snapshot.study_rights[0].id).total_credits == 0


@pytest.mark.parametrize("field,value", [
    ("reported_count", 1), ("reported_count", 3), ("reported_credits", "2,4"),
])
def test_reconciliation_mismatch(field, value):
    view = observation()
    view[field] = value
    with pytest.raises(PeppiError) as error:
        parse(view)
    assert error.value.code == "PERSONAL_VIEW_INCOMPLETE"


@pytest.mark.parametrize("field,value", [
    ("url", "https://other.example/suoritusote"),
    ("url", TRANSCRIPT_URL + "?p_auth=fictional-secret"),
    ("visible", False), ("visible", 1), ("reported_count", True),
    ("reported_credits", "NaN"), ("reported_credits", "2e0"),
    ("reported_credits", "10001"), ("reported_credits", "-1"),
    ("unexpected", "fictional-private-marker"),
])
def test_invalid_context_shape(field, value):
    view = observation()
    view[field] = value
    with pytest.raises(PeppiError) as error:
        parse(view)
    assert error.value.code == "PERSONAL_VIEW_INVALID"
    assert "fictional-private-marker" not in str(error.value)
    assert "fictional-secret" not in str(error.value)


@pytest.mark.parametrize("field,value", [
    ("row_type", "module"), ("row_type", "transfer"), ("visible", False), ("visible", 1),
    ("source_status", "Ei arvioitu"), ("source_status", ""),
    ("course_code", ""), ("title", "   "), ("grade", ""),
    ("assessment_date", "31.02.2026"), ("assessment_date", "2026-01-02"),
    ("credits", "2.00001"), ("additional_info", "fictional-private-correction"),
])
def test_unsupported_rows_fail_without_private_error_payload(field, value):
    view = observation()
    view["rows"][0][field] = value
    with pytest.raises(PeppiError) as error:
        parse(view)
    assert error.value.code == "PERSONAL_VIEW_INVALID"
    assert "fictional-private-correction" not in str(error.value)


def test_wrong_study_right_rejects_all_records():
    with pytest.raises(PeppiError) as error:
        parse(observation(), expected_study_right="another-right")
    assert error.value.code == "STUDY_CONTEXT_CHANGED"


def test_duplicate_courses_remain_unresolved_in_credit_service():
    view = observation()
    view["rows"][1] = copy.deepcopy(view["rows"][0])
    view["reported_credits"] = "4"
    snapshot = parse(view)
    assert len(snapshot.achievements) == 2
    assert len({r.id for r in snapshot.achievements}) == 2
    summary = credit_summary(snapshot, snapshot.study_rights[0].id)
    assert summary.status == "unresolved" and summary.total_credits is None


def test_order_is_irrelevant_but_changed_records_change_observation_id():
    view = observation()
    first = parse(view)
    view["rows"].reverse()
    assert parse(view) == first
    view["rows"][0]["grade"] = "5"
    assert parse(view).id != first.id


def test_retrieval_time_is_preserved_without_changing_content_identity():
    later = datetime(2026, 1, 11, tzinfo=timezone.utc)
    first, second = parse(observation()), parse(observation(), retrieved_at=later)
    assert first.id == second.id
    assert second.study_rights[0].provenance.retrieved_at == later
    with pytest.raises(PeppiError):
        parse(observation(), retrieved_at=datetime(2026, 1, 11))


def test_bounded_and_malformed_input():
    for body in ("x" * (MAX_VIEW_BYTES + 1), "{", "null", "[]", "\ud800"):
        with pytest.raises(PeppiError) as error:
            normalize_transcript_view(body, expected_study_right="fictional-right", retrieved_at=NOW)
        assert error.value.code == "PERSONAL_VIEW_INVALID"

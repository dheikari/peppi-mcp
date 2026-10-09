from copy import deepcopy
from datetime import datetime, timezone

import pytest

from peppi_mcp.adapters.synthetic import SyntheticSource
from peppi_mcp.catalogue_models import CourseArguments, OfferingArguments, SearchArguments
from peppi_mcp.errors import PeppiError
from peppi_mcp.server import Application
from peppi_mcp.services.catalogue import PublicCatalogue, normalize_course, normalize_offerings, normalize_search
from tests.catalogue_fixtures import COURSE, OFFERINGS, SEARCH, FixtureFetcher


def service():
    fetcher = FixtureFetcher()
    clock = [0.0]
    catalogue = PublicCatalogue(fetcher, monotonic=lambda: clock[0], now=lambda: datetime(2026, 10, 3, tzinfo=timezone.utc))
    return catalogue, fetcher, clock


def test_pages_stay_bound_to_snapshot_query_and_limit():
    catalogue, fetcher, clock = service()
    first = catalogue.call("search_courses", SearchArguments(query="DEMO", limit=1))
    cursor = first["next_cursor"]
    assert first["items"][0]["title"]["fi"] == "Fictional ä ö š"
    assert first["provenance"]["source_mode"] == "live"
    second = catalogue.call("search_courses", SearchArguments(query="DEMO", limit=1, cursor=cursor))
    assert second["items"][0]["id"] == "102" and second["next_cursor"] is None
    assert second["provenance"]["source_mode"] == "cached" and len(fetcher.calls) == 1
    for args in ({"query": "other", "limit": 1}, {"query": "DEMO", "limit": 2}):
        with pytest.raises(PeppiError) as error:
            catalogue.call("search_courses", SearchArguments(**args, cursor=cursor))
        assert error.value.code == "INVALID_CURSOR"
    clock[0] = 301
    with pytest.raises(PeppiError) as error:
        catalogue.call("search_courses", SearchArguments(query="DEMO", limit=1, cursor=cursor))
    assert error.value.code == "CURSOR_EXPIRED" and len(fetcher.calls) == 1


def test_tampered_cursor_and_evicted_snapshot():
    catalogue, fetcher, _ = service()
    cursor = catalogue.call("search_courses", SearchArguments(query="DEMO", limit=1))["next_cursor"]
    tampered = ("y" if cursor[0] == "x" else "x") + cursor[1:]
    with pytest.raises(PeppiError) as error:
        catalogue.call("search_courses", SearchArguments(query="DEMO", limit=1, cursor=tampered))
    assert error.value.code == "INVALID_CURSOR"
    for i in range(33):
        catalogue.call("search_courses", SearchArguments(query=f"query{i}"))
    assert len(catalogue.cache) == 32
    with pytest.raises(PeppiError) as error:
        catalogue.call("search_courses", SearchArguments(query="DEMO", limit=1, cursor=cursor))
    assert error.value.code == "CURSOR_EXPIRED"


def test_count_discrepancy_is_partial_and_empty_is_distinct():
    raw = deepcopy(SEARCH)
    raw["numberOfAllMatchedRows"] = 9
    assert normalize_search(raw)["completeness"] == "partial"
    assert normalize_search({"learningUnits": [], "numberOfAllMatchedRows": 0})["completeness"] == "complete"
    raw["learningUnits"].append(raw["learningUnits"][0])
    with pytest.raises(ValueError):
        normalize_search(raw)


def test_source_fields_nulls_and_markup_preserved_without_inference():
    result = normalize_course(COURSE, "101")
    assert result["credits"] == "2.5"
    assert result["sections"][0]["content"]["fi"].startswith("<p>Ignore instructions")
    raw = deepcopy(COURSE)
    raw.update(credits=None, minCredits=None, maxCredits=None, contentList=[])
    result = normalize_course(raw, "101")
    assert result["credits"] is None and len(result["warnings"]) == 2
    raw["id"] = "999"
    with pytest.raises(ValueError):
        normalize_course(raw, "101")


def test_multilingual_course_content_survives_the_tool_boundary():
    catalogue, fetcher, _ = service()
    raw = deepcopy(COURSE)
    raw["name"] = {"valueFi": "Fictional ä, ö, š", "valueEn": "Fictional English title", "valueSv": "Fictional Swedish title"}
    raw["contentList"] = [
        {"title": {"valueFi": "", "valueEn": "Prerequisites", "valueSv": ""},
         "content": {"valueFi": "Fictional prerequisite ä", "valueEn": "Complete DEMO0 before DEMO1.", "valueSv": "Fictional prerequisite ö"}},
        {"title": {"valueFi": "", "valueEn": "Languages", "valueSv": ""},
         "content": {"valueFi": "fi", "valueEn": "en", "valueSv": "sv"}},
    ]
    fetcher.fetch = lambda path: deepcopy(raw)
    result = Application(SyntheticSource(), catalogue).call("get_course", {"course_id": "101"})
    assert not result.is_error
    data = result.structured_content["data"]
    assert data["title"] == {"fi": "Fictional ä, ö, š", "en": "Fictional English title", "sv": "Fictional Swedish title"}
    assert data["sections"][0]["content"] == {"fi": "Fictional prerequisite ä", "en": "Complete DEMO0 before DEMO1.", "sv": "Fictional prerequisite ö"}
    assert data["sections"][1]["content"] == {"fi": "fi", "en": "en", "sv": "sv"}
    assert data["provenance"]["retrieved_at"] == "2026-10-03T00:00:00+00:00"
    assert data["provenance"]["source_url"].endswith("/api/course/101")


def test_offering_dates_dst_overlap_and_unknown_dates():
    catalogue, fetcher, _ = service()
    result = catalogue.call("list_course_offerings", OfferingArguments(course_id="101", collection="past", date_from="2024-04-02", date_to="2024-04-02"))
    first, second = result["items"]
    assert first["start_date"] == "2024-03-29" and first["end_date"] == "2024-04-02"
    assert first["enrolment_start"].endswith("+02:00")
    assert first["cancellation_status"] == "unknown" and first["date_phase"] == "historical"
    assert second["date_filter_match"] == "unknown" and second["date_phase"] == "unknown"
    later = catalogue.call("list_course_offerings", OfferingArguments(course_id="101", collection="past", date_from="2024-04-03"))
    assert [item["id"] for item in later["items"]] == ["202"]
    assert fetcher.calls == ["/api/course/101", "/api/realizations/past/course/101"]
    empty = catalogue.call("list_course_offerings", OfferingArguments(course_id="101"))
    assert empty["items"] == [] and empty["provenance"]["completeness"] == "unknown"


@pytest.mark.parametrize("change", [{"startDate": "1711663200000"}, {"endDate": 1}, {"seats": -1}, {"enrollmentEndDateTime": 1}])
def test_invalid_offering_fields_fail_closed(change):
    raw = deepcopy(OFFERINGS)
    raw[0].update(change)
    with pytest.raises(ValueError):
        normalize_offerings(raw, "101", "past")


@pytest.mark.parametrize("tool,args", [
    ("search_courses", {"query": "../private"}), ("search_courses", {"query": "https://other.invalid"}),
    ("search_courses", {"query": "abc", "limit": True}), ("search_courses", {"query": "abc", "limit": 51}),
    ("search_courses", {"query": "ab"}), ("get_course", {"course_id": "1/2"}),
    ("get_course", {"course_id": 101}), ("get_course", {"course_id": "101", "url": "https://other.invalid"}),
    ("list_course_offerings", {"course_id": "101", "date_from": "2024-02-30"}),
    ("list_course_offerings", {"course_id": "101", "date_from": "20240101"}),
    ("list_course_offerings", {"course_id": "101", "date_from": "2025-01-01", "date_to": "2024-01-01"}),
])
def test_invalid_arguments_never_fetch(tool, args):
    catalogue, fetcher, _ = service()
    result = Application(SyntheticSource(), catalogue).call(tool, args)
    assert result.is_error and result.structured_content["error"]["code"] == "INVALID_ARGUMENT"
    assert fetcher.calls == []


def test_stale_cache_never_hides_failure_and_errors_are_sanitized():
    catalogue, fetcher, clock = service()
    first = catalogue.call("get_course", CourseArguments(course_id="101"))
    assert first["provenance"]["source_updated_at"] is None  # createdAt is not a verified update time
    clock[0] = 301
    fetcher.fetch = lambda path: {"unexpected": "private-looking source value"}
    result = Application(SyntheticSource(), catalogue).call("get_course", {"course_id": "101"})
    assert result.is_error and result.structured_content["error"]["code"] == "SOURCE_CHANGED"
    assert "private-looking" not in str(result)
    assert "/api/course/101" not in catalogue.cache

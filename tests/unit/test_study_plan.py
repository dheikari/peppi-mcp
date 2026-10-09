import asyncio
from datetime import timedelta

import pytest

from peppi_mcp.adapters.lapland_study_plan import normalize_plan, parse_listing, version_key
from peppi_mcp.errors import PeppiError
from peppi_mcp.models import NoArguments
from peppi_mcp.server import LiveApplication
from peppi_mcp.services.study_progress import study_progress
from peppi_mcp.study_plan_models import PlanArguments, ProgressArguments
from tests.plan_fixtures import listing, metadata, plan, projection, version_url
from tests.unit.test_live_service import Browser, connected


class PlanBrowser(Browser):
    def __init__(self):
        super().__init__()
        self.plan_reads = 0
        self.change_plan = False
        self.wrong_right = False

    async def list_plans(self, right, identity):
        return listing(right.key)

    async def read_plan(self, right, identity, key):
        self.plan_reads += 1
        await asyncio.sleep(self.wait)
        result = plan("wrong-right" if self.wrong_right else right.key)
        if key != "501":
            raise PeppiError("PLAN_NOT_FOUND", "Fictional unavailable version")
        if self.change_plan and self.plan_reads > 1:
            result = result.model_copy(update={"id":"changed-plan"})
        return result


def test_explicit_recorded_version_and_source_credit_ranges():
    result = plan()
    assert result.listing.current_plan_id == "501"
    assert [v.source_status for v in result.listing.versions] == ["DRAFT", "Hyväksytty"]
    assert len(result.nodes) == 4 and result.source_completed_credits == result.source_total_credits
    assert result.nodes[1].parent_id == result.nodes[0].id


def test_draft_menu_label_does_not_require_the_optional_edit_hint():
    raw = metadata()
    raw["versions"][0]["label"] = "2 DRAFT"
    result = parse_listing(raw,expected_right="right-a",retrieved_at=listing().retrieved_at)
    assert result.versions[0].source_status == "DRAFT"


@pytest.mark.parametrize("change", ["wrong_right","wrong_version","duplicate_version","unknown_status","external_url","action_url"])
def test_version_discovery_refuses_ambiguity_or_nonread_urls(change):
    raw = metadata()
    if change == "wrong_right": raw["study_right_key"] = "right-b"
    elif change == "wrong_version": raw["header"] = raw["header"].replace(": 2", ": 3")
    elif change == "duplicate_version": raw["versions"].append(raw["versions"][0])
    elif change == "unknown_status": raw["versions"][0]["label"] = "2 UNKNOWN"
    elif change == "external_url": raw["versions"][0]["url"] = version_url().replace("https://", "https://evil.invalid/")
    else: raw["versions"][0]["url"] = version_url().replace("p_p_lifecycle=0", "p_p_lifecycle=1")
    with pytest.raises(PeppiError):
        parse_listing(raw, expected_right="right-a", retrieved_at=listing().retrieved_at)


@pytest.mark.parametrize("change", ["pending","invalid","wrong_plan","duplicate_node","missing_parent","cycle","count","scope","credits","range","unknown_kind"])
def test_incomplete_or_changed_plan_cannot_be_returned_as_complete(change):
    raw = projection()
    if change in {"pending","invalid"}: raw[change] = True
    elif change == "wrong_plan": raw["nodes"][1]["plan_key"] = "502"
    elif change == "duplicate_node": raw["nodes"][1]["id"] = "1"
    elif change == "missing_parent": raw["nodes"][1]["parent_id"] = "99"
    elif change == "cycle": raw["nodes"][0]["parent_id"] = "2"
    elif change == "count": raw["node_count"] += 1
    elif change == "scope": raw["scope"] = "HOPSin laajuus 2 / 3 op"
    elif change == "credits": raw["nodes"][1]["credits"] = "nan op"
    elif change == "range": raw["nodes"][1]["credits"] = "3 - 1 op"
    else: raw["nodes"][1]["source_kind"] = "NEW_SOURCE_KIND"
    with pytest.raises(PeppiError): normalize_plan(raw, listing())


@pytest.mark.parametrize("field,issue", [("total","headline_total"),("group","inside_plan_groups")])
def test_conflicting_hops_totals_are_preserved_and_never_certified(field, issue):
    async def run():
        raw = projection()
        if field == "total": raw["total"] = "2"
        else: raw["nodes"][0]["summary"] = raw["nodes"][0]["summary"].replace("1,5", "2")
        result = normalize_plan(raw, listing())
        assert result.reconciliation_issues == (issue,)
        browser = Browser()
        transcript = await browser.read(browser.identity.rights[0], browser.identity)
        progress = study_progress(result, transcript)
        assert progress["status"] == "unresolved" and progress["source_reconciliation_issues"] == [issue]
        assert progress["graduation_eligibility"] is None
    asyncio.run(run())


def test_outside_studies_and_variable_elective_ranges_are_not_degree_requirements():
    raw = projection()
    raw["nodes"][0].update(summary="1,5 op suorituksia<br/>3 - 5 op ulkopuolinen laajuus<br/>")
    raw["summary"] = raw["summary"].replace("<br/>0 op hopsin", "<br/>1,5 op hopsin")
    result = normalize_plan(raw, listing())
    assert all(n.outside_plan for n in result.nodes)
    assert result.nodes[0].planned_credits.maximum == 5


def test_progress_matches_codes_but_never_claims_group_rules_or_eligibility():
    async def run():
        browser = Browser()
        transcript = await browser.read(browser.identity.rights[0], browser.identity)
        result = study_progress(plan(), transcript)
        assert result["status"] == "source_credits_reconciled"
        assert len(result["requirements"]) == 3 and not result["unmapped_achievements"]
        assert result["groups"][0]["credits_reconciled"]
        assert result["groups"][0]["requirement_satisfaction"] == "unresolved"
        assert result["degree_requirements_satisfied"] is None
        assert result["graduation_eligibility"] is None
    asyncio.run(run())


@pytest.mark.parametrize("change", ["same_title_other_code","duplicate_allocation","credit_conflict","grade_conflict","status_conflict","transfer","module","replacement","agreement"])
def test_ambiguous_progress_is_explicit_and_never_title_matched(change):
    async def run():
        browser = Browser()
        transcript = await browser.read(browser.identity.rights[0], browser.identity)
        value = plan()
        raw = projection()
        if change == "same_title_other_code": raw["nodes"][1]["course_code"] = "OTHER"
        elif change == "duplicate_allocation": raw["nodes"][1]["course_code"] = "TEST1"
        elif change == "credit_conflict": raw["nodes"][1]["credits"] = "1 op"
        elif change == "grade_conflict": raw["nodes"][1]["grade"] = "4"
        elif change == "status_conflict": raw["nodes"][1]["source_status"] = "Ei arvioitu"
        elif change == "agreement": raw["nodes"][1]["source_relation"] = "study_agreement"
        else:
            updates = {"kind":change} if change != "replacement" else {"replaces_ids":("unknown",)}
            transcript = transcript.model_copy(update={"achievements":(transcript.achievements[0].model_copy(update=updates),*transcript.achievements[1:])})
        result = study_progress(normalize_plan(raw, value.listing), transcript)
        assert result["status"] == "unresolved" and result["issues"]
        assert result["unmapped_achievements"] and not result["equivalences_applied"]
    asyncio.run(run())


def test_plan_ids_are_connection_and_right_bound_and_progress_rechecks_source():
    async def run():
        service, browser, right = await connected(PlanBrowser())
        args = PlanArguments(study_right_id=right)
        choices, _ = await service.call("get_study_plan", args)
        assert choices["selection_required"] and choices["plan"] is None
        key = choices["current_plan_id"]
        result, _ = await service.call("get_study_plan", args.model_copy(update={"plan_id":key}))
        assert len(result["plan"]["nodes"]) == 4
        assert result["plan"]["nodes"][1]["parent_id"] == result["plan"]["nodes"][0]["id"]
        assert result["provenance"]["source_url"].endswith("/hops")
        progress, _ = await service.call("get_study_progress", ProgressArguments(study_right_id=right,plan_id=key))
        assert progress["progress"]["status"] == "source_credits_reconciled" and browser.plan_reads == 3
        assert progress["transcript_provenance"]["source_url"].endswith("/suoritusote")
        with pytest.raises(PeppiError) as error:
            await service.call("get_study_plan", PlanArguments(study_right_id=service._id("right-b"),plan_id=key))
        assert error.value.code == "PLAN_NOT_FOUND"
        await service.call("disconnect_personal", NoArguments())
        assert not service._plans
    asyncio.run(run())


@pytest.mark.parametrize("failure", ["source_changed","wrong_right","expiry","timeout"])
def test_progress_rejects_changes_and_session_failures(failure):
    async def run():
        service, browser, right = await connected(PlanBrowser())
        choices, _ = await service.call("get_study_plan", PlanArguments(study_right_id=right))
        if failure == "source_changed": browser.change_plan = True
        elif failure == "wrong_right": browser.wrong_right = True
        elif failure == "expiry": browser.error = PeppiError("SIGN_IN_NEEDED", "Expired")
        else: browser.wait, service.deadline = 10, .001
        with pytest.raises(PeppiError) as error:
            await service.call("get_study_progress", ProgressArguments(study_right_id=right,plan_id=choices["current_plan_id"]))
        assert error.value.code == {"source_changed":"PLAN_CHANGED","wrong_right":"STUDY_CONTEXT_CHANGED","expiry":"SESSION_EXPIRED","timeout":"PERSONAL_READ_TIMEOUT"}[failure]
        if failure != "source_changed": assert not service._plans and service.browser is None
    asyncio.run(run())


def test_live_schema_and_missing_plan_selection_boundary():
    async def run():
        service, _, right = await connected(PlanBrowser())
        app = LiveApplication(service)
        result = await app.call("get_study_progress", {"study_right_id":right})
        assert result.structured_content["error"]["code"] == "INVALID_ARGUMENT"
        result = await app.call("get_study_plan", {"study_right_id":right,"plan_id":"arbitrary"})
        assert result.structured_content["error"]["code"] == "PLAN_NOT_FOUND"
        status = (await app.call("get_connection_status", {})).structured_content["data"]
        assert status["capabilities"]["get_study_plan"] == "experimental_live_hops_read"
    asyncio.run(run())


def test_parser_diagnostic_names_a_field_without_echoing_the_private_value():
    raw = projection()
    raw["nodes"][1]["course_code"] = "PRIVATE/STUDENT/UNSUPPORTED"
    with pytest.raises(PeppiError) as error:
        normalize_plan(raw, listing())
    assert "course_code" in error.value.message and "PRIVATE" not in error.value.message


def test_partial_plan_provenance_survives_the_live_tool_boundary():
    async def run():
        service, browser, right = await connected(PlanBrowser())
        choices, _ = await service.call("get_study_plan", PlanArguments(study_right_id=right))
        read = browser.read_plan
        async def partial(*args):
            value = await read(*args)
            return value.model_copy(update={"reconciliation_issues":("inside_plan_groups",)})
        browser.read_plan = partial
        args = PlanArguments(study_right_id=right,plan_id=choices["current_plan_id"])
        result, _ = await service.call("get_study_plan", args)
        assert result["provenance"]["completeness"] == "partial"
        assert result["plan"]["source_reconciliation_issues"] == ["inside_plan_groups"]
        result, _ = await service.call("get_study_progress", ProgressArguments(**args.model_dump()))
        assert result["progress"]["status"] == "unresolved"
        assert result["provenance"]["completeness"] == "partial"
    asyncio.run(run())

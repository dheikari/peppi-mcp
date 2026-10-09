import asyncio
import json
from decimal import Decimal

import pytest

from peppi_mcp.errors import PeppiError
from peppi_mcp.models import NoArguments, ScopedArguments
from peppi_mcp.services.assessment import assess
from peppi_mcp.services.study_progress import study_progress
from peppi_mcp.worker_protocol import decode, validate_reply
from tests.plan_fixtures import plan, projection, listing
from peppi_mcp.adapters.lapland_study_plan import normalize_plan
from tests.unit.test_live_service import Browser, connected


def test_bounded_queue_cancel_disconnect_and_responsive_status():
    async def run():
        service, browser, right = await connected()
        service.queue_timeout = .04
        browser.wait = 10
        args = ScopedArguments(study_right_id=right)
        active = asyncio.create_task(service.call("get_credit_summary", args))
        await asyncio.sleep(.01)
        waiting = [asyncio.create_task(service.call("get_credit_summary", args)) for _ in range(4)]
        await asyncio.sleep(.001)
        status, _ = await asyncio.wait_for(service.call("get_connection_status", NoArguments()), .05)
        assert status["operation_state"] == "busy" and status["queued_requests"] == 4
        with pytest.raises(PeppiError) as error:
            await service.call("get_credit_summary", args)
        assert error.value.code == "PERSONAL_BUSY"
        waiting[0].cancel()
        with pytest.raises(asyncio.CancelledError): await waiting[0]
        for task in waiting[1:]:
            with pytest.raises(PeppiError) as error: await task
            assert error.value.code == "PERSONAL_BUSY"
        assert not active.done() and browser.closed == 0 and not service._waiters
        waiting = asyncio.create_task(service.call("get_credit_summary", args))
        await asyncio.sleep(.001)
        await asyncio.wait_for(service.call("disconnect_personal", NoArguments()), .2)
        for task in (active, waiting):
            with pytest.raises(PeppiError) as error: await task
            assert error.value.code == "SIGN_IN_NEEDED"
        assert browser.closed == 1 and not service._pages and not service._plans
    asyncio.run(run())


def test_late_reply_cannot_reanimate_a_disconnected_identity():
    async def run():
        service, browser, right = await connected()
        started, release = asyncio.Event(), asyncio.Event()
        original = browser.check
        async def late():
            started.set()
            try: await release.wait()
            except asyncio.CancelledError: await release.wait()
            return await original()
        browser.check = late
        active = asyncio.create_task(service.call("get_credit_summary", ScopedArguments(study_right_id=right)))
        await started.wait()
        await service.close()
        release.set()
        with pytest.raises(PeppiError): await active
        assert service.identity is None and service.browser is None and service.state == "signed_out"
    asyncio.run(run())


def test_disconnect_invalidates_a_granted_waiter_before_it_resumes():
    async def run():
        service, _, _ = await connected()
        first = await service._acquire()
        waiting = asyncio.create_task(service._acquire())
        await asyncio.sleep(0)
        service._release(first)
        # The permit has moved, but the waiting caller has not resumed yet.
        await service.close()
        with pytest.raises(PeppiError) as error: await waiting
        assert error.value.code == "SIGN_IN_NEEDED" and service._owner is None
    asyncio.run(run())


def test_disconnect_after_read_completion_still_prevents_delivery():
    async def run():
        service, _, right = await connected()
        operation = service._run
        async def complete_then_disconnect(*args):
            result = await operation(*args)
            await service.close()
            return result
        service._run = complete_then_disconnect
        with pytest.raises(PeppiError) as error:
            await service.call("get_credit_summary",ScopedArguments(study_right_id=right))
        assert error.value.code == "SIGN_IN_NEEDED" and service.identity is None
    asyncio.run(run())


def test_recoverable_schema_errors_preserve_session_but_throttling_sends_no_request():
    async def run():
        now = [1.0]
        service, browser, right = await connected(clock=lambda: now[0])
        args = ScopedArguments(study_right_id=right)
        browser.error = PeppiError("PERSONAL_VIEW_INVALID", "Fictional schema changed")
        with pytest.raises(PeppiError): await service.call("get_credit_summary", args)
        assert service.browser is browser and browser.closed == 0
        browser.error = PeppiError("RATE_LIMITED", "Pause", retryable=True, retry_after_seconds=10)
        with pytest.raises(PeppiError): await service.call("get_credit_summary", args)
        checks = browser.checks
        browser.error = None
        with pytest.raises(PeppiError) as error: await service.call("get_credit_summary", args)
        assert error.value.code == "RATE_LIMITED" and browser.checks == checks
        now[0] += 11
        assert (await service.call("get_credit_summary", args))[0]["total_credits"] == "1.5"
    asyncio.run(run())


def test_cleanup_failure_is_visible_and_never_returns_records():
    async def run():
        service, browser, _ = await connected()
        async def fail(): raise RuntimeError("PRIVATE_SECRET")
        browser.close = fail
        result, _ = await service.call("disconnect_personal", NoArguments())
        assert result["cleanup_pending"] and result["personal_connection"] == "unavailable"
        assert "PRIVATE_SECRET" not in json.dumps(result) and service.identity is None
    asyncio.run(run())


def test_discrepancy_assessment_preserves_source_conflict_despite_arithmetic_explanation():
    async def run():
        browser = Browser()
        transcript = await browser.read(browser.identity.rights[0], browser.identity)
        raw = projection()
        # The absent course accounts numerically for the group/sidebar difference,
        # but cannot reconcile contradictory source statements or prove allocation.
        raw["nodes"].pop()
        raw["node_count"] -= 1
        raw["nodes"][0]["summary"] = raw["nodes"][0]["summary"].replace("1,5", "1")
        value = normalize_plan(raw, listing())
        progress = study_progress(value, transcript)
        result = assess(value, progress, {n.id:"opaque:"+n.id for n in value.nodes})
        assert result.source_consistency == "conflicting" and result.comparison_status == "unresolved"
        conflict = next(d for d in result.discrepancies if d.code == "inside_plan_groups")
        assert conflict.difference == Decimal("-0.5")
        assert progress["unmapped_achievements"][0]["credits"] == "0.5"
        assert "outside_plan" not in progress["unmapped_achievements"][0]
        assert all(d.node_id is None or d.node_id.startswith("opaque:") for d in result.discrepancies)
        assert "Partial" in result.summary and result.limitations
    asyncio.run(run())


@pytest.mark.parametrize("credits,delta", [("1 op",Decimal("-0.5")),("0 - 1 op",None)])
def test_course_credit_discrepancy_preserves_exact_values_and_ranges(credits,delta):
    async def run():
        browser = Browser()
        transcript = await browser.read(browser.identity.rights[0],browser.identity)
        raw = projection()
        raw["nodes"][1]["credits"] = credits
        value = normalize_plan(raw,listing())
        result = assess(value,study_progress(value,transcript),{n.id:"opaque:"+n.id for n in value.nodes})
        discrepancy = next(d for d in result.discrepancies if d.code == "completed_credits_disagree_or_have_a_range")
        assert discrepancy.difference == delta and discrepancy.node_id.startswith("opaque:")
        assert discrepancy.quantities[0].value == Decimal("0.5")
        assert len(discrepancy.quantities) == (2 if delta is not None else 3)
    asyncio.run(run())


@pytest.mark.parametrize("line", [b'',b'{}',b'[]\n',b'{"ok":true,"ok":false}\n',b'{"x":NaN}\n',b'\xff\n'])
def test_worker_rejects_unframed_ambiguous_or_invalid_json(line):
    with pytest.raises((ValueError, UnicodeError)): decode(line, 100)


@pytest.mark.parametrize("change", ["id", "action", "ok", "extra", "data", "unknown_error"])
def test_worker_rejects_unexpected_or_late_envelopes(change):
    request = {"id":1,"action":"check"}
    reply = {**request,"ok":True,"data":{}}
    if change == "id": reply["id"] = 2
    elif change == "action": reply["action"] = "open"
    elif change == "ok": reply["ok"] = "true"
    elif change == "extra": reply["secret"] = "PRIVATE_SECRET"
    elif change == "data": reply["data"] = []
    else: reply = {**request,"ok":False,"code":"SECRET","message":"PRIVATE_SECRET","retryable":False,"retry_after_seconds":None}
    with pytest.raises(ValueError): validate_reply(reply, request)

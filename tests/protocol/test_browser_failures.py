import asyncio
import json
import os
import sys
from urllib.parse import parse_qs, urlsplit

import pytest
from mcp import Client
from mcp.client.stdio import StdioServerParameters

from tests.local_peppi import local_peppi, PLAN_PATH, version_url
from peppi_mcp.adapters.lapland_browser import TRANSCRIPT_PATH
from peppi_mcp.adapters.lapland_study_plan import PREFIX
from peppi_mcp.worker_protocol import SAFE_ERRORS

pytestmark = pytest.mark.usefixtures("browser_case")


def parameters(origin, appdata=None):
    return StdioServerParameters(command=sys.executable, args=["-m","tests.browser_fixture_server","--mode","live","--browser",os.environ.get("PEPPI_TEST_BROWSER", "firefox")],
                                env={**os.environ,"PEPPI_FIXTURE_ORIGIN":origin,"PYTHONUTF8":"1",**({"LOCALAPPDATA":str(appdata)} if appdata else {})})


async def call(client, name, args=None, error=None):
    response = await client.call_tool(name, args or {})
    body = response.structured_content
    assert json.loads(response.content[0].text) == body
    if response.is_error != (error is not None):
        code = body.get("error", {}).get("code")
        known = set(SAFE_ERRORS) | {"PERSONAL_READ_TIMEOUT", "PERSONAL_READ_FAILED",
            "PERSONAL_BUSY", "PERSONAL_CLEANUP_PENDING", "SESSION_EXPIRED"}
        code = code if code in known else "UNEXPECTED_ERROR" if response.is_error else "UNEXPECTED_SUCCESS"
        raise AssertionError("Unexpected tool outcome: " + name + ": " + code)
    if error:
        assert body["error"]["code"] == error
        assert "PRIVATE_SECRET" not in json.dumps(body)
        return body
    assert body["ok"]
    return body["data"]


async def connect(client):
    status = await call(client, "get_connection_status")
    assert status["personal_browser"] == os.environ.get("PEPPI_TEST_BROWSER", "firefox")
    assert (await call(client,"connect_personal"))["personal_connection"] == "awaiting_login"
    assert (await call(client,"connect_personal"))["personal_connection"] == "connected"
    return (await call(client,"list_study_rights"))["items"]


def test_shipped_worker_maps_two_rights_versions_and_scoped_discrepancies():
    async def run(origin, state):
        async with Client(parameters(origin), read_timeout_seconds=45) as client:
            rights = await connect(client)
            for right in rights:
                choices = await call(client,"get_study_plan",{"study_right_id":right["id"]})
                for version in choices["available_plans"]:
                    selected = {"study_right_id":right["id"],"plan_id":version["id"]}
                    tree = await call(client,"get_study_plan", selected)
                    assert next(iter(tree)) == "assessment" and len(tree["plan"]["nodes"]) == 4
                    assert "PRIVATE_ASSESSOR" not in json.dumps(tree)
                    progress = await call(client,"get_study_progress", selected)
                    assert progress["assessment"]["comparison_status"] == "reconciled"
                    assert progress["progress"]["graduation_eligibility"] is None
                state["fault"] = "conflict"
                partial = await call(client,"get_study_progress", selected)
                assert partial["assessment"]["source_consistency"] == "conflicting"
                assert partial["provenance"]["completeness"] == "partial"
                state["fault"] = ""
            state["fault"] = "signed_out"
            await call(client,"get_study_progress",selected,error="SESSION_EXPIRED")
            status = await call(client,"get_connection_status")
            assert status["personal_connection"] == "expired" and not status["cleanup_pending"]
        for method, path in state["requests"]:
            parsed = urlsplit(path)
            if method == "POST":
                assert parsed.path == "/delegate/studyentitlements"
                assert parse_qs(parsed.query) in ({"groupByCollection":["true"]},
                    {"selectedEntitlementId":["101"]},{"selectedEntitlementId":["102"]})
            else:
                assert parsed.path in {"/","/favicon.ico",TRANSCRIPT_PATH,PLAN_PATH}
                if parsed.query:
                    assert parsed.path == PLAN_PATH
                    assert parse_qs(parsed.query) in [parse_qs(urlsplit(version_url(origin,k)).query) for k in ("501","502","601")]
    with local_peppi() as (origin,state): asyncio.run(run(origin,state))


@pytest.mark.parametrize("fault,code,closed", [
    ("signed_out","SESSION_EXPIRED",True), ("redirect","SESSION_EXPIRED",True),
    ("denied","ACCESS_DENIED",True), ("account","STUDY_CONTEXT_CHANGED",True),
    ("malformed","PERSONAL_VIEW_INVALID",False), ("oversized","SOURCE_TOO_LARGE",False),
    ("rate_limited","RATE_LIMITED",False), ("hidden","PERSONAL_VIEW_INCOMPLETE",False),
    ("count","PERSONAL_VIEW_INCOMPLETE",False), ("missing_zero","PERSONAL_VIEW_INVALID",False),
])
def test_source_faults_cross_actual_browser_worker_and_stdio(fault, code, closed):
    async def run(origin, state):
        async with Client(parameters(origin), read_timeout_seconds=45) as client:
            right = (await connect(client))[0]["id"]
            first = await call(client,"list_achievements",{"study_right_id":right,"limit":1})
            if fault == "account": state["account"] = "202"
            else: state["fault"] = fault
            await call(client,"get_credit_summary",{"study_right_id":right},error=code)
            status = await call(client,"get_connection_status")
            assert (status["read_mechanism"] is None) == closed
            if closed:
                await call(client,"list_achievements",{"study_right_id":right,"limit":1,"cursor":first["next_cursor"]},error="SIGN_IN_NEEDED")
            await call(client,"disconnect_personal")
    with local_peppi() as (origin,state): asyncio.run(run(origin,state))


@pytest.mark.parametrize("fault,code", [("wrong_right","STUDY_CONTEXT_CHANGED"),
    ("wrong_version","STUDY_CONTEXT_CHANGED"),("removed","PERSONAL_VIEW_INVALID"),
    ("loading","PERSONAL_VIEW_INCOMPLETE"),("plan_changed","PLAN_CHANGED")])
def test_hops_context_and_stability_failures_cross_stdio(fault, code):
    async def run(origin,state):
        async with Client(parameters(origin), read_timeout_seconds=45) as client:
            right = (await connect(client))[0]["id"]
            choices = await call(client,"get_study_plan",{"study_right_id":right})
            selected = {"study_right_id":right,"plan_id":choices["available_plans"][1]["id"]}
            state.update(fault=fault,hops_reads=0)
            await call(client,"get_study_progress",selected,error=code)
            await call(client,"disconnect_personal")
    with local_peppi() as (origin,state): asyncio.run(run(origin,state))


def test_stdio_disconnect_preempts_browser_read_and_clears_queue():
    async def run(origin,state):
        async with Client(parameters(origin), read_timeout_seconds=45) as client:
            right = (await connect(client))[0]["id"]
            choices = await call(client,"get_study_plan",{"study_right_id":right})
            selected = {"study_right_id":right,"plan_id":choices["current_plan_id"]}
            state["fault"] = "loading"
            active = asyncio.create_task(call(client,"get_study_plan",selected,error="SIGN_IN_NEEDED"))
            await asyncio.sleep(.2)
            waiting = asyncio.create_task(call(client,"get_credit_summary",{"study_right_id":right},error="SIGN_IN_NEEDED"))
            await asyncio.sleep(.1)
            status = await asyncio.wait_for(call(client,"get_connection_status"), 2)
            assert status["operation_state"] == "busy" and status["queued_requests"] == 1
            await asyncio.wait_for(call(client,"disconnect_personal"), 10)
            await asyncio.gather(active,waiting)
            assert not (await call(client,"get_connection_status"))["cleanup_pending"]
    with local_peppi() as (origin,state): asyncio.run(run(origin,state))


def test_stdio_cancellation_and_client_eof_close_owned_profiles(tmp_path):
    async def run(origin,state):
        background = None
        try:
            async with Client(parameters(origin,tmp_path), read_timeout_seconds=45) as client:
                right = (await connect(client))[0]["id"]
                choices = await call(client,"get_study_plan",{"study_right_id":right})
                selected = {"study_right_id":right,"plan_id":choices["current_plan_id"]}
                state["fault"] = "loading"
                active = asyncio.create_task(client.call_tool("get_study_plan",selected))
                await asyncio.sleep(.3)
                queued = asyncio.create_task(client.call_tool("get_credit_summary",{"study_right_id":right}))
                await asyncio.sleep(.1)
                queued.cancel()
                with pytest.raises(asyncio.CancelledError): await queued
                await asyncio.sleep(.1)
                status = await call(client,"get_connection_status")
                assert status["operation_state"]=="busy" and status["queued_requests"]==0
                active.cancel()
                with pytest.raises(asyncio.CancelledError): await active
                for _ in range(50):
                    status = await call(client,"get_connection_status")
                    if status["operation_state"]=="idle": break
                    await asyncio.sleep(.1)
                assert status["personal_connection"]=="signed_out" and not status["cleanup_pending"]
                state["fault"] = ""
                right = (await connect(client))[0]["id"]
                choices = await call(client,"get_study_plan",{"study_right_id":right})
                state["fault"] = "loading"
                background = asyncio.create_task(client.call_tool("get_study_plan",{"study_right_id":right,"plan_id":choices["current_plan_id"]}))
                await asyncio.sleep(.2)
                # Leave the client while the server owns an active browser call.
        finally:
            if background:
                background.cancel()
                await asyncio.gather(background,return_exceptions=True)
        assert not list((tmp_path/"peppi-mcp"/"runtime").glob("run-*"))
    with local_peppi() as (origin,state): asyncio.run(run(origin,state))


@pytest.mark.parametrize("change_at", [1, 3, 5])
def test_account_change_before_during_or_after_acquisition_never_returns_records(change_at):
    async def run(origin,state):
        async with Client(parameters(origin), read_timeout_seconds=45) as client:
            right = (await connect(client))[0]["id"]
            state.update(transcript_reads=0,change_account_at=change_at)
            await call(client,"list_achievements",{"study_right_id":right},error="STUDY_CONTEXT_CHANGED")
            status = await call(client,"get_connection_status")
            assert status["read_mechanism"] is None and not status["cleanup_pending"]
            new_right = (await connect(client))[0]["id"]
            assert new_right != right  # Same displayed name, different verified account/session.
            await call(client,"get_credit_summary",{"study_right_id":right},error="STUDY_RIGHT_NOT_FOUND")
            await call(client,"disconnect_personal")
    with local_peppi() as (origin,state): asyncio.run(run(origin,state))


def test_real_queue_capacity_expiry_and_active_deadline(tmp_path):
    async def run(origin,state):
        async with Client(parameters(origin,tmp_path), read_timeout_seconds=45) as client:
            right = (await connect(client))[0]["id"]
            args = {"study_right_id":right}
            # Each fetch is below its 12-second timeout; their combined time
            # exceeds the service deadline. No production timeout is shortened.
            state["delay"] = 9
            started = asyncio.get_running_loop().time()
            active = asyncio.create_task(call(client,"get_credit_summary",args,error="PERSONAL_READ_TIMEOUT"))
            await asyncio.sleep(.2)
            waiting = [asyncio.create_task(call(client,"get_credit_summary",args,error="PERSONAL_BUSY")) for _ in range(4)]
            await asyncio.sleep(.2)
            status = await asyncio.wait_for(call(client,"get_connection_status"),2)
            assert status["queued_requests"] == 4 and status["active_stage"] == "fresh account verification"
            await asyncio.wait_for(call(client,"get_credit_summary",args,error="PERSONAL_BUSY"),2)
            await asyncio.wait_for(asyncio.gather(*waiting),6)
            assert not active.done()
            assert (await call(client,"get_connection_status"))["queued_requests"] == 0
            await active
            elapsed = asyncio.get_running_loop().time() - started
            assert 29 <= elapsed < 40  # 30 seconds active, separately bounded cleanup.
            status = await call(client,"get_connection_status")
            assert status["read_mechanism"] is None and not status["cleanup_pending"]
        assert not list((tmp_path/"peppi-mcp"/"runtime").glob("run-*"))
    with local_peppi() as (origin,state): asyncio.run(run(origin,state))


def test_explicit_zero_and_new_acquisitions_through_browser_stdio():
    async def run(origin,state):
        async with Client(parameters(origin), read_timeout_seconds=45) as client:
            right = (await connect(client))[0]["id"]
            args = {"study_right_id":right,"limit":1}
            first = await call(client,"list_achievements",args)
            second = await call(client,"list_achievements",{**args,"cursor":first["next_cursor"]})
            assert first["provenance"]["retrieved_at"] == second["provenance"]["retrieved_at"]
            fresh = await call(client,"list_achievements",args)
            assert fresh["provenance"]["retrieved_at"] > first["provenance"]["retrieved_at"]
            state["fault"] = "zero"
            empty = await call(client,"list_achievements",args)
            assert empty["matching_records"] == 0 and empty["items"] == []
            assert (await call(client,"get_credit_summary",{"study_right_id":right}))["total_credits"] == "0"
            await call(client,"disconnect_personal")
    with local_peppi() as (origin,state): asyncio.run(run(origin,state))

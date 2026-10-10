import asyncio
from contextlib import ExitStack
import json
import os
import sys
import warnings
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


async def call(client, name, args=None, error=None, *, startup_record=None):
    response = await client.call_tool(name, args or {})
    body = response.structured_content
    assert json.loads(response.content[0].text) == body
    if response.is_error != (error is not None):
        code = body.get("error", {}).get("code")
        known = set(SAFE_ERRORS) | {"PERSONAL_READ_TIMEOUT", "PERSONAL_READ_FAILED",
            "PERSONAL_BUSY", "PERSONAL_CLEANUP_PENDING", "SESSION_EXPIRED"}
        code = code if code in known else "UNEXPECTED_ERROR" if response.is_error else "UNEXPECTED_SUCCESS"
        message = "Unexpected tool outcome: " + name + ": " + code
        if startup_record is not None:
            message += "; startup stage: " + startup_stage(startup_record)
        raise AssertionError(message)
    if error:
        assert body["error"]["code"] == error
        secret_safe = "PRIVATE_SECRET" not in json.dumps(body)
        assert secret_safe, "Tool error exposed a fictional secret"
        return body
    assert body["ok"]
    return body["data"]


def startup_stage(path):
    try:
        with path.open("rb") as stream:
            raw = stream.read(1025)
        if len(raw) > 1024:
            return "unrecorded"
        data = json.loads(raw)
        if set(data) == {"stage"} and data["stage"] in {
                "worker launch", "browser creation", "local source load", "ready"}:
            return data["stage"]
    except (OSError, ValueError, TypeError):
        pass
    return "unrecorded"


async def connect(client, startup_record=None):
    status = await call(client, "get_connection_status")
    assert status["personal_browser"] == os.environ.get("PEPPI_TEST_BROWSER", "firefox")
    assert (await call(client,"connect_personal", startup_record=startup_record))["personal_connection"] == "awaiting_login"
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
@pytest.mark.parametrize("cleanup_refused", [False, True])
def test_account_change_before_during_or_after_acquisition_never_returns_records(tmp_path, change_at, cleanup_refused):
    async def run(origin,state):
        from tests.protocol.test_cleanup_stdio import update, owned_handles, assert_owned_stopped
        settings = parameters(origin, tmp_path)
        record, diagnostic = tmp_path / "owned-processes.json", tmp_path / "cleanup-diagnostic.json"
        control, startup = tmp_path / "cleanup.json", tmp_path / "startup.json"
        settings.env.update(PEPPI_FIXTURE_PROCESS_RECORD=str(record),
            PEPPI_FIXTURE_CLEANUP_RECORD=str(diagnostic), PEPPI_FIXTURE_CLEANUP_CONTROL=str(control),
            PEPPI_FIXTURE_STARTUP_RECORD=str(startup))
        update(control, fail=False)
        root = tmp_path / "peppi-mcp" / "runtime"
        with ExitStack() as captured:
            async with Client(settings, read_timeout_seconds=45) as client:
                right = (await connect(client, startup))[0]["id"]
                owned = json.loads(record.read_text())
                profiles = list(root.glob("run-*"))
                assert len(profiles) == 1
                owner = json.loads((profiles[0] / "owner.json").read_text())
                handles = owned_handles(owned, owner["pid"])
                for handle in handles.values(): captured.callback(handle.Close)
                first = await call(client, "list_achievements", {"study_right_id":right, "limit":1})
                update(control, fail=cleanup_refused)
                state.update(transcript_reads=0,change_account_at=change_at)
                refused = await call(client,"list_achievements",{"study_right_id":right},error="STUDY_CONTEXT_CHANGED")
                no_records = "data" not in refused
                assert no_records, "Account-change refusal returned data"
                status = await call(client,"get_connection_status")
                assert status["read_mechanism"] is None and status["sign_in_needed"]
                # Authentication is discarded immediately; disposal can finish
                # later or retain a locked profile under the existing contract.
                async with asyncio.timeout(11):
                    while status["operation_state"] == "closing":
                        assert status["active_stage"] == "owned browser cleanup"
                        await asyncio.sleep(.02)
                        status = await call(client, "get_connection_status")
                assert_owned_stopped(owned, handles)
                if cleanup_refused:
                    assert status["cleanup_pending"], "Fictional file refusal was not retained"
                if status["cleanup_pending"]:
                    detail = json.loads(diagnostic.read_text()) if diagnostic.exists() else {}
                    assert detail.get("stage") == "profile removal", "Pending cleanup was not a profile refusal"
                    assert detail.get("error_type") in {"PermissionError", "OSError"}, "Unexpected cleanup failure category"
                    assert detail.get("winerror") is None or detail["winerror"] in {5, 32, 33, 145}, "Unexpected Windows cleanup error"
                    assert status["personal_connection"] == "unavailable"
                    assert json.loads((profiles[0] / "owner.json").read_text()) == owner
                    if cleanup_refused:
                        await call(client, "connect_personal", error="PERSONAL_CLEANUP_PENDING")
                        assert list(root.glob("run-*")) == profiles  # No replacement browser.
                await call(client, "list_achievements", {"study_right_id":right, "limit":1,
                    "cursor":first["next_cursor"]}, error="SIGN_IN_NEEDED")
                update(control, fail=False)
                status = await asyncio.wait_for(call(client,"disconnect_personal"), 11)
                assert not status["cleanup_pending"] and status["operation_state"] == "idle"
                assert status["personal_connection"] == "signed_out" and status["queued_requests"] == 0
                assert_owned_stopped(owned, handles)
                assert not list(root.glob("run-*"))  # Verified before EOF or a new browser.
                new_right = (await connect(client, startup))[0]["id"]
                assert new_right != right  # Same display name, different verified account/session.
                await call(client,"get_credit_summary",{"study_right_id":right},error="STUDY_RIGHT_NOT_FOUND")
                await call(client, "list_achievements", {"study_right_id":new_right, "limit":1,
                    "cursor":first["next_cursor"]}, error="INVALID_CURSOR")
                await call(client,"disconnect_personal")
        assert not list(root.glob("run-*"))
    with local_peppi() as (origin,state): asyncio.run(run(origin,state))


def test_real_queue_capacity_expiry_and_active_deadline(tmp_path):
    async def run(origin,state):
        from tests.protocol.test_cleanup_stdio import owned_handles, assert_owned_stopped
        settings = parameters(origin, tmp_path)
        record = tmp_path / "owned-processes.json"
        diagnostic = tmp_path / "cleanup-diagnostic.json"
        settings.env["PEPPI_FIXTURE_PROCESS_RECORD"] = str(record)
        settings.env["PEPPI_FIXTURE_CLEANUP_RECORD"] = str(diagnostic)
        root = tmp_path / "peppi-mcp" / "runtime"
        with ExitStack() as captured:
            async with Client(settings, read_timeout_seconds=45) as client:
                right = (await connect(client))[0]["id"]
                owned = json.loads(record.read_text())
                profiles = list(root.glob("run-*"))
                assert len(profiles) == 1
                owner = json.loads((profiles[0] / "owner.json").read_text())
                handles = owned_handles(owned, owner["pid"])
                for handle in handles.values():
                    captured.callback(handle.Close)
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
                assert 29 <= elapsed < 41  # 30 active + 10 cleanup + 1 stdio measurement margin.
                status = await call(client,"get_connection_status")
                assert status["read_mechanism"] is None and status["sign_in_needed"]
                assert status["personal_connection"] == "unavailable" and status["queued_requests"] == 0
                assert status["operation_state"] in {"closing", "idle"}
                if status["operation_state"] == "closing":
                    assert status["cleanup_pending"] and status["active_stage"] == "owned browser cleanup"
                pending = status["cleanup_pending"]
                refused = await client.call_tool("get_credit_summary", args)
                body = refused.structured_content
                assert json.loads(refused.content[0].text) == body
                no_records = "data" not in body
                assert refused.is_error and not body["ok"]
                assert no_records, "Refused read returned data"
                assert body["error"]["code"] in {"PERSONAL_BUSY", "SIGN_IN_NEEDED"}
                secret_safe = "PRIVATE_SECRET" not in json.dumps(body)
                assert secret_safe, "Refused read exposed a fictional secret"
                # Observe a live disposal task without resetting its budget or
                # retrying the read. An unfinished task must still fail this check.
                async with asyncio.timeout(11):
                    while status["operation_state"] == "closing":
                        status = await call(client, "get_connection_status")
                        await asyncio.sleep(.02)
                if pending or status["cleanup_pending"]:
                    detail = json.loads(diagnostic.read_text()) if diagnostic.exists() else {}
                    category = detail.get("error_type")
                    category = category if category in {"PermissionError", "FileNotFoundError", "OSError", "ValueError"} else "unclassified"
                    winerror = detail.get("winerror")
                    winerror = winerror if type(winerror) is int else None
                    warnings.warn("Bounded timeout cleanup pending: " + json.dumps({
                        "still_pending":status["cleanup_pending"], "profile_error":category,
                        "winerror":winerror}), RuntimeWarning)
                    if status["cleanup_pending"]:
                        assert detail.get("stage") == "profile removal", "Pending cleanup failure was not classified as profile removal"
                        assert category in {"PermissionError", "OSError"}, "Pending cleanup was not an allowed filesystem refusal"
                        assert winerror is None or winerror in {5, 32, 33, 145}, "Pending cleanup had an unexpected Windows error category"
                        assert_owned_stopped(owned, handles)
                        assert json.loads((profiles[0] / "owner.json").read_text()) == owner
                # A bounded attempt may retain disposal work. One explicit
                # disconnect joins it or retries; never retry reads until green.
                status = await asyncio.wait_for(call(client,"disconnect_personal"), 11)
                assert not status["cleanup_pending"] and status["operation_state"] == "idle"
                assert status["personal_connection"] == "signed_out" and status["queued_requests"] == 0
                await call(client, "get_credit_summary", args, error="SIGN_IN_NEEDED")
                assert_owned_stopped(owned, handles)
                assert not list(root.glob("run-*"))
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

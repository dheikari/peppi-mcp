"""Cleanup regressions through the shipped browser worker and MCP transport."""
import asyncio
import json
import subprocess
import threading
import pytest
from mcp import Client

from tests.local_peppi import local_peppi
from tests.protocol.test_browser_failures import parameters, call, connect

pytestmark = pytest.mark.usefixtures("browser_case")


def update(path, **state):
    temporary = path.with_suffix(".new")
    temporary.write_text(json.dumps(state))
    temporary.replace(path)


async def until(predicate, timeout=15):
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(.02)


def descendants(parent_pid):
    """Read a Windows process snapshot; never inspect command lines or stop PIDs."""
    import ctypes
    from ctypes import wintypes
    class Entry(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("usage", wintypes.DWORD),
            ("pid", wintypes.DWORD), ("heap", ctypes.c_size_t),
            ("module", wintypes.DWORD), ("threads", wintypes.DWORD),
            ("parent", wintypes.DWORD), ("priority", wintypes.LONG),
            ("flags", wintypes.DWORD), ("name", wintypes.WCHAR * 260)]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    for name in ("Process32FirstW", "Process32NextW"):
        function = getattr(kernel, name)
        function.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
        function.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)  # TH32CS_SNAPPROCESS
    if snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    rows = []
    try:
        entry = Entry()
        entry.size = ctypes.sizeof(entry)
        if not kernel.Process32FirstW(snapshot, ctypes.byref(entry)):
            raise ctypes.WinError(ctypes.get_last_error())
        while True:
            rows.append((entry.pid, entry.parent))
            if not kernel.Process32NextW(snapshot, ctypes.byref(entry)):
                if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES
                    raise ctypes.WinError(ctypes.get_last_error())
                break
    finally:
        kernel.CloseHandle(snapshot)
    owned = {parent_pid}
    while True:
        expanded = owned | {pid for pid, parent in rows if parent in owned}
        if expanded == owned:
            return owned - {parent_pid}
        owned = expanded


def owned_handles(record, parent_pid):
    """Capture query-only handles for the test server's verified descendants."""
    import win32api
    import win32job
    pids = descendants(parent_pid)
    assert len(pids) > 3  # Includes real browser subprocesses, beyond its main PID.
    assert {record[k] for k in ("driver_pid", "browser_pid", "worker_pid")} <= set(pids)
    handles = {}
    job = win32job.OpenJobObject(win32job.JOB_OBJECT_QUERY, False, record["fixture_job_name"])
    try:
        for pid in pids:
            try:
                handles[pid] = win32api.OpenProcess(0x1000, False, pid)
                if not win32job.IsProcessInJob(handles[pid], job):
                    handles.pop(pid).Close()
            except Exception as exc:
                if getattr(exc, "winerror", None) != 87:
                    raise
                # A transient owned child already exited before handle capture.
        assert {record[k] for k in ("driver_pid", "browser_pid", "worker_pid")} <= set(handles)
        return handles
    except BaseException:
        for handle in handles.values():
            handle.Close()
        raise
    finally:
        # Never retain an observer job handle across forced server termination:
        # kill-on-job-close must still be controlled by the actual server.
        job.Close()


def assert_owned_stopped(record, handles):
    """Verify captured identities and late children in the exact owned job."""
    import pywintypes
    import win32job
    import win32process
    assert all(win32process.GetExitCodeProcess(h) != 259 for h in handles.values()), "Owned process is still running"
    try:
        job = win32job.OpenJobObject(win32job.JOB_OBJECT_QUERY, False, record["fixture_job_name"])
    except pywintypes.error as exc:
        if exc.winerror != 2:  # Only ERROR_FILE_NOT_FOUND proves the named job is gone.
            raise
        return
    try:
        assert win32job.QueryInformationJobObject(job, win32job.JobObjectBasicAccountingInformation)["ActiveProcesses"] == 0, "Owned job still has active processes"
    finally:
        job.Close()


def test_failed_cleanup_blocks_new_browser_and_explicit_retry_recovers(tmp_path):
    async def run(origin, state):
        control = tmp_path / "cleanup.json"
        update(control, fail=True)
        settings = parameters(origin, tmp_path)
        settings.env["PEPPI_FIXTURE_CLEANUP_CONTROL"] = str(control)
        root = tmp_path / "peppi-mcp" / "runtime"
        async with Client(settings, read_timeout_seconds=45) as client:
            old_right = (await connect(client))[0]["id"]
            first = await call(client, "list_achievements", {"study_right_id":old_right, "limit":1})
            status = await call(client, "disconnect_personal")
            assert status["cleanup_pending"] and status["personal_connection"] == "unavailable"
            profiles = list(root.glob("run-*"))
            assert len(profiles) == 1 and (profiles[0] / "owner.json").exists()
            error = await call(client, "connect_personal", error="PERSONAL_CLEANUP_PENDING")
            assert error["error"]["retryable"]
            assert list(root.glob("run-*")) == profiles
            await call(client, "list_achievements", {"study_right_id":old_right,"limit":1,"cursor":first["next_cursor"]}, error="SIGN_IN_NEEDED")
            update(control, fail=False)
            status = await call(client, "disconnect_personal")
            assert not status["cleanup_pending"] and status["personal_connection"] == "signed_out"
            assert not list(root.glob("run-*"))
            new_right = (await connect(client))[0]["id"]
            assert new_right != old_right
            await call(client, "list_achievements", {"study_right_id":new_right,"limit":1,"cursor":first["next_cursor"]}, error="INVALID_CURSOR")
            fresh = await call(client, "list_achievements", {"study_right_id":new_right,"limit":1})
            assert fresh["provenance"]["retrieved_at"] > first["provenance"]["retrieved_at"]
            await call(client, "disconnect_personal")
        assert not list(root.glob("run-*"))
    with local_peppi() as (origin,state):
        asyncio.run(run(origin,state))


def test_cleanup_budget_cancelled_waiter_responsive_status_and_late_completion(tmp_path):
    async def run(origin, state):
        control = tmp_path / "cleanup.json"
        update(control, block=True)
        settings = parameters(origin, tmp_path)
        settings.env["PEPPI_FIXTURE_CLEANUP_CONTROL"] = str(control)
        root = tmp_path / "peppi-mcp" / "runtime"
        async with Client(settings, read_timeout_seconds=45) as client:
            await connect(client)
            first = asyncio.create_task(client.call_tool("disconnect_personal", {}))
            await until(lambda: control.with_suffix(".started").exists())
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first
            try:
                status = await asyncio.wait_for(call(client, "get_connection_status"), 2)
                assert status["operation_state"] == "closing"
                assert status["active_stage"] == "owned browser cleanup"
                await call(client, "connect_personal", error="PERSONAL_BUSY")
                assert len(list(root.glob("run-*"))) == 1
                # Join the same attempt: a second caller does not reset its budget.
                status = await asyncio.wait_for(call(client,"disconnect_personal"), 11)
                assert status["cleanup_pending"] and status["operation_state"] == "closing"
                await call(client, "connect_personal", error="PERSONAL_BUSY")
            finally:
                update(control, block=False)
            async with asyncio.timeout(5):
                while True:
                    status = await call(client, "get_connection_status")
                    if status["operation_state"] == "idle":
                        break
                    await asyncio.sleep(.02)
            assert not status["cleanup_pending"] and not list(root.glob("run-*"))
            await connect(client)
            await call(client, "disconnect_personal")
        assert not list(root.glob("run-*"))
    with local_peppi() as (origin,state):
        asyncio.run(run(origin,state))


@pytest.mark.parametrize("interruption", ["disconnect", "cancel", "eof"])
def test_shipped_worker_startup_interruption_crosses_stdio(tmp_path, interruption):
    async def run(origin, state):
        import win32api
        import win32process
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()
        state.update(startup_entered=entered, startup_release=release, startup_finished=finished)
        root = tmp_path / "peppi-mcp" / "runtime"
        settings = parameters(origin, tmp_path)
        record = tmp_path / "owned-processes.json"
        settings.env["PEPPI_FIXTURE_PROCESS_RECORD"] = str(record)
        opening = None
        handles, server_handle = {}, None
        try:
            async with Client(settings, read_timeout_seconds=45) as client:
                opening = asyncio.create_task(client.call_tool("connect_personal", {}))
                assert await asyncio.to_thread(entered.wait, 20)
                profiles = list(root.glob("run-*"))
                assert len(profiles) == 1 and (profiles[0] / "owner.json").exists()
                owner = json.loads((profiles[0] / "owner.json").read_text())
                server_handle = win32api.OpenProcess(0x1000, False, owner["pid"])
                owned = json.loads(record.read_text())
                handles = owned_handles(owned, owner["pid"])
                assert all(win32process.GetExitCodeProcess(handles[owned[k]]) == 259
                    for k in ("driver_pid", "browser_pid", "worker_pid"))
                status = await asyncio.wait_for(call(client, "get_connection_status"), 2)
                assert status["operation_state"] == "busy"
                if interruption == "disconnect":
                    closed = await asyncio.wait_for(call(client, "disconnect_personal"), 12)
                    response = await opening
                    body = response.structured_content
                    assert response.is_error and not body["ok"]
                    assert body["error"]["code"] == "SIGN_IN_NEEDED"
                    assert json.loads(response.content[0].text) == body
                    assert "PRIVATE_SECRET" not in json.dumps(body)
                    assert closed["personal_connection"] == "signed_out"
                    assert not closed["cleanup_pending"]
                elif interruption == "cancel":
                    opening.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await opening
                    async with asyncio.timeout(12):
                        while True:
                            status = await call(client, "get_connection_status")
                            if status["operation_state"] == "idle":
                                break
                            await asyncio.sleep(.02)
                    assert status["personal_connection"] == "signed_out"
                    assert not status["cleanup_pending"]
                # EOF exits the actual client transport during blocked startup.
                if interruption != "eof":
                    await call(client, "list_study_rights", error="SIGN_IN_NEEDED")
                    assert not list(root.glob("run-*"))
                    await until(lambda: all(win32process.GetExitCodeProcess(h) != 259 for h in handles.values()))
                    assert_owned_stopped(owned, handles)
            # Verify before releasing the fictional HTTP response. Exit code 0
            # distinguishes graceful EOF shutdown from a client force-termination.
            assert win32process.GetExitCodeProcess(server_handle) == 0
            await until(lambda: all(win32process.GetExitCodeProcess(h) != 259 for h in handles.values()))
            assert not list(root.glob("run-*"))
        finally:
            release.set()
            if opening is not None:
                opening.cancel()
                await asyncio.gather(opening, return_exceptions=True)
            if server_handle:
                server_handle.Close()
            for handle in handles.values():
                handle.Close()
        assert await asyncio.to_thread(finished.wait, 3)
        assert not list(root.glob("run-*"))
    with local_peppi() as (origin, state):
        asyncio.run(run(origin, state))


def test_forced_stdio_server_termination_stops_browser_and_recovers_profile(tmp_path):
    import win32process
    async def run(origin, state):
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()
        state.update(startup_entered=entered, startup_release=release, startup_finished=finished)
        settings = parameters(origin, tmp_path)
        record = tmp_path / "owned-processes.json"
        settings.env["PEPPI_FIXTURE_PROCESS_RECORD"] = str(record)
        root = tmp_path / "peppi-mcp" / "runtime"
        process = await asyncio.create_subprocess_exec(settings.command, *settings.args,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, env=settings.env,
            creationflags=subprocess.CREATE_NO_WINDOW)
        handles = {}
        async def send(message):
            process.stdin.write((json.dumps(message) + "\n").encode())
            await process.stdin.drain()
        try:
            await send({"jsonrpc":"2.0", "id":1, "method":"initialize", "params":{
                "protocolVersion":"2025-11-25", "capabilities":{},
                "clientInfo":{"name":"fictional-startup-interruption", "version":"1"}}})
            initialized = json.loads(await asyncio.wait_for(process.stdout.readline(), 10))
            assert initialized["id"] == 1 and "result" in initialized
            await send({"jsonrpc":"2.0", "method":"notifications/initialized"})
            await send({"jsonrpc":"2.0", "id":2, "method":"tools/call", "params":{
                "name":"connect_personal", "arguments":{}}})
            assert await asyncio.to_thread(entered.wait, 20)
            owned = json.loads(record.read_text())
            handles = owned_handles(owned, process.pid)
            assert all(win32process.GetExitCodeProcess(handles[owned[k]]) == 259
                for k in ("driver_pid", "browser_pid", "worker_pid"))
            profiles = list(root.glob("run-*"))
            assert len(profiles) == 1
            process.kill()
            await asyncio.wait_for(process.wait(), 5)
            await until(lambda: all(win32process.GetExitCodeProcess(h) != 259 for h in handles.values()), timeout=10)
            # No cleanup ran in the killed server. A fresh server must recover
            # the exact abandoned lease without starting/reusing authentication.
            assert profiles[0].exists() and (profiles[0] / "owner.json").exists()
            state.pop("startup_entered")
            release.set()
            assert await asyncio.to_thread(finished.wait, 3)
            request_count = len(state["requests"])
            async with Client(parameters(origin, tmp_path), read_timeout_seconds=45) as client:
                status = await call(client, "get_connection_status")
                assert status["personal_connection"] == "signed_out"
                assert not status["cleanup_pending"] and status["operation_state"] == "idle"
                assert not list(root.glob("run-*"))
                await call(client, "list_study_rights", error="SIGN_IN_NEEDED")
                assert len(state["requests"]) == request_count
            assert b"PRIVATE_SECRET" not in await process.stderr.read()
        finally:
            release.set()
            if process.returncode is None:
                process.kill()
                await process.wait()
            for handle in handles.values():
                handle.Close()
    with local_peppi() as (origin, state):
        asyncio.run(run(origin, state))

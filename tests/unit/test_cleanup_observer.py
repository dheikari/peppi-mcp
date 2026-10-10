"""Observers verify owned jobs without claiming unrelated server descendants."""
import asyncio
import json
import os
import subprocess
import sys
import uuid
from types import SimpleNamespace

import pytest

from tests.protocol.test_browser_failures import call, startup_stage


@pytest.mark.parametrize("code,expected", [
    ("PERSONAL_READ_TIMEOUT", "PERSONAL_READ_TIMEOUT"),
    ("PRIVATE_SECRET", "UNEXPECTED_ERROR"),
])
def test_unexpected_tool_outcome_reports_only_a_fixed_code(code, expected):
    body = {"ok": False, "error": {"code": code, "message": "PRIVATE_SECRET"}}
    class Client:
        async def call_tool(self, name, args):
            return SimpleNamespace(structured_content=body, is_error=True,
                content=[SimpleNamespace(text=json.dumps(body))])
    with pytest.raises(AssertionError) as caught:
        asyncio.run(call(Client(), "connect_personal"))
    assert str(caught.value) == "Unexpected tool outcome: connect_personal: " + expected
    assert "PRIVATE_SECRET" not in str(caught.value)


@pytest.mark.parametrize("content,expected", [
    (b'{"stage":"browser creation"}', "browser creation"),
    (b'{"stage":"PRIVATE_SECRET"}', "unrecorded"),
    (b'{"stage":["PRIVATE_SECRET"]}', "unrecorded"),
    (b'{"stage":"ready","url":"PRIVATE_SECRET"}', "unrecorded"),
    (b'PRIVATE_SECRET', "unrecorded"),
    (b'{"stage":"ready"}' + b' ' * 2000, "unrecorded"),
])
def test_startup_diagnostics_allow_only_a_fixed_stage(tmp_path, content, expected):
    record = tmp_path / "startup.json"
    record.write_bytes(content)
    assert startup_stage(record) == expected
    assert "PRIVATE_SECRET" not in startup_stage(record)


@pytest.mark.parametrize("stage,expected", [("browser creation", "browser creation"),
                                           ("PRIVATE_SECRET", "unrecorded")])
def test_failed_connect_includes_only_a_validated_startup_stage(tmp_path, stage, expected):
    record = tmp_path / "startup.json"
    record.write_text(json.dumps({"stage":stage}))
    body = {"ok":False, "error":{"code":"PERSONAL_READ_TIMEOUT", "message":"PRIVATE_SECRET"}}
    class Client:
        async def call_tool(self, name, args):
            return SimpleNamespace(structured_content=body, is_error=True,
                content=[SimpleNamespace(text=json.dumps(body))])
    with pytest.raises(AssertionError) as caught:
        asyncio.run(call(Client(), "connect_personal", startup_record=record))
    assert str(caught.value) == "Unexpected tool outcome: connect_personal: PERSONAL_READ_TIMEOUT; startup stage: " + expected
    assert "PRIVATE_SECRET" not in str(caught.value)


@pytest.mark.skipif(os.name != "nt", reason="Owned Windows job observer")
def test_observer_rejects_owned_survivors_and_preserves_unrelated_children():
    import win32api
    import win32con
    import win32job
    from tests.protocol.test_cleanup_stdio import assert_owned_stopped, descendants

    name = "Local\\peppi-observer-" + uuid.uuid4().hex
    job = win32job.CreateJobObject(None, name)
    processes, handles = [], []
    def launch(owned):
        process = subprocess.Popen([sys.executable, "-c", "import sys; sys.stdin.buffer.read()"],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW)
        processes.append(process)
        handle = win32api.OpenProcess(win32con.PROCESS_SET_QUOTA | win32con.PROCESS_TERMINATE | 0x1000, False, process.pid)
        handles.append(handle)
        if owned:
            win32job.AssignProcessToJobObject(job, handle)
        return process, handle
    try:
        unrelated, _ = launch(False)
        first, first_handle = launch(True)
        record = {"fixture_job_name": name}
        with pytest.raises(AssertionError, match="Owned process is still running"):
            assert_owned_stopped(record, {first.pid: first_handle})
        first.terminate()
        first.wait(timeout=10)
        late, _ = launch(True)
        with pytest.raises(AssertionError, match="Owned job still has active processes"):
            assert_owned_stopped(record, {first.pid: first_handle})
        win32job.TerminateJobObject(job, 0)
        late.wait(timeout=10)
        assert_owned_stopped(record, {first.pid: first_handle})
        assert unrelated.poll() is None
        assert unrelated.pid in descendants(os.getpid())
    finally:
        win32job.TerminateJobObject(job, 0)
        for process in processes:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=10)
            process.stdin.close()
        for handle in handles:
            handle.Close()
        job.Close()

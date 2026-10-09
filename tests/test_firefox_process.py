"""Real owned-process cleanup without a browser, network or authentication."""

import asyncio
import os

import pytest

from peppi_mcp.adapters.firefox_process import FirefoxProcess


@pytest.mark.skipif(os.name != "nt", reason="Windows process containment")
def test_unresponsive_worker_and_its_child_are_closed_together(monkeypatch):
    import win32api
    import win32con
    import win32process
    create = asyncio.create_subprocess_exec
    async def fictional_worker(*args, **kwargs):
        assert args[-1] == "peppi_mcp.browser_worker"
        return await create(*args[:-1], "tests.process_tree_worker", **kwargs)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fictional_worker)
    async def run():
        browser = FirefoxProcess()
        request = browser._request
        child_handle = None
        async def capture(action, **payload):
            nonlocal child_handle
            response = await request(action, **payload)
            if action == "open":
                child_handle = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION, False, response["child_pid"])
            return response
        browser._request = capture
        try:
            await browser.open()
            parent = browser.process
            profile_root = browser.lease.path
            assert win32process.GetExitCodeProcess(child_handle) == 259
            await asyncio.wait_for(browser.close(), 8)
            assert parent.returncode is not None and browser.job is None
            assert not profile_root.exists() and not browser.cleanup_pending
            for _ in range(20):
                if win32process.GetExitCodeProcess(child_handle) != 259:
                    break
                await asyncio.sleep(.05)
            assert win32process.GetExitCodeProcess(child_handle) != 259
        finally:
            await browser.close()
            if child_handle:
                child_handle.Close()
    asyncio.run(run())


@pytest.mark.skipif(os.name != "nt", reason="Windows process containment")
def test_partial_startup_job_assignment_failure_closes_worker_and_profile(monkeypatch):
    import win32job
    created = []
    create = asyncio.create_subprocess_exec
    async def capture(*args, **kwargs):
        process = await create(*args, **kwargs)
        created.append(process)
        return process
    def fail(*args): raise RuntimeError("FICTIONAL_PRIVATE_STARTUP_VALUE")
    monkeypatch.setattr(asyncio,"create_subprocess_exec",capture)
    monkeypatch.setattr(win32job,"AssignProcessToJobObject",fail)
    async def run():
        browser = FirefoxProcess()
        with pytest.raises(RuntimeError): await browser.open()
        assert created[0].returncode is not None
        assert browser.process is None and browser.job is None and browser.lease is None
        assert not browser.cleanup_pending
    asyncio.run(run())


def test_cancelled_worker_exchange_never_accepts_its_late_reply():
    from peppi_mcp.errors import PeppiError
    class Sink:
        def write(self, _): pass
        async def drain(self): pass
    class Process:
        returncode = None
        stdin = Sink()
    async def run():
        browser = FirefoxProcess()
        process = Process()
        process.stdout = asyncio.StreamReader()
        browser.process = process
        first = asyncio.create_task(browser._request("check"))
        await asyncio.sleep(0)
        first.cancel()
        with pytest.raises(asyncio.CancelledError): await first
        process.stdout.feed_data(b'{"id":1,"action":"check","ok":true,"data":{"secret":"PRIVATE_SECRET"}}\n')
        with pytest.raises(PeppiError) as error: await browser._request("check")
        assert error.value.code == "BROWSER_UNAVAILABLE" and "PRIVATE_SECRET" not in str(error.value)
    asyncio.run(run())


def test_worker_error_text_is_not_trusted_as_a_diagnostic():
    from peppi_mcp.errors import PeppiError
    class Sink:
        def write(self, _): pass
        async def drain(self): pass
    class Process:
        returncode = None
        stdin = Sink()
    async def run():
        browser = FirefoxProcess()
        process = Process()
        process.stdout = asyncio.StreamReader()
        process.stdout.feed_data(b'{"id":1,"action":"check","ok":false,"code":"PERSONAL_VIEW_INVALID","message":"PRIVATE_SECRET","retryable":false,"retry_after_seconds":null}\n')
        browser.process = process
        with pytest.raises(PeppiError) as error: await browser._request("check")
        assert error.value.code == "PERSONAL_VIEW_INVALID" and "PRIVATE_SECRET" not in str(error.value)
    asyncio.run(run())


@pytest.mark.skipif(os.name != "nt", reason="Windows process containment")
def test_cancelled_partial_startup_and_disconnect_join_cleanup(monkeypatch):
    async def run():
        from peppi_mcp.services.live import LivePersonal
        from peppi_mcp.models import NoArguments
        from peppi_mcp.errors import PeppiError
        entered = asyncio.Event()
        browser = FirefoxProcess()
        async def stalled_open(action, **payload):
            assert action == "open"
            entered.set()
            await asyncio.Event().wait()
        browser._request = stalled_open
        service = LivePersonal(lambda: browser)
        opening = asyncio.create_task(service.call("connect_personal", NoArguments()))
        await entered.wait()
        process, profile = browser.process, browser.lease.path
        await service.call("disconnect_personal", NoArguments())
        with pytest.raises(PeppiError) as error:
            await opening
        assert error.value.code == "SIGN_IN_NEEDED"
        assert process.returncode is not None and not profile.exists()
        assert browser._retiring is None and not service.cleanup_pending
    asyncio.run(run())


@pytest.mark.skipif(os.name != "nt", reason="Windows process containment")
def test_profile_is_retained_until_job_termination_is_verified(tmp_path, monkeypatch):
    import win32job
    from peppi_mcp.runtime_storage import RuntimeLease
    query = win32job.QueryInformationJobObject
    prove = [False]
    def uncertain(job, kind):
        if kind == win32job.JobObjectBasicAccountingInformation and not prove[0]:
            return {"ActiveProcesses": 1}
        return query(job, kind)
    monkeypatch.setattr(win32job, "QueryInformationJobObject", uncertain)
    async def run():
        browser = FirefoxProcess()
        browser.job = win32job.CreateJobObject(None, "")
        browser.lease = RuntimeLease(tmp_path / "runtime")
        profile = browser.lease.path
        await browser.close_with_deadline(asyncio.get_running_loop().time() + .03)
        await browser.wait_cleanup()
        assert browser.cleanup_pending and profile.exists()
        assert browser._retiring.job is not None
        prove[0] = True
        await browser.close()
        assert not browser.cleanup_pending and not profile.exists()
    asyncio.run(run())


@pytest.mark.skipif(os.name != "nt", reason="Windows profile ownership")
def test_failed_initialization_rollback_retains_lease_without_claiming_cleanup(tmp_path, monkeypatch):
    from pathlib import Path
    from peppi_mcp.runtime_storage import RuntimeLeaseCreationError
    root = tmp_path / "runtime"
    monkeypatch.setattr("peppi_mcp.runtime_storage.runtime_root", lambda: root)
    write, rmdir = Path.write_text, Path.rmdir
    def failed_write(path, *args, **kwargs):
        if path.name == "owner.json":
            raise OSError("PRIVATE_SECRET")
        return write(path,*args,**kwargs)
    def failed_rmdir(path):
        if path.parent == root:
            raise OSError("PRIVATE_SECRET")
        return rmdir(path)
    monkeypatch.setattr(Path, "write_text", failed_write)
    monkeypatch.setattr(Path, "rmdir", failed_rmdir)
    async def run():
        browser = FirefoxProcess()
        try:
            with pytest.raises(RuntimeLeaseCreationError):
                await browser.open()
            assert browser.cleanup_pending and browser.lease.path.exists()
            assert browser._retiring.lease is browser.lease
            assert browser.process is None
        finally:
            monkeypatch.setattr(Path, "write_text", write)
            monkeypatch.setattr(Path, "rmdir", rmdir)
            profile = browser.lease.path
            try:
                await browser.close()
                assert not browser.cleanup_pending and not profile.exists()
            finally:
                if profile.exists():
                    assert not list(profile.iterdir())
                    profile.rmdir()
    asyncio.run(run())

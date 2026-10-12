"""Real fictional Windows locks verify the owned cleanup budget."""
import asyncio
import json
import os
import threading

import pytest

from peppi_mcp.adapters.firefox_process import FirefoxProcess
from peppi_mcp.runtime_storage import CleanupWorker, RuntimeLease, remove_owned
from peppi_mcp.services.live import LivePersonal
from tests.unit.test_live_service import Browser


@pytest.mark.parametrize("kind,code,retryable", [
    (PermissionError, 32, True),
    (OSError, 33, True),
    (PermissionError, 5, False),
    (OSError, None, False),
    (ValueError, 32, False),
    (OSError, 32.0, False),
    (OSError, "PRIVATE_SECRET", False),
])
def test_cleanup_worker_preserves_only_known_lock_classification(kind, code, retryable):
    def failure():
        error = kind("PRIVATE_SECRET")
        error.winerror = code
        raise error
    async def run():
        expected = OSError if issubclass(kind, OSError) else ValueError
        with pytest.raises(expected) as caught:
            await CleanupWorker().run(failure)
        assert getattr(caught.value, "retryable", False) is retryable
        assert str(caught.value) == ("Owned runtime cleanup failed" if expected is OSError
                                    else "Owned runtime cleanup refused")
        assert caught.value.__cause__ is None and caught.value.__context__ is None
    asyncio.run(run())


@pytest.mark.skipif(os.name != "nt", reason="Windows profile ownership")
def test_changed_ownership_is_refused_once_and_keeps_exact_lease(tmp_path, monkeypatch):
    lease = RuntimeLease(tmp_path / "runtime")
    marker = lease.path / "owner.json"
    tampered = {**lease.owner, "created": "PRIVATE_SECRET"}
    marker.write_text(json.dumps(tampered))
    calls = []
    def removal(*args):
        calls.append(True)
        return remove_owned(*args)
    monkeypatch.setattr("peppi_mcp.runtime_storage.remove_owned", removal)
    async def run():
        browser = FirefoxProcess()
        browser.lease = lease
        await browser.close()
        assert calls == [True], "Ownership refusal was retried"
        assert browser.cleanup_pending and browser.lease is lease
        assert json.loads(marker.read_text()) == tampered
        marker.write_text(json.dumps(lease.owner))
        await browser.close()
        assert calls == [True, True] and not browser.cleanup_pending
        assert browser.lease is None and not lease.path.exists()
    try:
        asyncio.run(run())
    finally:
        if marker.exists():
            marker.write_text(json.dumps(lease.owner))
        remove_owned(lease.root, lease.path, lease.owner)


@pytest.mark.skipif(os.name != "nt", reason="Windows sharing violations")
def test_cleanup_recovers_a_real_file_lock_released_after_five_refusals(tmp_path, monkeypatch):
    import win32con
    import win32file

    lease = RuntimeLease(tmp_path / "runtime")
    locked = lease.path / "fictional-cookie-store"
    locked.write_text("PRIVATE_SECRET")
    handle = win32file.CreateFile(str(locked), win32con.GENERIC_READ, 0, None,
                                  win32con.OPEN_EXISTING, 0, None)
    released = threading.Event()
    failures = []
    def removal(*args):
        try:
            return remove_owned(*args)
        except OSError as exc:
            failures.append(exc.winerror)
            if len(failures) == 5:
                handle.Close()
                released.set()
            raise
    monkeypatch.setattr("peppi_mcp.runtime_storage.remove_owned", removal)
    async def run():
        browser = FirefoxProcess()
        browser.lease = lease
        service = LivePersonal(Browser)
        service.browser = browser
        await service.close()
        assert released.is_set() and failures == [32] * 5
        assert not service.cleanup_pending, "Cleanup abandoned a released lock before its deadline"
        assert service.status()["personal_connection"] == "signed_out"
        assert service.status()["operation_state"] == "idle"
        assert browser.lease is None and not lease.path.exists()
    try:
        asyncio.run(run())
    finally:
        if not released.is_set():
            handle.Close()
        remove_owned(lease.root, lease.path, lease.owner)


@pytest.mark.skipif(os.name != "nt", reason="Windows sharing violations")
def test_persistent_file_lock_exhausts_only_the_cleanup_budget_and_retains_ownership(tmp_path):
    import win32con
    import win32file
    lease = RuntimeLease(tmp_path / "runtime")
    locked = lease.path / "fictional-cookie-store"
    locked.write_text("PRIVATE_SECRET")
    handle = win32file.CreateFile(str(locked), win32con.GENERIC_READ, 0, None,
                                  win32con.OPEN_EXISTING, 0, None)
    async def run():
        browser = FirefoxProcess()
        browser.lease = lease
        service = LivePersonal(Browser)
        service.browser = browser
        service.cleanup_timeout = .1  # Fictional unit clock; production stays ten seconds.
        started = asyncio.get_running_loop().time()
        await service.close()
        elapsed = asyncio.get_running_loop().time() - started
        if service._cleanup_task is not None:
            await asyncio.wait_for(asyncio.shield(service._cleanup_task), .3)
        assert elapsed < .3 and service.cleanup_pending and browser.lease is lease
        assert json.loads((lease.path / "owner.json").read_text()) == lease.owner
        assert locked.exists() and service.status()["personal_connection"] == "unavailable"
        handle.Close()
        await service.close()
        assert not service.cleanup_pending and not lease.path.exists()
    try:
        asyncio.run(run())
    finally:
        handle.Close()
        remove_owned(lease.root, lease.path, lease.owner)

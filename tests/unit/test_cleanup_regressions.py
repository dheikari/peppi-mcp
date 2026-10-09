"""Regressions for cleanup ownership, cancellation and bounded recovery."""
import asyncio
import threading
import os

import pytest

from peppi_mcp.adapters.firefox_process import FirefoxProcess
from peppi_mcp.errors import PeppiError
from peppi_mcp.models import NoArguments
from peppi_mcp.runtime_storage import RuntimeLease, remove_owned
from peppi_mcp.services.live import LivePersonal
from tests.unit.test_live_service import Browser
import anyio


@pytest.mark.skipif(os.name != "nt", reason="Windows profile ownership")
def test_failed_profile_removal_blocks_reconnect_and_can_be_recovered(tmp_path, monkeypatch):
    created = []
    class LocalBrowser(FirefoxProcess):
        async def open(self):
            self.lease = RuntimeLease(tmp_path / "runtime")
            created.append(self.lease)
    async def run():
        service = LivePersonal(LocalBrowser)
        await service.call("connect_personal", NoArguments())
        def fail(*args):
            raise PermissionError("PRIVATE_FICTIONAL_LOCK")
        monkeypatch.setattr("peppi_mcp.runtime_storage.remove_owned", fail)
        try:
            await service.close()
            assert service.cleanup_pending and created[0].path.exists()
            with pytest.raises(PeppiError) as error:
                await service.call("connect_personal", NoArguments())
            assert error.value.code == "PERSONAL_CLEANUP_PENDING"
            assert len(created) == 1 and service.status()["cleanup_pending"]
            monkeypatch.setattr("peppi_mcp.runtime_storage.remove_owned", remove_owned)
            await service.call("disconnect_personal", NoArguments())
            assert not created[0].path.exists() and not service.cleanup_pending
            await service.call("connect_personal", NoArguments())
            assert len(created) == 2 and created[1].path.exists()
        finally:
            monkeypatch.setattr("peppi_mcp.runtime_storage.remove_owned", remove_owned)
            await service.close()
            for lease in created:
                remove_owned(lease.root, lease.path, lease.owner)
    asyncio.run(run())


@pytest.mark.skipif(os.name != "nt", reason="Windows profile ownership")
def test_concurrent_backend_close_shares_removal_and_truthful_result(tmp_path, monkeypatch):
    lease = RuntimeLease(tmp_path / "runtime")
    released = threading.Event()
    calls = []
    async def run():
        started = asyncio.Event()
        loop = asyncio.get_running_loop()
        def removal(root, path, owner):
            calls.append(True)
            loop.call_soon_threadsafe(started.set)
            if len(calls) > 1:
                raise PermissionError("PRIVATE_FICTIONAL_LOCK")
            assert released.wait(5)
            remove_owned(root, path, owner)
        monkeypatch.setattr("peppi_mcp.runtime_storage.remove_owned", removal)
        browser = FirefoxProcess()
        browser.lease = lease
        first = asyncio.create_task(browser.close())
        await started.wait()
        entered = asyncio.Event()
        async def second_close():
            entered.set()
            await browser.close()
        second = asyncio.create_task(second_close())
        await entered.wait()
        released.set()
        await asyncio.gather(first, second)
        assert calls == [True]
        assert not lease.path.exists() and not browser.cleanup_pending
        assert browser.lease is None
    try:
        asyncio.run(run())
    finally:
        released.set()
        if lease.path.exists():
            remove_owned(lease.root, lease.path, lease.owner)


def test_cancelled_cleanup_waiter_keeps_guard_until_actual_completion():
    async def run():
        started, release = asyncio.Event(), asyncio.Event()
        old, new = Browser(), Browser()
        async def cleanup():
            started.set()
            await release.wait()
        old.close = cleanup
        service = LivePersonal(lambda: new)
        service.browser = old
        closer = asyncio.create_task(service.close())
        await started.wait()
        running = service._cleanup_task
        closer.cancel()
        with pytest.raises(asyncio.CancelledError):
            await closer
        try:
            assert service._cleanup_task is running and not running.done()
            with pytest.raises(PeppiError) as error:
                await service.call("connect_personal", NoArguments())
            assert error.value.code == "PERSONAL_BUSY"
            assert service.browser is None
        finally:
            release.set()
            await running
        await service.call("connect_personal", NoArguments())
        assert service.browser is new and service.state == "awaiting_login"
        await service.close()
    asyncio.run(run())


def test_multiple_cancelled_waiters_and_anyio_scope_do_not_cancel_cleanup():
    async def run():
        started, release = asyncio.Event(), asyncio.Event()
        browser = Browser()
        calls = []
        async def cleanup():
            calls.append(True)
            started.set()
            await release.wait()
        browser.close = cleanup
        service = LivePersonal(Browser)
        service.browser = browser
        first = asyncio.create_task(service.close())
        await started.wait()
        others = [asyncio.create_task(service.close()) for _ in range(2)]
        await asyncio.sleep(0)
        for task in [first, *others]:
            task.cancel()
        results = await asyncio.gather(first, *others, return_exceptions=True)
        assert all(isinstance(result, asyncio.CancelledError) for result in results)
        owned = service._cleanup_task
        assert owned is not None and not owned.done()
        async def scoped_waiter():
            with anyio.CancelScope() as scope:
                scope.cancel()
                await service.close()
        waiter = asyncio.create_task(scoped_waiter())
        release.set()
        await waiter
        await owned
        assert calls == [True] and service._cleanup_task is None
        assert not service.cleanup_pending and service.state == "signed_out"
    asyncio.run(run())


@pytest.mark.skipif(os.name != "nt", reason="Windows profile ownership")
def test_slow_daemon_removal_outlives_budget_without_losing_guard(tmp_path, monkeypatch):
    async def run():
        released = threading.Event()
        started = asyncio.Event()
        loop = asyncio.get_running_loop()
        lease = RuntimeLease(tmp_path / "runtime")
        def slow(root, path, owner):
            loop.call_soon_threadsafe(started.set)
            assert released.wait(5)
            remove_owned(root, path, owner)
        monkeypatch.setattr("peppi_mcp.runtime_storage.remove_owned", slow)
        browser = FirefoxProcess()
        browser.lease = lease
        service = LivePersonal(Browser)
        service.browser = browser
        service.cleanup_timeout = .04
        close = asyncio.create_task(service.close())
        await started.wait()
        try:
            await asyncio.wait_for(close, .3)
            status = service.status()
            assert status["operation_state"] == "closing" and status["cleanup_pending"]
            assert status["active_stage"] == "owned browser cleanup"
            assert service._cleanup_task is not None and lease.path.exists()
            with pytest.raises(PeppiError) as error:
                await service.call("connect_personal", NoArguments())
            assert error.value.code == "PERSONAL_BUSY"
            running = service._cleanup_task
        finally:
            released.set()
        await asyncio.wait_for(running, 1)
        assert not service.cleanup_pending and not lease.path.exists()
        await service.call("connect_personal", NoArguments())
        assert service.state == "awaiting_login"
        await service.close()
    asyncio.run(run())


@pytest.mark.parametrize("pending_kind", ["running", "failed"])
def test_active_timeout_can_return_pending_cleanup_and_block_reconnect(pending_kind):
    from peppi_mcp.models import AchievementArguments, ScopedArguments
    from tests.unit.test_live_service import connected

    async def run():
        started, release = asyncio.Event(), asyncio.Event()
        service, browser, right = await connected()
        page, _ = await service.call("list_achievements", AchievementArguments(study_right_id=right, limit=1))
        never = asyncio.Event()
        fail_cleanup = True
        async def blocked_read(*args):
            await never.wait()
        async def blocked_cleanup():
            started.set()
            if pending_kind == "failed" and fail_cleanup:
                raise OSError("PRIVATE_FICTIONAL_LOCK")
            await release.wait()
        browser.read, browser.close = blocked_read, blocked_cleanup
        service.deadline = .05  # Fictional unit clock only.
        service.cleanup_timeout = .1 if pending_kind == "running" else 1
        try:
            with pytest.raises(PeppiError) as error:
                await service.call("get_credit_summary", ScopedArguments(study_right_id=right))
            assert error.value.code == "PERSONAL_READ_TIMEOUT"
            assert started.is_set()
            status = service.status()
            assert status["cleanup_pending"] and status["personal_connection"] == "unavailable"
            assert status["operation_state"] == ("closing" if pending_kind == "running" else "idle")
            assert status["active_stage"] == ("owned browser cleanup" if pending_kind == "running" else None)
            assert status["read_mechanism"] is None and status["queued_requests"] == 0
            assert service.identity is None and not service._pages and not service._plans
            assert service._retired == [browser]
            cleanup = service._cleanup_task
            assert (cleanup is not None and not cleanup.done()) if pending_kind == "running" else cleanup is None
            for name, args, code in (
                ("connect_personal", NoArguments(), "PERSONAL_BUSY" if pending_kind == "running" else "PERSONAL_CLEANUP_PENDING"),
                ("list_achievements", AchievementArguments(study_right_id=right, limit=1, cursor=page["next_cursor"]), "PERSONAL_BUSY" if pending_kind == "running" else "SIGN_IN_NEEDED"),
            ):
                with pytest.raises(PeppiError) as refused:
                    await service.call(name, args)
                assert refused.value.code == code
            assert browser.opened == 1
        finally:
            fail_cleanup = False
            release.set()
            if service._cleanup_task is not None:
                await asyncio.wait_for(asyncio.shield(service._cleanup_task), 1)
            await service.call("disconnect_personal", NoArguments())
        status = service.status()
        assert not status["cleanup_pending"] and status["operation_state"] == "idle"
        assert status["personal_connection"] == "signed_out"
        with pytest.raises(PeppiError) as refused:
            await service.call("list_achievements", AchievementArguments(study_right_id=right, limit=1, cursor=page["next_cursor"]))
        assert refused.value.code == "SIGN_IN_NEEDED"
    asyncio.run(run())


def test_failed_cleanup_recovery_invalidates_old_rights_and_cursors(monkeypatch):
    from peppi_mcp.models import AchievementArguments
    from tests.unit.test_live_service import connected
    async def run():
        service, browser, right = await connected()
        page, _ = await service.call("list_achievements", AchievementArguments(study_right_id=right, limit=1))
        async def fail():
            raise OSError("PRIVATE_FICTIONAL_LOCK")
        browser.close = fail
        await service.close()
        assert not service._pages and not service._plans and service.identity is None
        browser.close = Browser().close
        await service.call("disconnect_personal", NoArguments())
        service.factory = Browser
        await service.call("connect_personal", NoArguments())
        await service.call("connect_personal", NoArguments())
        rights, _ = await service.call("list_study_rights", NoArguments())
        new_right = rights["items"][0]["id"]
        assert new_right != right
        with pytest.raises(PeppiError) as error:
            await service.call("list_achievements", AchievementArguments(study_right_id=new_right, limit=1, cursor=page["next_cursor"]))
        assert error.value.code == "INVALID_CURSOR"
        await service.close()
    asyncio.run(run())


def test_bounded_startup_recovery_keeps_status_responsive_and_guard_owned():
    async def run():
        released = threading.Event()
        started = asyncio.Event()
        loop = asyncio.get_running_loop()
        def recovery():
            loop.call_soon_threadsafe(started.set)
            assert released.wait(5)
            return False
        service = LivePersonal(Browser, recover=recovery)
        service.cleanup_timeout = .03
        initialize = asyncio.create_task(service.initialize())
        await started.wait()
        try:
            await asyncio.wait_for(initialize, .3)
            assert service.status()["cleanup_pending"]
            assert service.status()["operation_state"] == "closing"
            with pytest.raises(PeppiError) as error:
                await service.call("connect_personal", NoArguments())
            assert error.value.code == "PERSONAL_BUSY"
            owned = service._cleanup_task
        finally:
            released.set()
        await owned
        assert not service.cleanup_pending and service.state == "signed_out"
        await service.call("connect_personal", NoArguments())
        await service.close()
    asyncio.run(run())


@pytest.mark.parametrize("state", ["denied", "expired"])
def test_late_cleanup_keeps_requested_state_and_single_task_ownership(state):
    async def run():
        entered, released = asyncio.Event(), asyncio.Event()
        browser = Browser()
        count = []
        async def cleanup():
            count.append(True)
            entered.set()
            await released.wait()
        browser.close = cleanup
        service = LivePersonal(Browser)
        service.browser = browser
        service.cleanup_timeout = .01
        closing = asyncio.create_task(service.close(state))
        await entered.wait()
        owned = service._cleanup_task
        assert service._start_cleanup("signed_out") is owned
        await closing
        assert service.state == "unavailable" and service.cleanup_pending
        released.set()
        await owned
        assert count == [True] and service.state == state
        assert not service.cleanup_pending and service._cleanup_task is None
    asyncio.run(run())

"""Transport-independent lifecycle tests with fictional records only."""

import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest

from peppi_mcp.adapters.lapland_transcript_view import TRANSCRIPT_URL, normalize_transcript_view
from peppi_mcp.errors import PeppiError
from peppi_mcp.models import AchievementArguments, NoArguments, ScopedArguments
from peppi_mcp.services.live import Identity, LivePersonal, SourceRight


class Browser:
    method = "fictional_test_browser"

    def __init__(self):
        self.identity = Identity("fictional-account-a", (SourceRight("right-a", "Fictional degree", ("right-b",)), SourceRight("right-b", "Other degree")))
        self.opened = self.closed = self.reads = self.checks = 0
        self.error = None
        self.wait = 0
        self.during_read = None

    async def open(self):
        self.opened += 1

    async def check(self):
        self.checks += 1
        if self.error:
            raise self.error
        return self.identity

    async def read(self, right, identity):
        self.reads += 1
        await asyncio.sleep(self.wait)
        if self.during_read:
            self.during_read()
        data = {"url": TRANSCRIPT_URL, "study_right_id": right.key, "visible": True,
                "reported_count": 3, "reported_credits": "1,5",
                "rows": [{"row_type": "course_unit", "visible": True, "source_status": "Suoritettu",
                          "course_code": "TEST" + str(i), "title": "Fictional course", "credits": "0,5",
                          "grade": "5", "assessment_date": "03.01.2026", "additional_info": ""} for i in range(3)]}
        return normalize_transcript_view(json.dumps(data), expected_study_right=right.key,
            retrieved_at=datetime(2026, 1, 3, tzinfo=timezone.utc) + timedelta(seconds=self.reads))

    async def close(self):
        self.closed += 1


async def connected(browser=None, **kwargs):
    browser = browser or Browser()
    service = LivePersonal(lambda: browser, **kwargs)
    status, _ = await service.call("connect_personal", NoArguments())
    assert status["personal_connection"] == "awaiting_login"
    await service.call("connect_personal", NoArguments())
    rights, _ = await service.call("list_study_rights", NoArguments())
    return service, browser, rights["items"][0]["id"]


def test_quiet_start_explicit_connect_and_idempotent_window():
    async def run():
        browser = Browser()
        service = LivePersonal(lambda: browser)
        status, _ = await service.call("get_connection_status", NoArguments())
        assert status["sign_in_needed"] and browser.opened == 0
        with pytest.raises(PeppiError) as error:
            await service.call("list_study_rights", NoArguments())
        assert error.value.code == "SIGN_IN_NEEDED"
        for _ in range(3):
            await service.call("connect_personal", NoArguments())
        assert browser.opened == 1
        assert service.state == "connected"
        await service.call("disconnect_personal", NoArguments())
        assert browser.closed == 1 and service.identity is None and not service._pages
    asyncio.run(run())


def test_pagination_pins_original_snapshot_and_fresh_queries_reacquire():
    async def run():
        service, browser, right = await connected()
        args = AchievementArguments(study_right_id=right, limit=1)
        first, mode = await service.call("list_achievements", args)
        assert mode == "live" and browser.reads == 1
        next_args = args.model_copy(update={"cursor": first["next_cursor"]})
        second, mode = await service.call("list_achievements", next_args)
        assert mode == "cached" and browser.reads == 1
        assert second["provenance"]["retrieved_at"] == first["provenance"]["retrieved_at"]
        assert second["items"][0]["provenance"]["source_mode"] == "cached"
        assert first["items"][0]["id"] != second["items"][0]["id"]
        fresh, mode = await service.call("list_achievements", args)
        assert mode == "live" and browser.reads == 2
        assert fresh["provenance"]["retrieved_at"] > first["provenance"]["retrieved_at"]
        summary, _ = await service.call("get_credit_summary", ScopedArguments(study_right_id=right))
        assert summary["total_credits"] == "1.5"
        assert summary["provenance"]["source_url"] == TRANSCRIPT_URL
    asyncio.run(run())


@pytest.mark.parametrize("change", ["page_size", "right", "tamper", "expired", "evicted"])
def test_cursor_scope_and_retention(change):
    async def run():
        now = [10.0]
        service, browser, right = await connected(clock=lambda: now[0])
        args = AchievementArguments(study_right_id=right, limit=1)
        page, _ = await service.call("list_achievements", args)
        next_args = args.model_copy(update={"cursor": page["next_cursor"]})
        expected = "INVALID_CURSOR"
        if change == "page_size":
            next_args = next_args.model_copy(update={"limit": 2})
        elif change == "right":
            next_args = next_args.model_copy(update={"study_right_id": service._id("right-b")})
        elif change == "tamper":
            next_args = next_args.model_copy(update={"cursor": "not-a-valid-token"})
        elif change == "expired":
            now[0] += 301
            expected = "CURSOR_EXPIRED"
        else:
            for _ in range(service.capacity):
                await service.call("list_achievements", args)
            assert len(service._pages) == service.capacity
            expected = "CURSOR_EXPIRED"
        with pytest.raises(PeppiError) as error:
            await service.call("list_achievements", next_args)
        assert error.value.code == expected
    asyncio.run(run())


@pytest.mark.parametrize("code", ["SIGN_IN_NEEDED", "ACCESS_DENIED", "BROWSER_UNAVAILABLE"])
def test_authentication_loss_cannot_return_a_cached_page(code):
    async def run():
        service, browser, right = await connected()
        args = AchievementArguments(study_right_id=right, limit=1)
        page, _ = await service.call("list_achievements", args)
        browser.error = PeppiError(code, "Fictional failure")
        with pytest.raises(PeppiError) as error:
            await service.call("list_achievements", args.model_copy(update={"cursor": page["next_cursor"]}))
        assert error.value.code == ("SESSION_EXPIRED" if code == "SIGN_IN_NEEDED" else code)
        assert not service._pages and service.identity is None and browser.closed == 1
    asyncio.run(run())


@pytest.mark.parametrize("during_read", [False, True])
def test_account_change_discards_results_and_reconnect_changes_ids(during_read):
    async def run():
        service, browser, right = await connected()
        def switch():
            browser.identity = Identity("fictional-account-b", browser.identity.rights)
        if during_read:
            browser.during_read = switch
        else:
            switch()
        with pytest.raises(PeppiError) as error:
            await service.call("get_credit_summary", ScopedArguments(study_right_id=right))
        assert error.value.code == "STUDY_CONTEXT_CHANGED"
        assert not service._pages and service.identity is None
        await service.call("connect_personal", NoArguments())
        await service.call("connect_personal", NoArguments())
        rights, _ = await service.call("list_study_rights", NoArguments())
        assert right != rights["items"][0]["id"]
    asyncio.run(run())


@pytest.mark.parametrize("status", ["all", "failed", "incomplete", "planned", "unknown"])
def test_unsupported_status_does_not_claim_empty_success(status):
    async def run():
        service, browser, right = await connected()
        with pytest.raises(PeppiError) as error:
            await service.call("list_achievements", AchievementArguments(study_right_id=right, status=status))
        assert error.value.code == "CAPABILITY_UNAVAILABLE" and browser.reads == 0
    asyncio.run(run())


def test_serialized_reads_timeout_and_cancellation_cleanup():
    async def run():
        service, browser, right = await connected()
        browser.wait = .02
        results = await asyncio.gather(*(service.call("get_credit_summary", ScopedArguments(study_right_id=right)) for _ in range(3)))
        assert all(result[0]["total_credits"] == "1.5" for result in results)
        service.deadline = .001
        with pytest.raises(PeppiError) as error:
            await service.call("get_credit_summary", ScopedArguments(study_right_id=right))
        assert error.value.code == "PERSONAL_READ_TIMEOUT" and service.browser is None
        service, browser, right = await connected()
        browser.wait = 10
        task = asyncio.create_task(service.call("get_credit_summary", ScopedArguments(study_right_id=right)))
        await asyncio.sleep(.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert service.browser is None and browser.closed == 1
    asyncio.run(run())


def test_unexpected_browser_exception_is_sanitized():
    async def run():
        service, browser, right = await connected()
        browser.error = RuntimeError("credential=DO-NOT-LEAK")
        with pytest.raises(PeppiError) as error:
            await service.call("list_study_rights", NoArguments())
        assert "DO-NOT-LEAK" not in str(error.value)
        assert service.browser is None
    asyncio.run(run())


def test_source_cannot_return_a_different_right_under_requested_id():
    async def run():
        service, browser, right = await connected()
        original_read = browser.read
        async def wrong_read(requested, identity):
            return await original_read(identity.rights[1], identity)
        browser.read = wrong_read
        with pytest.raises(PeppiError) as error:
            await service.call("get_credit_summary", ScopedArguments(study_right_id=right))
        assert error.value.code == "STUDY_CONTEXT_CHANGED"
        assert service.browser is None and not service._pages
    asyncio.run(run())


def test_mcp_style_cancel_scope_allows_browser_cleanup_to_finish():
    import anyio
    async def run():
        service, browser, right = await connected()
        browser.wait = 10
        async def delayed_close():
            await anyio.sleep(.01)
            browser.closed += 1
        browser.close = delayed_close
        with anyio.move_on_after(.01):
            await service.call("get_credit_summary", ScopedArguments(study_right_id=right))
        assert service.browser is None and browser.closed == 1
    anyio.run(run)

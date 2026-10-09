"""Async personal-session boundary and bounded, session-scoped pagination.

Browser objects never leave their owning event loop. Backend implementations
must verify identity through a fresh server response, not a cached DOM header.
"""

import asyncio
import base64
import hashlib
import hmac
import json
import math
import secrets
import time
import anyio
from collections import OrderedDict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from peppi_mcp.adapters.lapland_transcript_view import TRANSCRIPT_URL
from peppi_mcp.adapters.lapland_study_plan import PLAN_URL
from peppi_mcp.errors import PeppiError
from peppi_mcp.models import AchievementArguments, Snapshot
from peppi_mcp.services.achievements import credit_summary
from peppi_mcp.services.study_progress import study_progress
from peppi_mcp.services.assessment import assess
from peppi_mcp.study_plan_models import PlanListing, PlanSnapshot
from peppi_mcp.runtime_storage import CleanupWorker


@dataclass(frozen=True)
class SourceRight:
    key: str
    programme: str
    linked_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class Identity:
    principal: str
    rights: tuple[SourceRight, ...]


class PersonalBrowser(Protocol):
    method: str

    async def open(self) -> None: ...
    async def check(self) -> Identity: ...
    async def read(self, right: SourceRight, identity: Identity) -> Snapshot: ...
    async def list_plans(self, right: SourceRight, identity: Identity) -> PlanListing: ...
    async def read_plan(self, right: SourceRight, identity: Identity, plan_key: str) -> PlanSnapshot: ...
    async def close(self) -> None: ...


@dataclass(frozen=True)
class _Page:
    snapshot: Snapshot
    binding: tuple[str, str, int]
    expires: float


class LivePersonal:
    ttl = 300
    capacity = 8
    deadline = 30
    queue_timeout = 5
    queue_capacity = 4
    cleanup_timeout = 10

    def __init__(self, factory, *, clock=time.monotonic, recover=None, browser_name=None):
        self.factory, self.clock = factory, clock
        self.browser_name = browser_name
        self.browser: PersonalBrowser | None = None
        self.identity: Identity | None = None
        self.state = "signed_out"
        self.last_verified_at: str | None = None
        self._secret = secrets.token_bytes(32)
        self._pages: OrderedDict[str, _Page] = OrderedDict()
        self._plans: dict[tuple[str, str], str] = {}
        self._owner = None
        self._active = None
        self._waiters = deque()
        self._generation = 0
        self._cleanup_task = None
        self._cleanup_deadline = 0.0
        self._retired = []
        self._recover = recover
        self._storage_pending = recover is not None
        self._storage_worker = CleanupWorker()
        self.cleanup_pending = False
        self._cooldown = 0.0
        self._stage = "session operation"

    def status(self):
        return {"mode": "live", "institution_target": "University of Lapland",
                "personal_browser": self.browser_name,
                "personal_connection": self.state, "sign_in_needed": self.state != "connected",
                "read_mechanism": self.browser.method if self.browser else None,
                "last_verified_at": self.last_verified_at, "is_current_health_check": False,
                "supported_achievement_statuses": ["completed"],
                "study_plan_mechanism": "rendered_recorded_hops_version",
                "cache_ttl_seconds": self.ttl, "cache_storage": "memory_only",
                "operation_state": "closing" if self._cleanup_task else "busy" if self._owner else "idle",
                "active_stage": "owned browser cleanup" if self._cleanup_task else self._stage if self._owner else None,
                "queued_requests": len(self._waiters), "cleanup_pending": self.cleanup_pending,
                "warnings": ["Local MCP responses are visible to the client; a cloud assistant may process them through its provider."]}

    def _clear(self):
        self.identity = None
        self._pages.clear()
        self._plans.clear()
        self._secret = secrets.token_bytes(32)

    async def close(self, state="signed_out"):
        if self._cleanup_task is not None:
            await self._wait_cleanup(self._cleanup_task)
            return
        browser, self.browser = self.browser, None
        self._generation += 1
        self._clear()
        self.state = state
        if browser is not None:
            self._retired.append(browser)
        while self._waiters:
            waiter = self._waiters.popleft()
            if not waiter.done():
                waiter.set_exception(PeppiError("SIGN_IN_NEEDED", "The connection ended while waiting. Reconnect before reading."))
        active = self._active
        if active is not None and active is not asyncio.current_task():
            active.cancel()

        await self._wait_cleanup(self._start_cleanup(state))

    async def initialize(self):
        if self._storage_pending:
            await self._wait_cleanup(self._start_cleanup(self.state))

    def _start_cleanup(self, state):
        if self._cleanup_task is not None:
            return self._cleanup_task
        generation = self._generation
        deadline = asyncio.get_running_loop().time() + self.cleanup_timeout
        self._cleanup_deadline = deadline
        async def cleanup():
            for browser in tuple(self._retired):
                if asyncio.get_running_loop().time() >= deadline:
                    break
                try:
                    bounded = getattr(browser, "close_with_deadline", None)
                    if bounded is not None:
                        await bounded(deadline)
                        await browser.wait_cleanup()
                    else:
                        await browser.close()
                    if not getattr(browser, "cleanup_pending", False):
                        self._retired.remove(browser)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    pass  # Retain the backend; source/credential details omitted.
            if self._storage_pending and self._recover is not None and asyncio.get_running_loop().time() < deadline:
                try:
                    self._storage_pending = bool(await self._storage_worker.run(self._recover))
                except asyncio.CancelledError:
                    raise
                except Exception:
                    self._storage_pending = True
        task = asyncio.create_task(cleanup())
        self._cleanup_task = task
        def completed(done):
            if not done.cancelled():
                done.exception()
            # Only the task that owns this guard may release it or publish state.
            if self._cleanup_task is done:
                self._cleanup_task = None
                if generation == self._generation:
                    self.cleanup_pending = bool(self._retired) or self._storage_pending
                    self.state = "unavailable" if self.cleanup_pending else state
        task.add_done_callback(completed)
        return task

    async def _wait_cleanup(self, task):
        with anyio.CancelScope(shield=True):
            await asyncio.wait({task}, timeout=max(0, self._cleanup_deadline - asyncio.get_running_loop().time()))
        if not task.done():
            self.cleanup_pending = True
            self.state = "unavailable"

    @staticmethod
    def _cleanup_error():
        return PeppiError("PERSONAL_CLEANUP_PENDING",
            "Owned browser cleanup is incomplete. Retry disconnect_personal after file locks clear; if it persists, stop the connector and follow owned-runtime troubleshooting.", retryable=True)

    async def _observe(self, operation):
        generation = self._generation
        value = await operation
        if generation != self._generation:
            raise PeppiError("SIGN_IN_NEEDED", "The connection ended during the operation. No records were returned.")
        return value

    async def _acquire(self):
        generation = self._generation
        if self._cleanup_task:
            raise PeppiError("PERSONAL_BUSY", "Session cleanup is in progress. Wait before reconnecting.", retryable=True)
        ticket = object()
        if self._owner is None:
            self._owner = ticket
            return ticket
        if len(self._waiters) >= self.queue_capacity:
            raise PeppiError("PERSONAL_BUSY", "The personal-read queue is full. Wait for the current operation to finish.", retryable=True)
        waiter = asyncio.get_running_loop().create_future()
        self._waiters.append(waiter)
        try:
            async with asyncio.timeout(self.queue_timeout):
                ticket = await asyncio.shield(waiter)
                if generation != self._generation:
                    raise PeppiError("SIGN_IN_NEEDED", "The connection ended while waiting. Reconnect before reading.")
                return ticket
        except BaseException as exc:
            if waiter in self._waiters:
                self._waiters.remove(waiter)
            if waiter.done() and not waiter.cancelled() and waiter.exception() is None:
                self._release(waiter.result())
            else:
                waiter.cancel()
            if isinstance(exc, TimeoutError):
                raise PeppiError("PERSONAL_BUSY", "The browser remained busy for five seconds. Wait for the current operation to finish.", retryable=True) from None
            raise

    def _release(self, ticket):
        if self._owner is not ticket:
            return
        self._owner = None
        while self._waiters:
            waiter = self._waiters.popleft()
            if not waiter.done():
                self._owner = object()
                waiter.set_result(self._owner)
                break

    def _id(self, key):
        return "live-right:" + hmac.new(self._secret, key.encode(), hashlib.sha256).hexdigest()

    def _plan_id(self, right, key):
        return "live-plan:" + hmac.new(self._secret, (right.key + ":" + key).encode(), hashlib.sha256).hexdigest()

    def _plan_listing_payload(self, listing, right):
        if listing.study_right_key != right.key:
            raise PeppiError("STUDY_CONTEXT_CHANGED", "HOPS belongs to another study right.")
        # Keep only the latest verified version membership for this right.
        self._plans = {key: value for key, value in self._plans.items() if key[0] != right.key}
        versions = []
        for version in listing.versions:
            public_id = self._plan_id(right, version.id)
            self._plans[(right.key, public_id)] = version.id
            versions.append({**version.model_dump(mode="json"), "id": public_id})
        return {"study_right_id": self._id(right.key), "available_plans": versions,
                "current_plan_id": self._plan_id(right, listing.current_plan_id),
                "current_plan_name": listing.current_plan_name,
                "provenance": {"source_mode": "live", "retrieved_at": listing.retrieved_at.isoformat(),
                               "source_url": PLAN_URL, "completeness_scope": "recorded_hops_version_selector"}}

    async def _study_plan(self, name, args, right):
        if args.plan_id is None:
            self._stage = "HOPS version discovery"
            listing = await self._observe(self.browser.list_plans(right, self.identity))
            await self._verify()
            payload = self._plan_listing_payload(listing, right)
            payload.update(selection_required=True, plan=None)
            return payload, "live"
        key = self._plans.get((right.key, args.plan_id))
        if key is None:
            raise PeppiError("PLAN_NOT_FOUND", "Call get_study_plan without plan_id, then select a version for this connection and study right.")
        self._stage = "selected HOPS read"
        plan = await self._observe(self.browser.read_plan(right, self.identity, key))
        if plan.listing.study_right_key != right.key or plan.listing.current_plan_id != key:
            raise PeppiError("STUDY_CONTEXT_CHANGED", "The acquired HOPS context does not match the selected version.")
        progress = None
        transcript = None
        if name == "get_study_progress":
            self._stage = "completed transcript read"
            transcript = self._bind(await self._observe(self.browser.read(right, self.identity)), right)
            self._stage = "HOPS consistency recheck"
            after = await self._observe(self.browser.read_plan(right, self.identity, key))
            if (after.id != plan.id or after.listing.study_right_key != right.key
                    or after.listing.current_plan_id != key):
                raise PeppiError("PLAN_CHANGED", "HOPS changed while comparing it with the transcript. Start a fresh query.")
            progress = study_progress(plan, transcript)
        await self._verify()
        payload = self._plan_listing_payload(plan.listing, right)
        selected = next(v for v in payload["available_plans"] if v["id"] == args.plan_id)
        # Private row IDs are replaced consistently in both tree and progress.
        node_ids = {n.id: "plan-row:" + hmac.new(self._secret, (right.key + ":" + key + ":" + n.id).encode(), hashlib.sha256).hexdigest() for n in plan.nodes}
        payload = {"assessment": assess(plan, progress, node_ids).model_dump(mode="json"), **payload}
        if progress is not None:
            for collection in (progress["requirements"], progress["groups"], progress["issues"]):
                for row in collection:
                    if row["node_id"] is not None:
                        row["node_id"] = node_ids[row["node_id"]]
            payload.update(plan=selected, progress=progress,
                transcript_provenance=self._provenance(transcript.study_rights[0].provenance.model_dump(mode="json"), "live"))
        else:
            nodes = [{**n.model_dump(mode="json"), "id": node_ids[n.id],
                      "parent_id": node_ids.get(n.parent_id)} for n in plan.nodes]
            payload.update(plan={**selected, "name": plan.listing.current_plan_name, "nodes": nodes,
                "source_completed_credits": str(plan.source_completed_credits), "source_outside_credits": str(plan.source_outside_credits),
                "source_total_credits":str(plan.source_total_credits), "source_reconciliation_issues":list(plan.reconciliation_issues),
                "planned_credits": plan.planned_credits.model_dump(mode="json"), "target_credits": plan.target_credits.model_dump(mode="json")})
        payload["provenance"].update(completeness_scope="unfiltered_rendered_tree_of_selected_recorded_hops_version",
            completeness="partial" if plan.reconciliation_issues else "complete_for_rendered_view",
            snapshot_id="live-plan-snapshot:" + hmac.new(self._secret, plan.id.encode(), hashlib.sha256).hexdigest(),
            warnings=["This is the recorded HOPS view. Curriculum choice and equivalence rules are not fully exposed; no degree audit or eligibility decision is implied."]
                + (["HOPS source totals conflict. Treat this plan view as partial; inspect source_reconciliation_issues and individual group totals."] if plan.reconciliation_issues else []))
        return payload, "live"

    async def _verify(self):
        self._stage = "fresh account verification"
        if self.browser is None:
            raise PeppiError("SIGN_IN_NEEDED", "Call connect_personal and complete sign-in in the isolated browser.")
        identity = await self._observe(self.browser.check())
        if (not identity.principal or not 0 < len(identity.rights) <= 100
                or len({right.key for right in identity.rights}) != len(identity.rights)):
            raise PeppiError("PERSONAL_VIEW_INVALID", "The authenticated study context could not be established.")
        if self.identity is not None and identity != self.identity:
            raise PeppiError("STUDY_CONTEXT_CHANGED", "The account or available study contexts changed. Reconnect and list study rights again.")
        self.identity = identity
        self.last_verified_at = datetime.now(timezone.utc).isoformat()
        self.state = "connected"
        return identity

    def _right(self, right_id):
        for right in self.identity.rights:
            if self._id(right.key) == right_id:
                return right
        raise PeppiError("STUDY_RIGHT_NOT_FOUND", "Select a study right returned by this connection's list_study_rights.")

    def _bind(self, snapshot, right):
        if len(snapshot.study_rights) != 1:
            raise PeppiError("PERSONAL_VIEW_INVALID", "The source did not return one explicit study right.")
        expected = "ui-right:" + hashlib.sha256(right.key.encode()).hexdigest()
        if snapshot.study_rights[0].id != expected:
            raise PeppiError("STUDY_CONTEXT_CHANGED", "The acquired transcript belongs to a different study right. No records were returned.")
        right_id = self._id(right.key)
        source_id = "live:" + hmac.new(self._secret, snapshot.id.encode(), hashlib.sha256).hexdigest()
        prov = snapshot.study_rights[0].provenance.model_copy(update={
            "source_id": source_id, "study_right_id": right_id,
            "warnings": tuple(w for w in snapshot.study_rights[0].provenance.warnings
                              if not w.startswith("This normalization does not establish")),
        })
        bound = snapshot.model_copy(update={"id": source_id,
            "study_rights": (snapshot.study_rights[0].model_copy(update={
                "id": right_id, "programme": right.programme, "provenance": prov}),),
            "achievements": tuple(row.model_copy(update={"provenance": prov}) for row in snapshot.achievements),
            "source_groups": tuple(row.model_copy(update={"provenance": prov}) for row in snapshot.source_groups)})
        return Snapshot.model_validate(bound.model_dump())

    @staticmethod
    def _provenance(payload, mode):
        # Enrich live responses only; immutable-mode wire shapes stay unchanged.
        if isinstance(payload, dict):
            if "source_id" in payload and "retrieved_at" in payload:
                payload.update(source_mode=mode, source_url=TRANSCRIPT_URL,
                               completeness_scope="completed_courses_for_selected_study_right")
            for value in payload.values():
                LivePersonal._provenance(value, mode)
        elif isinstance(payload, list):
            for value in payload:
                LivePersonal._provenance(value, mode)
        return payload

    def _encode(self, key, offset):
        raw = json.dumps([key, offset], separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw + hmac.digest(self._secret, raw, "sha256")).decode()

    def _decode(self, cursor, binding):
        try:
            token = base64.b64decode(cursor, altchars=b"-_", validate=True)
            raw, signature = token[:-32], token[-32:]
            if not hmac.compare_digest(signature, hmac.digest(self._secret, raw, "sha256")):
                raise ValueError
            key, offset = json.loads(raw)
            page = self._pages.get(key)
            if page is None or page.expires <= self.clock():
                self._pages.pop(key, None)
                raise PeppiError("CURSOR_EXPIRED", "Start a new query; the retained snapshot has expired or was evicted.")
            if page.binding != binding or type(offset) is not int or not 0 < offset < len(page.snapshot.achievements):
                raise ValueError
            return key, offset, page.snapshot
        except PeppiError:
            raise
        except (ValueError, TypeError, KeyError, UnicodeError):
            raise PeppiError("INVALID_CURSOR", "Cursor is invalid for this connection, study right, filter or page size.") from None

    async def call(self, name, args):
        if name == "get_connection_status":
            return self.status(), "live"
        if name == "disconnect_personal":
            await self.close()
            return self.status(), "live"
        ticket = await self._acquire()
        generation = self._generation
        task = asyncio.create_task(self._run(name, args, generation))
        self._active = task
        try:
            result = await asyncio.shield(task)
            # Disconnect can run after the operation finishes but before this
            # waiting caller resumes. Recheck at the final delivery boundary.
            if generation != self._generation:
                raise PeppiError("SIGN_IN_NEEDED", "The connection ended before delivery. No records were returned.")
            return result
        except asyncio.CancelledError:
            if generation != self._generation:
                raise PeppiError("SIGN_IN_NEEDED", "The connection was disconnected. No records were returned.") from None
            task.cancel()
            await self.close()
            raise
        finally:
            # Keep the slot until even a cancellation-resistant backend has ended.
            def release(_=None):
                if self._active is task:
                    self._active = None
                self._release(ticket)
                if task.done() and not task.cancelled():
                    task.exception()  # Consume a discarded late failure.
            if task.done():
                release()
            else:
                task.add_done_callback(release)

    async def _run(self, name, args, generation):
        self._stage = "session operation"
        try:
            remaining = self._cooldown - self.clock()
            if remaining > 0:
                raise PeppiError("RATE_LIMITED", "Peppi requested a pause; no request was sent.", retryable=True, retry_after_seconds=math.ceil(remaining))
            async with asyncio.timeout(self.deadline):
                result = await self._call(name, args)
            if generation != self._generation:
                raise PeppiError("SIGN_IN_NEEDED", "The connection ended. No records were returned.")
            return result
        except asyncio.CancelledError:
            if generation == self._generation:
                await self.close()
            raise
        except TimeoutError:
            await self.close("unavailable")
            raise PeppiError("PERSONAL_READ_TIMEOUT", "The personal operation timed out during " + self._stage + ". Reconnect before retrying.", retryable=True) from None
        except PeppiError as exc:
            if generation != self._generation:
                raise PeppiError("SIGN_IN_NEEDED", "The connection ended. No records were returned.") from None
            if exc.code == "RATE_LIMITED":
                self._cooldown = max(self._cooldown, self.clock() + (exc.retry_after_seconds or 60))
            elif exc.code == "SIGN_IN_NEEDED":
                if self.state == "connected":
                    await self.close("expired")
                    raise PeppiError("SESSION_EXPIRED", "The authenticated session ended. Reconnect; no cached records were returned.") from None
                if name == "connect_personal" and self.browser is not None:
                    self.state = "awaiting_login"
                    return self.status(), "live"
            elif exc.code in {"ACCESS_DENIED", "STUDY_CONTEXT_CHANGED", "BROWSER_UNAVAILABLE", "BROWSER_DEPENDENCY_MISSING"}:
                await self.close("denied" if exc.code == "ACCESS_DENIED" else "unavailable")
            raise
        except Exception:
            await self.close("unavailable")
            raise PeppiError("PERSONAL_READ_FAILED", "The browser operation failed. Reconnect before retrying; source details were omitted.") from None

    async def _call(self, name, args):
        if name == "get_connection_status":
            return self.status(), "live"
        if name == "disconnect_personal":
            await self.close()
            return self.status(), "live"
        if name == "connect_personal":
            if self.browser is None:
                validate = getattr(self.factory, "validate_dependencies", None)
                if validate is not None:
                    validate()
                if self.cleanup_pending or self._retired or self._storage_pending:
                    await self._wait_cleanup(self._start_cleanup("signed_out"))
                    if self.cleanup_pending or self._cleanup_task is not None:
                        raise self._cleanup_error()
                self._clear()
                self.browser = self.factory()
                await self._observe(self.browser.open())
                self.state = "awaiting_login"
            else:
                await self._verify()
            return self.status(), "live"
        await self._verify()
        if name == "list_study_rights":
            return {"items": [{"id": self._id(right.key), "programme": right.programme,
                               "linked_study_right_ids": [self._id(key) for key in right.linked_keys],
                               "provenance": {"source_mode": "live", "retrieved_at": self.last_verified_at,
                                              "source_url": TRANSCRIPT_URL, "completeness_scope": "authenticated_study_right_selector"}}
                              for right in self.identity.rights], "next_cursor": None, "source_mode": "live"}, "live"
        right = self._right(args.study_right_id)
        if name in {"get_study_plan", "get_study_progress"}:
            return await self._study_plan(name, args, right)
        if name == "list_achievements" and args.status != "completed":
            raise PeppiError("CAPABILITY_UNAVAILABLE", "This live reader supports completed achievements only.")
        cached = name == "list_achievements" and args.cursor is not None
        binding = (args.study_right_id, args.status, args.limit) if isinstance(args, AchievementArguments) else None
        if cached:
            key, offset, snapshot = self._decode(args.cursor, binding)
        else:
            self._stage = "completed transcript read"
            snapshot = self._bind(await self._observe(self.browser.read(right, self.identity)), right)
            await self._verify()
            offset, key = 0, secrets.token_hex(16)
        mode = "cached" if cached else "live"
        if name == "get_credit_summary":
            return self._provenance(credit_summary(snapshot, args.study_right_id).model_dump(mode="json"), mode), mode
        end = offset + args.limit
        if not cached and end < len(snapshot.achievements):
            now = self.clock()
            self._pages = OrderedDict((k, v) for k, v in self._pages.items() if v.expires > now)
            self._pages[key] = _Page(snapshot, binding, now + self.ttl)
            while len(self._pages) > self.capacity:
                self._pages.popitem(last=False)
        payload = {"study_right_id": args.study_right_id,
                   "items": [row.model_dump(mode="json") for row in snapshot.achievements[offset:end]],
                   "matching_records": len(snapshot.achievements),
                   "next_cursor": self._encode(key, end) if end < len(snapshot.achievements) else None,
                   "provenance": snapshot.study_rights[0].provenance.model_dump(mode="json"),
                   "warnings": ["Raw source rows are not a credit total; use get_credit_summary."]}
        return self._provenance(payload, mode), mode

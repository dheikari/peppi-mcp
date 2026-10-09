"""Owned browser worker with bounded JSON IPC and Windows process-tree cleanup."""

import asyncio
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass

from peppi_mcp.errors import PeppiError
from peppi_mcp.models import Snapshot
from peppi_mcp.study_plan_models import PlanListing, PlanSnapshot
from peppi_mcp.services.live import Identity, SourceRight
from peppi_mcp.runtime_storage import RuntimeLease, RuntimeLeaseCreationError, CleanupWorker
from peppi_mcp.worker_protocol import MAX_REPLY, MAX_REQUEST, SAFE_ERRORS, decode, validate_reply, validate_request

@dataclass
class _Retiring:
    process: object
    job: object
    lease: RuntimeLease | None
    interrupted: bool


class FirefoxProcess:
    method = "browser_session_json_rights_and_rendered_transcript"

    def __init__(self, *, browser="firefox"):
        if browser not in {"firefox", "chrome"}:
            raise ValueError("Unsupported browser selection")
        self.browser_name = browser
        self.process = None
        self.job = None
        self.lease = None
        self.cleanup_pending = False
        self._sequence = 0
        self._broken = False
        self._request_lock = asyncio.Lock()
        self._cleanup_task = None
        self._retiring = None
        self._cleanup_worker = CleanupWorker()

    @staticmethod
    def validate_dependencies():
        if os.name != "nt":
            raise PeppiError("BROWSER_UNAVAILABLE", "Live browser support is currently verified on Windows only.")
        try:
            import win32api
            import win32con
            import win32job
            import selenium
        except ImportError:
            raise PeppiError("BROWSER_DEPENDENCY_MISSING", "Install the project with its optional [live] extra, including Windows process support.") from None

    async def open(self):
        # The worker waits for an explicit open command before creating children.
        # Assigning the job first guarantees cleanup of this browser tree only.
        self.validate_dependencies()
        import win32api
        import win32con
        import win32job
        try:
            self.lease = RuntimeLease(recover=False)
            self.cleanup_pending = self.lease.cleanup_pending
            self.process = await asyncio.create_subprocess_exec(
            sys.executable, "-u", "-m", "peppi_mcp.browser_worker",
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, limit=MAX_REPLY + 1,
            creationflags=subprocess.CREATE_NO_WINDOW,
                env={**os.environ, "PYTHONUTF8": "1", "PEPPI_OWNED_PROFILE_ROOT": str(self.lease.path), "PEPPI_BROWSER": self.browser_name},
            )
            self.job = win32job.CreateJobObject(None, "")
            info = win32job.QueryInformationJobObject(self.job, win32job.JobObjectExtendedLimitInformation)
            info["BasicLimitInformation"]["LimitFlags"] |= win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            win32job.SetInformationJobObject(self.job, win32job.JobObjectExtendedLimitInformation, info)
            handle = win32api.OpenProcess(win32con.PROCESS_SET_QUOTA | win32con.PROCESS_TERMINATE, False, self.process.pid)
            try:
                win32job.AssignProcessToJobObject(self.job, handle)
            finally:
                handle.Close()
            await self._request("open")
        except BaseException as exc:
            if isinstance(exc, RuntimeLeaseCreationError):
                self.lease = exc.lease
            await self.close()
            raise

    async def _request(self, action, **payload):
        async with self._request_lock:
            return await self._exchange(action, payload)

    async def _exchange(self, action, payload):
        if self._broken or self.process is None or self.process.returncode is not None:
            raise PeppiError("BROWSER_UNAVAILABLE", "The connector browser worker is closed.")
        self._sequence += 1
        try:
            request = validate_request({"id": self._sequence, "action": action, **payload})
            encoded = (json.dumps(request) + "\n").encode()
            if len(encoded) > MAX_REQUEST:
                raise ValueError
            self.process.stdin.write(encoded)
            await self.process.stdin.drain()
            line = await self.process.stdout.readline()
            reply = validate_reply(decode(line, MAX_REPLY), request)
            if not reply["ok"]:
                raise PeppiError(reply["code"], SAFE_ERRORS[reply["code"]], retryable=reply["retryable"], retry_after_seconds=reply["retry_after_seconds"])
            return reply["data"]
        except PeppiError:
            raise
        except asyncio.CancelledError:
            self._broken = True
            raise
        except Exception:
            self._broken = True
            raise PeppiError("BROWSER_UNAVAILABLE", "The browser worker returned an invalid or interrupted response.") from None

    async def check(self):
        data = await self._request("check")
        if (set(data) != {"principal", "rights"} or not isinstance(data["principal"], str) or not 1 <= len(data["principal"]) <= 100
                or not isinstance(data["rights"], list) or not 1 <= len(data["rights"]) <= 100
                or any(set(r) != {"key", "programme", "linked_keys"} or not isinstance(r["key"], str)
                       or not isinstance(r["programme"], str) or not isinstance(r["linked_keys"], list)
                       or any(not isinstance(k, str) for k in r["linked_keys"]) for r in data["rights"])):
            self._broken = True
            raise PeppiError("BROWSER_UNAVAILABLE", "The worker returned an invalid study context.")
        return Identity(data["principal"], tuple(SourceRight(
            right["key"], right["programme"], tuple(right["linked_keys"])) for right in data["rights"]))

    async def read(self, right, identity):
        data = await self._request("read", right=asdict(right), identity=asdict(identity))
        return Snapshot.model_validate(data)

    async def list_plans(self, right, identity):
        return PlanListing.model_validate(await self._request("list_plans", right=asdict(right), identity=asdict(identity)))

    async def read_plan(self, right, identity, plan_key):
        return PlanSnapshot.model_validate(await self._request("read_plan", right=asdict(right), identity=asdict(identity), plan_key=plan_key))

    async def close(self):
        await self.close_with_deadline(asyncio.get_running_loop().time() + 10)

    async def close_with_deadline(self, deadline):
        if self._cleanup_task is None:
            if self._retiring is None:
                self._retiring = _Retiring(self.process, self.job, self.lease,
                                          self._broken or self._request_lock.locked())
                self.process = self.job = None
                self._broken = True
            record = self._retiring
            task = asyncio.create_task(self._cleanup(record, deadline))
            self._cleanup_task = task
            def completed(done):
                if self._cleanup_task is done:
                    self._cleanup_task = None
                    self.cleanup_pending = self._retiring is not None
                if not done.cancelled():
                    done.exception()
            task.add_done_callback(completed)
        task = self._cleanup_task
        # asyncio.wait does not cancel the owned task when its waiter is cancelled.
        await asyncio.wait({task}, timeout=max(0, deadline - asyncio.get_running_loop().time()))
        if not task.done():
            self.cleanup_pending = True

    async def wait_cleanup(self):
        if self._cleanup_task is not None:
            await asyncio.shield(self._cleanup_task)

    async def _cleanup(self, record, deadline):
        loop = asyncio.get_running_loop()
        try:
            process, job, lease = record.process, record.job, record.lease
            if process is not None and process.returncode is None and not record.interrupted:
                try:
                    async with asyncio.timeout_at(min(deadline, loop.time() + .5)):
                        self._sequence += 1
                        process.stdin.write((json.dumps({"id": self._sequence, "action": "close"}) + "\n").encode())
                        await process.stdin.drain()
                        await process.wait()
                except Exception:
                    pass
            if job is not None:
                import win32job
                win32job.TerminateJobObject(job, 0)
            if process is not None and process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                async with asyncio.timeout_at(deadline):
                    await process.wait()
            if job is not None:
                # Termination is asynchronous. A zero count verifies that no
                # owned child still has the profile open before deletion.
                while win32job.QueryInformationJobObject(job, win32job.JobObjectBasicAccountingInformation)["ActiveProcesses"]:
                    if loop.time() >= deadline:
                        raise TimeoutError
                    await asyncio.sleep(min(.05, max(0, deadline - loop.time())))
                job.Close()
                record.job = None
            record.process = None
            if lease is not None:
                for attempt in range(5):
                    if loop.time() >= deadline:
                        raise TimeoutError
                    try:
                        await self._cleanup_worker.run(lease.remove)
                        record.lease = self.lease = None
                        break
                    except OSError:
                        if attempt == 4 or loop.time() >= deadline:
                            raise
                        await asyncio.sleep(min(.2, max(0, deadline - loop.time())))
            self._retiring = None
            self.cleanup_pending = False
        except asyncio.CancelledError:
            self.cleanup_pending = True
            raise
        except Exception:
            self.cleanup_pending = True
            # Keep the exact ownership record for explicit bounded recovery.

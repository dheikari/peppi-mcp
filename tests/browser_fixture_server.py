"""Production MCP server with a local-fiction worker bootstrap, tests only."""
import asyncio
import json
import os
import time
from pathlib import Path
from peppi_mcp.server import main
import peppi_mcp.runtime_storage as storage

# Name only fixture jobs so the observer can establish exact membership rather
# than treating every PPID descendant (including OS helpers) as connector-owned.
process_record = os.environ.get("PEPPI_FIXTURE_PROCESS_RECORD")
if process_record:
    import uuid
    import win32job
    create_job = win32job.CreateJobObject
    def fixture_job(attributes, name):
        name = "Local\\peppi-fixture-" + uuid.uuid4().hex
        job = create_job(attributes, name)
        Path(process_record).with_suffix(".job").write_text(name)
        return job
    win32job.CreateJobObject = fixture_job

# Optional fictional diagnostics report categories only, never exception text,
# URLs, paths or browser state. They are absent from the packaged worker.
diagnostic = os.environ.get("PEPPI_FIXTURE_CLEANUP_RECORD")
if diagnostic:
    from tests.cleanup_diagnostics import removal_record, write_cleanup_evidence
    remove_lease = storage.RuntimeLease.remove
    removal_attempts = []
    removal_started = time.monotonic()
    def record_removal(error, path):
        detail = removal_record(error, path, len(removal_attempts) + 1, removal_started)
        removal_attempts.append(detail)
        write_cleanup_evidence(Path(diagnostic), removal_attempts)
    def diagnostic_removal(self):
        try:
            result = remove_lease(self)
        except Exception as exc:
            record_removal(exc, self.path)
            raise
        record_removal(None, self.path)
        return result
    storage.RuntimeLease.remove = diagnostic_removal

# Fault controls are restricted to this test bootstrap, never the shipped worker.
control = os.environ.get("PEPPI_FIXTURE_CLEANUP_CONTROL")
if control:
    control = Path(control)
    remove = storage.remove_owned
    def controlled_removal(*args):
        control.with_suffix(".started").touch()
        state = json.loads(control.read_text())
        while state.get("block"):
            time.sleep(.02)
            state = json.loads(control.read_text())
        if state.get("fail"):
            raise PermissionError("PRIVATE_SECRET")
        if state.get("sharing_refusals", 0):
            state["sharing_refusals"] -= 1
            temporary = control.with_suffix(".new")
            temporary.write_text(json.dumps(state))
            temporary.replace(control)
            error = PermissionError("PRIVATE_SECRET")
            error.winerror = 32
            raise error
        return remove(*args)
    storage.remove_owned = controlled_removal

create = asyncio.create_subprocess_exec
async def launch(*args, **kwargs):
    if args[-2:] == ("-m","peppi_mcp.browser_worker"):
        args = (*args[:-1],"tests.browser_fixture_worker")
        startup = os.environ.get("PEPPI_FIXTURE_STARTUP_RECORD")
        if startup:
            Path(startup).write_text(json.dumps({"stage":"worker launch"}))
    return await create(*args, **kwargs)
asyncio.create_subprocess_exec = launch
main()

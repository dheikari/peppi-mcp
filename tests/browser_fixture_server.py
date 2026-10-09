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
    remove_lease = storage.RuntimeLease.remove
    def diagnostic_removal(self):
        try:
            return remove_lease(self)
        except Exception as exc:
            location = None
            if getattr(exc, "filename", None):
                try:
                    location = len(Path(exc.filename).relative_to(self.path).parts)
                except ValueError:
                    pass
            longest = max((len(str(Path(folder) / name)) for folder, dirs, files in os.walk(self.path)
                           for name in (*dirs, *files)), default=0)
            context = exc.__context__
            Path(diagnostic).write_text(json.dumps({"stage":"profile removal", "error_type":type(exc).__name__, "winerror":getattr(exc,"winerror",None), "owned_directory_depth":location, "longest_path_characters":longest,
                "context_type":type(context).__name__ if context else None, "context_winerror":getattr(context,"winerror",None),
                "context_path_characters":len(str(getattr(context,"filename","") or ""))}))
            raise
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
        return remove(*args)
    storage.remove_owned = controlled_removal

create = asyncio.create_subprocess_exec
async def launch(*args, **kwargs):
    if args[-2:] == ("-m","peppi_mcp.browser_worker"):
        args = (*args[:-1],"tests.browser_fixture_worker")
    return await create(*args, **kwargs)
asyncio.create_subprocess_exec = launch
main()

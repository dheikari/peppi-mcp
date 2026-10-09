"""Fictional stuck filesystem work must not keep the server process alive."""
import asyncio
import json
import threading

from peppi_mcp.adapters.firefox_process import FirefoxProcess
from peppi_mcp.runtime_storage import RuntimeLease
import peppi_mcp.runtime_storage as storage

def blocked(*args):
    threading.Event().wait()
storage.remove_owned = blocked

async def main():
    browser = FirefoxProcess()
    browser.lease = RuntimeLease()
    path = browser.lease.path
    await browser.close_with_deadline(asyncio.get_running_loop().time() + .05)
    print(json.dumps({"pending": browser.cleanup_pending, "path":str(path)}), flush=True)

asyncio.run(main())

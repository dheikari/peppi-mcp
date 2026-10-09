"""A disposable parent to test kernel job cleanup after abrupt process exit."""
import asyncio
import json
from peppi_mcp.adapters.firefox_process import FirefoxProcess

create = asyncio.create_subprocess_exec
async def launch(*args, **kwargs):
    return await create(*args[:-1],"tests.process_tree_worker",**kwargs)
asyncio.create_subprocess_exec = launch

async def main():
    browser = FirefoxProcess()
    request = browser._request
    child = None
    async def capture(action, **payload):
        nonlocal child
        response = await request(action, **payload)
        if action=="open": child=response["child_pid"]
        return response
    browser._request = capture
    await browser.open()
    (browser.lease.path/"fictional-profile").mkdir()
    (browser.lease.path/"fictional-profile"/"cookie").write_text("FICTIONAL_PRIVATE_COOKIE")
    print(json.dumps({"worker":browser.process.pid,"child":child,"root":str(browser.lease.path)}),flush=True)
    await asyncio.Event().wait()
asyncio.run(main())

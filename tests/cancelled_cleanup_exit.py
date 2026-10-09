"""Shutdown cancellation must not start another indefinitely awaited worker."""
import asyncio
import threading

from peppi_mcp.services.live import LivePersonal

async def main():
    entered = asyncio.Event()
    class Browser:
        async def close(self):
            entered.set()
            await asyncio.Event().wait()
    def recovery():
        threading.Event().wait()
    service = LivePersonal(Browser, recover=recovery)
    service.browser = Browser()
    asyncio.create_task(service.close())
    await entered.wait()
    # Returning cancels outstanding tasks as asyncio.run shuts down.

asyncio.run(main())

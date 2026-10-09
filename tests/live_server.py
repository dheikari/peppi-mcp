"""Fictional subprocess backend for testing the real live MCP boundary."""

import asyncio

from mcp.server.stdio import stdio_server

from peppi_mcp.server import create_live_server
from peppi_mcp.services.live import LivePersonal
from tests.unit.test_study_plan import PlanBrowser


async def main():
    server = create_live_server(LivePersonal(PlanBrowser))
    async with stdio_server() as (incoming, outgoing):
        await server.run(incoming, outgoing, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())

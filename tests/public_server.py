"""Test-only subprocess server: public tools backed exclusively by fiction."""

import asyncio
import socket

from mcp.server.stdio import stdio_server

from catalogue_fixtures import FixtureFetcher
from peppi_mcp.config import Config
from peppi_mcp.server import create_server
from peppi_mcp.services.catalogue import PublicCatalogue


def forbidden(*args, **kwargs):
    raise AssertionError("Network access is forbidden in the test server")


async def main():
    socket.socket.connect = forbidden
    socket.create_connection = forbidden
    server = create_server(Config(public_catalogue=True), public_catalogue=PublicCatalogue(FixtureFetcher()))
    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())

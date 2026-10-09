import asyncio
import sys
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters


def test_public_tools_over_real_stdio_without_network():
    async def check():
        params = StdioServerParameters(command=sys.executable, args=[str(Path(__file__).parents[1] / "public_server.py")])
        async with Client(params, read_timeout_seconds=15) as client:
            tools = (await client.list_tools()).tools
            assert len(tools) == 7
            assert {tool.name for tool in tools if tool.annotations.open_world_hint} == {"search_courses", "get_course", "list_course_offerings"}
            first = await client.call_tool("search_courses", {"query": "DEMO", "limit": 1})
            assert not first.is_error and first.structured_content["source_mode"] == "live"
            second = await client.call_tool("search_courses", {"query": "DEMO", "limit": 1, "cursor": first.structured_content["data"]["next_cursor"]})
            assert second.structured_content["data"]["items"][0]["id"] == "102"
            assert second.structured_content["source_mode"] == "cached"
            course = await client.call_tool("get_course", {"course_id": "101"})
            assert course.structured_content["data"]["credits"] == "2.5"
            offers = await client.call_tool("list_course_offerings", {"course_id": "101", "collection": "past"})
            assert len(offers.structured_content["data"]["items"]) == 2
            personal = await client.call_tool("get_credit_summary", {"study_right_id": "demo-main"})
            assert personal.structured_content["source_mode"] == "synthetic"
            assert (await client.call_tool("list_enrolments", {})).is_error
    asyncio.run(check())

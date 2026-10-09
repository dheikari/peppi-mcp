import asyncio
import sys

from mcp import Client
from mcp.client.stdio import StdioServerParameters


def test_explicit_connection_and_pinned_pages_through_stdio():
    async def run():
        params = StdioServerParameters(command=sys.executable, args=["-m", "tests.live_server"])
        async with Client(params, read_timeout_seconds=15) as client:
            tools = {tool.name: tool for tool in (await client.list_tools()).tools}
            assert set(tools) == {"get_connection_status", "list_study_rights", "list_achievements", "get_credit_summary", "connect_personal", "disconnect_personal", "get_study_plan", "get_study_progress"}
            assert not tools["connect_personal"].annotations.read_only_hint
            assert tools["list_achievements"].annotations.open_world_hint
            assert tools["list_achievements"].input_schema["properties"]["status"]["enum"] == ["completed"]
            for name, tool in tools.items():
                if name in {"get_study_plan", "get_study_progress"}:
                    assert tool.meta == {"anthropic/maxResultSizeChars": 500_000}
                else:
                    assert tool.meta is None
            signed_out = await client.call_tool("list_study_rights", {})
            assert signed_out.is_error and signed_out.structured_content["error"]["code"] == "SIGN_IN_NEEDED"
            for state in ("awaiting_login", "connected"):
                response = await client.call_tool("connect_personal", {})
                assert response.structured_content["data"]["personal_connection"] == state
            response = await client.call_tool("list_study_rights", {})
            right = response.structured_content["data"]["items"][0]["id"]
            choices = (await client.call_tool("get_study_plan", {"study_right_id":right})).structured_content["data"]
            selected = {"study_right_id":right,"plan_id":choices["current_plan_id"]}
            plan = (await client.call_tool("get_study_plan", selected)).structured_content["data"]
            progress = (await client.call_tool("get_study_progress", selected)).structured_content["data"]
            assert len(plan["plan"]["nodes"]) == 4
            assert progress["progress"]["status"] == "source_credits_reconciled"
            assert progress["progress"]["graduation_eligibility"] is None
            args = {"study_right_id": right, "limit": 1}
            first = (await client.call_tool("list_achievements", args)).structured_content
            second = (await client.call_tool("list_achievements", {**args, "cursor": first["data"]["next_cursor"]})).structured_content
            assert first["source_mode"] == "live" and second["source_mode"] == "cached"
            assert first["data"]["provenance"]["retrieved_at"] == second["data"]["provenance"]["retrieved_at"]
            summaries = await asyncio.gather(*(client.call_tool("get_credit_summary", {"study_right_id": right}) for _ in range(3)))
            assert all(result.structured_content["data"]["total_credits"] == "1.5" for result in summaries)
            unsupported = await client.call_tool("list_achievements", {**args, "status": "all"})
            assert unsupported.is_error and unsupported.structured_content["error"]["code"] == "CAPABILITY_UNAVAILABLE"
            await client.call_tool("disconnect_personal", {})
            after = await client.call_tool("list_achievements", {**args, "cursor": first["data"]["next_cursor"]})
            assert after.is_error and after.structured_content["error"]["code"] == "SIGN_IN_NEEDED"
    asyncio.run(run())

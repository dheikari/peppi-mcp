import asyncio
import json
import os
import subprocess
import sys

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from peppi_mcp.demo import demonstrate


def test_official_client_demonstration():
    report = asyncio.run(demonstrate())
    assert report["transport"] == "stdio subprocess"
    assert report["client_shutdown"] == "completed"


def test_discovery_pagination_unicode_and_concurrent_reads():
    async def check():
        params = StdioServerParameters(command=sys.executable, args=["-m", "peppi_mcp", "--mode", "synthetic"])
        async with Client(params, read_timeout_seconds=15) as client:
            tools = (await client.list_tools()).tools
            assert {tool.name for tool in tools} == {"get_connection_status", "list_study_rights", "list_achievements", "get_credit_summary"}
            assert all(tool.annotations.read_only_hint and not tool.annotations.open_world_hint for tool in tools)
            assert all(tool.meta is None for tool in tools)
            listing = next(tool for tool in tools if tool.name == "list_achievements")
            assert listing.input_schema["properties"]["limit"]["maximum"] == 100
            rights = await client.call_tool("list_study_rights", {})
            connection = (await client.call_tool("get_connection_status", {})).structured_content["data"]
            assert connection["personal_access"]["state"] == "live_mode_available"
            assert connection["personal_access"]["client_authentication"]
            assert connection["personal_access"]["live_data_verified"] is True
            assert connection["personal_access"]["is_current_health_check"] is False
            assert len(rights.structured_content["data"]["items"]) == 5
            first = await client.call_tool("list_achievements", {"study_right_id": "demo-main", "limit": 1})
            first_data = first.structured_content["data"]
            assert "ä, ö, š" in first_data["items"][0]["title"]
            second = await client.call_tool("list_achievements", {"study_right_id": "demo-main", "limit": 1, "cursor": first_data["next_cursor"]})
            assert second.structured_content["data"]["items"][0]["id"] == "b"
            empty = await client.call_tool("list_achievements", {"study_right_id": "demo-empty"})
            assert empty.structured_content["data"]["items"] == [] and not empty.is_error
            responses = await asyncio.gather(*(client.call_tool("get_credit_summary", {"study_right_id": "demo-main"}) for _ in range(3)))
            assert all(r.structured_content["data"]["total_credits"] == "15.5" for r in responses)
            for args, code in [({"study_right_id": "unknown"}, "STUDY_RIGHT_NOT_FOUND"),
                               ({"study_right_id": "demo-main", "cursor": "invalid"}, "INVALID_CURSOR"),
                               ({"study_right_id": "demo-main", "limit": "2"}, "INVALID_ARGUMENT")]:
                result = await client.call_tool("list_achievements", args)
                assert result.is_error and result.structured_content["error"]["code"] == code
    asyncio.run(check())


def test_raw_protocol_stdout_and_clean_eof_shutdown():
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "wire-test", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "get_credit_summary", "arguments": {"study_right_id": "demo-main"}}},
    ]
    async def exchange():
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "peppi_mcp", "--mode", "synthetic",
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        responses = []
        try:
            for message in messages:
                process.stdin.write((json.dumps(message) + "\n").encode())
                await process.stdin.drain()
                if "id" not in message:
                    continue
                while True:
                    line = await asyncio.wait_for(process.stdout.readline(), timeout=15)
                    assert line, "Server closed stdout before responding"
                    # Any banner/log on stdout fails JSON decoding.
                    response = json.loads(line)
                    responses.append(response)
                    if response.get("id") == message["id"]:
                        break
            # EOF only after the pending calls finish: normal stdio shutdown.
            process.stdin.close()
            await asyncio.wait_for(process.wait(), timeout=15)
            responses.extend(json.loads(line) for line in (await process.stdout.read()).splitlines())
            stderr = (await process.stderr.read()).decode()
            assert process.returncode == 0, stderr
            return responses
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
    responses = asyncio.run(exchange())
    assert responses and all(row["jsonrpc"] == "2.0" for row in responses)
    by_id = {row.get("id"): row for row in responses}
    assert by_id[1]["result"]["protocolVersion"] == "2025-11-25"
    assert len(by_id[2]["result"]["tools"]) == 4
    assert by_id[3]["result"]["structuredContent"]["data"]["total_credits"] == "15.5"


def test_bad_startup_mode_is_stderr_only():
    completed = subprocess.run([sys.executable, "-m", "peppi_mcp", "--mode", "unsupported"], capture_output=True, text=True, timeout=15)
    assert completed.returncode != 0 and not completed.stdout
    assert "CONFIGURATION_ERROR" in completed.stderr
    assert "supported modes" in completed.stderr
    assert "Traceback" not in completed.stderr

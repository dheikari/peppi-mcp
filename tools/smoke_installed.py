"""Run outside the source checkout with a clean environment's Python."""
import asyncio
import json
import sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
import peppi_mcp


async def main():
    assert peppi_mcp.__version__ == "0.1.0a1"
    assert "site-packages" in Path(peppi_mcp.__file__).parts
    for mode, count in (("synthetic",4),("live",8)):
        async with Client(StdioServerParameters(command=sys.executable,args=["-m","peppi_mcp","--mode",mode])) as client:
            assert len((await client.list_tools()).tools) == count
            result = (await client.call_tool("get_connection_status",{})).structured_content
            assert result["ok"]
            if mode == "live":
                assert result["data"]["personal_connection"] == "signed_out" and result["data"]["read_mechanism"] is None
                denied = (await client.call_tool("get_study_plan",{"study_right_id":"unverified"})).structured_content
                assert denied["error"]["code"] == "SIGN_IN_NEEDED"
                if sys.argv[1] == "core":
                    missing = (await client.call_tool("connect_personal",{})).structured_content
                    assert missing["error"]["code"] == "BROWSER_DEPENDENCY_MISSING"
            else:
                summary = (await client.call_tool("get_credit_summary",{"study_right_id":"demo-main"})).structured_content
                assert summary["data"]["total_credits"] == "15.5"
    print(json.dumps({"installed_version":peppi_mcp.__version__,"environment":sys.argv[1],"stdio_smoke":"passed"}))


asyncio.run(main())

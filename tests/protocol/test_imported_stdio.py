import asyncio
import json
import subprocess
import sys

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from peppi_mcp.import_cli import import_file
from tests.transcript_fixtures import pdf_bytes


def test_imported_snapshot_through_actual_sdk_client(tmp_path):
    source = tmp_path / "fictional.pdf"
    source.write_bytes(pdf_bytes())
    store = tmp_path / "imports.sqlite3"
    report = import_file(source, profile="fictional", study_right_id="test-right", store_path=store)
    args = ["-m", "peppi_mcp", "--mode", "imported", "--profile", "fictional", "--snapshot", report["snapshot_id"], "--import-store", str(store)]
    async def check():
        async with Client(StdioServerParameters(command=sys.executable, args=args), read_timeout_seconds=15) as client:
            tools = (await client.list_tools()).tools
            assert len(tools) == 4 and all(t.annotations.read_only_hint and not t.annotations.open_world_hint for t in tools)
            status = await client.call_tool("get_connection_status", {})
            assert status.structured_content["data"]["mode"] == "imported"
            assert status.structured_content["data"]["personal_access"]["state"] == "live_mode_available"
            assert status.structured_content["data"]["personal_access"]["live_data_verified"] is True
            assert status.structured_content["data"]["personal_connection"] == "not_enabled"
            assert status.structured_content["data"]["sources"][0]["source_sha256"] == report["source_sha256"]
            rights = await client.call_tool("list_study_rights", {})
            assert [r["id"] for r in rights.structured_content["data"]["items"]] == ["test-right"]
            records, cursor = [], None
            while True:
                arguments = {"study_right_id": "test-right", "status": "all", "limit": 1}
                if cursor:
                    arguments["cursor"] = cursor
                result = await client.call_tool("list_achievements", arguments)
                assert not result.is_error
                assert json.loads(result.content[0].text) == result.structured_content
                records.extend(result.structured_content["data"]["items"])
                cursor = result.structured_content["data"]["next_cursor"]
                if not cursor:
                    break
            assert len(records) == 3 and "ä and ö" in records[0]["title"]
            summary = await client.call_tool("get_credit_summary", {"study_right_id": "test-right"})
            data = summary.structured_content["data"]
            assert data["total_credits"] == "3.5" and data["difference_from_source_total"] == "0.0"
            assert data["provenance"]["source_mode"] == "imported" and len(data["source_groups"]) == 2
            assert (await client.call_tool("get_study_plan", {})).is_error
            assert (await client.call_tool("list_achievements", {"study_right_id": "other"})).is_error
    asyncio.run(check())
    demo = subprocess.run([sys.executable, "-m", "peppi_mcp.demo", *args[2:], "--study-right", "test-right"], capture_output=True, text=True, timeout=30)
    assert demo.returncode == 0 and demo.stderr == "", demo.stderr
    output = json.loads(demo.stdout)
    assert output["mode"] == "imported" and output["achievement_count"] == 3
    assert output["credit_summary"]["total_credits"] == "3.5" and output["client_shutdown"] == "completed"


def test_missing_import_startup_has_no_stdout_or_fallback(tmp_path):
    process = subprocess.run([sys.executable, "-m", "peppi_mcp", "--mode", "imported", "--profile", "missing", "--snapshot", "import:missing", "--import-store", str(tmp_path / "missing.sqlite3")], capture_output=True, text=True, timeout=15)
    assert process.returncode != 0 and process.stdout == ""
    assert "IMPORT_NOT_FOUND" in process.stderr and "Traceback" not in process.stderr
    assert str(tmp_path) not in process.stderr and not list(tmp_path.iterdir())

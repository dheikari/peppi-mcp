"""A real official-SDK client launching the installed server over stdio."""

import asyncio
import argparse
import json
import sys
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters
from peppi_mcp.config import Config


async def demonstrate(public_catalogue: bool = False) -> dict:
    parameters = StdioServerParameters(command=sys.executable, args=["-m", "peppi_mcp", "--mode", "synthetic", *(["--public-catalogue"] if public_catalogue else [])])
    async with Client(parameters, read_timeout_seconds=45) as client:
        tools = await client.list_tools()
        status = await client.call_tool("get_connection_status", {})
        summary = await client.call_tool("get_credit_summary", {"study_right_id": "demo-main"})
        partial = await client.call_tool("get_credit_summary", {"study_right_id": "demo-ambiguous"})
        invalid = await client.call_tool("list_achievements", {"study_right_id": "demo-main", "limit": 0})
        unavailable = await client.call_tool("list_enrolments", {})
        assert not status.is_error and status.structured_content["data"]["mode"] == "synthetic"
        assert summary.structured_content["data"]["total_credits"] == "15.5"
        assert partial.structured_content["data"]["total_credits"] is None
        assert invalid.is_error and invalid.structured_content["error"]["code"] == "INVALID_ARGUMENT"
        assert unavailable.is_error and unavailable.structured_content["error"]["code"] == "CAPABILITY_UNAVAILABLE"
        report = {
            "transport": "stdio subprocess", "server": client.server_info.name,
            "protocol_version": client.protocol_version, "tools": [tool.name for tool in tools.tools],
            "mode": "synthetic", "demo_main_credits": "15.5", "ambiguous_total": None,
            "invalid_input": "INVALID_ARGUMENT", "unsupported_capability": "CAPABILITY_UNAVAILABLE",
        }
        if public_catalogue:
            async def read(name, arguments):
                response = await client.call_tool(name, arguments)
                if response.is_error:
                    raise RuntimeError(f"Public demonstration failed: {response.structured_content['error']['code']}")
                return response.structured_content
            search = await read("search_courses", {"query": "XAKA0103", "limit": 1})
            ids = [item["id"] for item in search["data"]["items"]]
            cursor = search["data"]["next_cursor"]
            page_count = 1
            while cursor and page_count < 10:
                page = await read("search_courses", {"query": "XAKA0103", "limit": 1, "cursor": cursor})
                assert page["source_mode"] == "cached"
                ids.extend(item["id"] for item in page["data"]["items"])
                cursor = page["data"]["next_cursor"]
                page_count += 1
            assert cursor is None and "7300" in ids
            course = await read("get_course", {"course_id": "7300"})
            assert course["data"]["code"] == "XAKA0103"
            past = await read("list_course_offerings", {"course_id": "7300", "collection": "past"})
            sample = next(item for item in past["data"]["items"] if item["id"] == "9906")
            assert (sample["start_date"], sample["end_date"]) == ("2020-03-17", "2020-04-22")
            boundary = await read("list_course_offerings", {"course_id": "7300", "collection": "past", "date_from": "2020-04-22", "date_to": "2020-04-22"})
            assert [item["id"] for item in boundary["data"]["items"]] == ["9906"]
            current = await read("list_course_offerings", {"course_id": "7300"})
            report["public_catalogue"] = {
                "source_mode": course["source_mode"], "search_pages": page_count, "course_ids": ids,
                "course_code": course["data"]["code"], "credits": course["data"]["credits"],
                "past_offerings_received": past["data"]["retrieved_count"],
                "current_offerings_received": current["data"]["retrieved_count"],
                "checked_offering": {key: sample[key] for key in ("code", "start_date", "end_date", "enrolment_start", "enrolment_end", "cancellation_status")},
                "date_boundary_check": "passed", "personal_connection": status.structured_content["data"]["personal_connection"],
            }
    return {**report, "client_shutdown": "completed"}


async def demonstrate_import(profile: str, snapshot: str, study_right_id: str, import_store: Path | None = None) -> dict:
    """Inspect the chosen snapshot through MCP without printing individual grades."""
    Config(mode="imported", profile=profile, snapshot=snapshot, import_store=import_store)
    args = ["-m", "peppi_mcp", "--mode", "imported", "--profile", profile, "--snapshot", snapshot]
    if import_store is not None:
        args += ["--import-store", str(import_store)]
    async with Client(StdioServerParameters(command=sys.executable, args=args), read_timeout_seconds=45) as client:
        async def read(name, arguments):
            response = await client.call_tool(name, arguments)
            if response.is_error:
                raise RuntimeError(f"Import demonstration failed: {response.structured_content['error']['code']}")
            assert response.structured_content["source_mode"] == "imported"
            return response.structured_content["data"]
        tools = (await client.list_tools()).tools
        status = await read("get_connection_status", {})
        rights = await read("list_study_rights", {})
        assert study_right_id in {right["id"] for right in rights["items"]}
        summary = await read("get_credit_summary", {"study_right_id": study_right_id})
        records, cursor, page_count = [], None, 0
        while True:
            arguments = {"study_right_id": study_right_id, "status": "all", "limit": 10}
            if cursor:
                arguments["cursor"] = cursor
            page = await read("list_achievements", arguments)
            records.extend(page["items"])
            cursor = page["next_cursor"]
            page_count += 1
            assert page_count <= 100
            if cursor is None:
                break
        assert len(records) == page["matching_records"]
        assert all(record["provenance"]["source_id"] == snapshot and record["provenance"]["study_right_id"] == study_right_id for record in records)
        report = {"transport": "stdio subprocess", "server": client.server_info.name,
            "protocol_version": client.protocol_version, "mode": status["mode"], "tools": [tool.name for tool in tools],
            "snapshot_id": snapshot, "study_right_id": study_right_id, "source": status["sources"][0],
            "achievement_count": len(records), "achievement_pages": page_count,
            "credit_summary": {key: summary[key] for key in ("status", "known_subtotal", "total_credits", "source_reported_total", "difference_from_source_total", "warnings")}}
    return {**report, "client_shutdown": "completed"}


def main():
    parser = argparse.ArgumentParser(description="Verify the server through a real MCP stdio client")
    parser.add_argument("--public-catalogue", action="store_true", help="Also make bounded anonymous public study-guide requests")
    parser.add_argument("--mode", choices=["synthetic", "imported"], default="synthetic")
    parser.add_argument("--profile")
    parser.add_argument("--snapshot")
    parser.add_argument("--study-right")
    parser.add_argument("--import-store", type=Path)
    args = parser.parse_args()
    if args.mode == "imported":
        if not all((args.profile, args.snapshot, args.study_right)) or args.public_catalogue:
            parser.error("Imported demonstration requires --profile, --snapshot and --study-right; public smoke checks use the synthetic demonstration.")
        demonstration = demonstrate_import(args.profile, args.snapshot, args.study_right, args.import_store)
    else:
        if any(value is not None for value in (args.profile, args.snapshot, args.study_right, args.import_store)):
            parser.error("Import selection requires --mode imported")
        demonstration = demonstrate(args.public_catalogue)
    # This is the client console, not the server protocol stream.
    print(json.dumps(asyncio.run(demonstration), indent=2))


if __name__ == "__main__":
    main()

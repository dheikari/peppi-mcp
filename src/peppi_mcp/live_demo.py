"""Interactive real-stdio verification. Personal rows stay in process memory."""

import asyncio
import json
import sys
import argparse
import time
from decimal import Decimal
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters


def fields(row):
    return tuple(row.get(key) for key in ("course_id", "title", "credits", "grade", "completed_on"))


async def main(reference_pdf=None, browser="firefox"):
    reference = None
    if reference_pdf:
        from peppi_mcp.adapters.lapland_transcript import parse_pdf
        from peppi_mcp.import_store import MAX_DOCUMENT_BYTES, outside_repository
        with outside_repository(reference_pdf).open("rb") as stream:
            source = stream.read(MAX_DOCUMENT_BYTES + 1)
        reference = parse_pdf(source, study_right_id="selected-private-reference")
    params = StdioServerParameters(command=sys.executable, args=["-m", "peppi_mcp", "--mode", "live", "--browser", browser])
    async with Client(params, read_timeout_seconds=60) as client:
        saved_cursor = None
        saved_right = None
        saved_records = {}
        saved_plan = None

        async def call(name, args):
            started = time.monotonic()
            response = (await client.call_tool(name, args)).structured_content
            print(json.dumps({"operation":name,"elapsed_seconds":round(time.monotonic()-started, 2),"ok":response["ok"]}), flush=True)
            if not response["ok"]:
                raise RuntimeError(response["error"]["code"] + ": " + response["error"]["message"])
            return response

        tools = [tool.name for tool in (await client.list_tools()).tools]
        before = (await call("get_connection_status", {}))["data"]["personal_connection"]
        connection = (await call("connect_personal", {}))["data"]
        print(json.dumps({"transport": "real_stdio", "tools": tools, "startup_state": before,
                          "state": connection["personal_connection"]}), flush=True)
        while line := await asyncio.to_thread(sys.stdin.readline):
            try:
                action = json.loads(line)["action"]
                if action == "close":
                    await call("disconnect_personal", {})
                    break
                if action == "status":
                    output = (await call("get_connection_status", {}))["data"]
                elif action == "verify":
                    connected = (await call("connect_personal", {}))["data"]
                    if connected["personal_connection"] != "connected":
                        print(json.dumps({"state": connected["personal_connection"]}), flush=True)
                        continue
                    rights = (await call("list_study_rights", {}))["data"]["items"]
                    output = {"rights": len(rights), "checks": []}
                    for index, right in enumerate(rights):
                        args = {"study_right_id": right["id"], "limit": 7}
                        page = await call("list_achievements", args)
                        data = page["data"]
                        records, pages = list(data["items"]), 1
                        stamp = data["provenance"]["retrieved_at"]
                        if data["next_cursor"]:
                            saved_right, saved_cursor = right["id"], data["next_cursor"]
                        while data["next_cursor"]:
                            page = await call("list_achievements", {**args, "cursor": data["next_cursor"]})
                            data = page["data"]
                            assert page["source_mode"] == "cached" and data["provenance"]["retrieved_at"] == stamp
                            records.extend(data["items"])
                            pages += 1
                            assert pages <= 150
                        assert len(records) == data["matching_records"]
                        fresh = await call("list_achievements", {"study_right_id": right["id"], "limit": 100})
                        if len(records) <= 100:
                            assert sorted(map(fields, fresh["data"]["items"])) == sorted(map(fields, records))
                        assert fresh["data"]["provenance"]["retrieved_at"] > stamp
                        summary = (await call("get_credit_summary", {"study_right_id": right["id"]}))["data"]
                        assert summary["difference_from_source_total"] in ("0", "0.0", "0.00", 0)
                        saved_records[right["id"]] = records
                        output["checks"].append({"right_index": index, "records": len(records), "pages": pages,
                            "fresh_read_matches": True, "credit_reconciliation": True})
                        print(json.dumps({"verified_right": index, "records": len(records), "pages": pages}), flush=True)
                    if reference is not None:
                        reference_rows = [row.model_dump(mode="json") for row in reference.achievements]
                        output["private_reference_matching_rights"] = sum(
                            sorted(map(fields, rows)) == sorted(map(fields, reference_rows))
                            for rows in saved_records.values())
                        output["private_reference_fields"] = ["course_id", "title", "credits", "grade", "completed_on"]
                elif action == "verify_plans":
                    connected = (await call("connect_personal", {}))["data"]
                    if connected["personal_connection"] != "connected":
                        print(json.dumps({"state": connected["personal_connection"]}), flush=True)
                        continue
                    rights = (await call("list_study_rights", {}))["data"]["items"]
                    output = {"rights":len(rights), "plan_checks":[]}
                    for right_index, right in enumerate(rights):
                        choices = (await call("get_study_plan", {"study_right_id":right["id"]}))["data"]
                        assert choices["selection_required"]
                        for version in choices["available_plans"]:
                            selected = {"study_right_id":right["id"], "plan_id":version["id"]}
                            saved_plan = selected
                            plan = (await call("get_study_plan", selected))["data"]
                            nodes = plan["plan"]["nodes"]
                            ids = {n["id"] for n in nodes}
                            assert len(ids) == len(nodes) and all(n["parent_id"] is None or n["parent_id"] in ids for n in nodes)
                            progress = (await call("get_study_progress", selected))["data"]
                            assert next(iter(plan)) == "assessment" and next(iter(progress)) == "assessment"
                            for response in (plan, progress):
                                assessment = response["assessment"]
                                assert assessment["limitations"]
                                for discrepancy in assessment["discrepancies"]:
                                    assert discrepancy["node_id"] is None or discrepancy["node_id"] in ids
                                    if discrepancy["difference"] is not None:
                                        left, right_value = discrepancy["quantities"]
                                        assert Decimal(discrepancy["difference"]) == Decimal(left["value"]) - Decimal(right_value["value"])
                            assert plan["assessment"]["comparison_status"] == "not_requested"
                            assert progress["assessment"]["source_consistency"] == ("conflicting" if progress["progress"]["source_reconciliation_issues"] else "consistent")
                            assert progress["assessment"]["comparison_status"] == ("reconciled" if progress["progress"]["status"] == "source_credits_reconciled" else "unresolved")
                            assert all("credits" in row and "outside_plan" not in row for row in progress["progress"]["unmapped_achievements"])
                            assert progress["progress"]["graduation_eligibility"] is None
                            assert len(progress["progress"]["requirements"]) == sum(n["kind"] == "course" for n in nodes)
                            reported = progress["progress"]["source_reported"]
                            if not progress["progress"]["source_reconciliation_issues"]:
                                assert Decimal(reported["completed_in_plan"]) + Decimal(reported["completed_outside_plan"]) == Decimal(reported["total_credits"])
                            assert progress["provenance"]["snapshot_id"] == plan["provenance"]["snapshot_id"]
                            assert progress["provenance"]["retrieved_at"] > plan["provenance"]["retrieved_at"]
                            check = {"right_index":right_index,"version":version["version"],"node_count":len(nodes),
                                "course_count":len(progress["progress"]["requirements"]),"fresh_reads_match":True,
                                "progress_status":progress["progress"]["status"],"unresolved_items":len(progress["progress"]["issues"]),
                                "source_reconciliation_issues":progress["progress"]["source_reconciliation_issues"],
                                "assessment_verified":True,
                                "unmapped_achievements":len(progress["progress"]["unmapped_achievements"])}
                            output["plan_checks"].append(check)
                            print(json.dumps({"verified_plan":check}), flush=True)
                elif action == "verify_plan_logout":
                    assert saved_plan
                    response = (await client.call_tool("get_study_progress", saved_plan)).structured_content
                    assert not response["ok"] and response["error"]["code"] == "SESSION_EXPIRED"
                    output = {"plan_authentication_loss_code":response["error"]["code"]}
                elif action == "pin":
                    rights = (await call("list_study_rights", {}))["data"]["items"]
                    for right in rights:
                        data = (await call("list_achievements", {"study_right_id":right["id"], "limit":7}))["data"]
                        if data["next_cursor"]:
                            saved_right, saved_cursor = right["id"], data["next_cursor"]
                            break
                    assert saved_cursor
                    output = {"fresh_cursor_retained": True}
                elif action == "verify_logout":
                    args = {"study_right_id": saved_right, "limit": 7}
                    if saved_cursor:
                        args["cursor"] = saved_cursor
                    response = (await client.call_tool("list_achievements", args)).structured_content
                    assert not response["ok"]
                    output = {"authentication_loss_code": response["error"]["code"]}
                else:
                    raise ValueError
                print(json.dumps({"ok": True, "data": output}), flush=True)
            except Exception as exc:
                print(json.dumps({"ok": False, "error": str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__}), flush=True)
    print(json.dumps({"client_shutdown": "completed"}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", choices=("firefox", "chrome"), default="firefox")
    parser.add_argument("--reference-pdf", type=Path, help="Optional deliberately selected PDF outside the repository; compare fields in memory only")
    args = parser.parse_args()
    asyncio.run(main(args.reference_pdf, args.browser))

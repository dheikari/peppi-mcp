"""Failure evidence remains useful without filenames or private text."""
import json
import time

from peppi_mcp.runtime_storage import filesystem_path
from tests.cleanup_diagnostics import cleanup_evidence, removal_record


def test_extended_windows_path_records_depth_and_never_its_filename(tmp_path):
    root = tmp_path / "PRIVATE_SECRET"
    filename = filesystem_path(root / "nested" / "PRIVATE_SECRET")
    error = PermissionError("PRIVATE_SECRET")
    error.filename, error.winerror = str(filename), 32
    detail = removal_record(error, root, 6, time.monotonic())
    assert detail["owned_directory_depth"] == 2 and detail["winerror"] == 32
    assert detail["attempt"] == 6 and not detail["success"]
    assert "PRIVATE_SECRET" not in json.dumps(detail)


def test_recovery_evidence_separates_attempts_and_records_success(tmp_path):
    started = time.monotonic()
    attempts = [removal_record(PermissionError("PRIVATE_SECRET"), tmp_path, 1, started),
                removal_record(None, tmp_path, 2, started)]
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps({**attempts[-1], "attempts":attempts}))
    assert cleanup_evidence(path) == attempts
    assert cleanup_evidence(path, after=1) == [attempts[-1]]
    assert attempts[-1]["success"] and attempts[-1]["error_type"] is None
    assert "PRIVATE_SECRET" not in json.dumps(cleanup_evidence(path))


def test_unclassified_error_and_noninteger_code_expose_no_private_marker(tmp_path):
    class PRIVATE_SECRET(Exception):
        pass
    error = PRIVATE_SECRET("PRIVATE_SECRET")
    error.filename, error.winerror = str(tmp_path.parent / "PRIVATE_SECRET"), "PRIVATE_SECRET"
    detail = removal_record(error, tmp_path, 1, time.monotonic())
    assert detail["error_type"] == "unclassified"
    assert detail["winerror"] is None and detail["owned_directory_depth"] is None
    assert "PRIVATE_SECRET" not in json.dumps(detail)

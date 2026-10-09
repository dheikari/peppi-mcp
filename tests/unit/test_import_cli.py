import json
import socket
import subprocess
import sys
from decimal import Decimal

import pytest

from peppi_mcp.adapters.imported_records import ImportedSource
from peppi_mcp.config import Config
from peppi_mcp.errors import PeppiError
from peppi_mcp.import_cli import import_file
from peppi_mcp.import_store import ImportStore
from peppi_mcp.server import Application
from tests.transcript_fixtures import pages, pdf_bytes


def test_cli_import_reimport_newer_snapshot_and_profile_isolation(tmp_path):
    source = tmp_path / "fictional.pdf"
    store = tmp_path / "data" / "imports.sqlite3"
    original = pdf_bytes()
    source.write_bytes(original)
    command = [sys.executable, "-m", "peppi_mcp.import_cli", str(source), "--profile", "fictional", "--study-right", "test-right", "--store", str(store)]
    def run():
        process = subprocess.run(command, capture_output=True, text=True, timeout=40)
        assert process.returncode == 0 and process.stderr == "", process.stderr
        return json.loads(process.stdout)
    first, again = run(), run()
    assert first["created"] and not again["created"]
    assert first["snapshot_id"] == again["snapshot_id"] and first["imported_at"] == again["imported_at"]
    assert first["credit_summary"]["total_credits"] == "3.5"
    assert source.read_bytes() == original
    newer = [page.replace("1.3.2026", "2.3.2026") for page in pages()]
    source.write_bytes(pdf_bytes(newer))
    current = run()
    assert current["created"] and current["snapshot_id"] != first["snapshot_id"]
    assert current["credit_summary"]["total_credits"] == "3.5"
    selected = ImportStore(store).load("fictional", first["snapshot_id"])
    assert len(selected.snapshot.achievements) == 3
    assert selected.snapshot.study_rights[0].provenance.source_issued_on.isoformat() == "2026-03-01"
    with pytest.raises(PeppiError) as error:
        ImportedSource("different-profile", first["snapshot_id"], store)
    assert error.value.code == "IMPORT_NOT_FOUND"
    # Only one SQLite store is created; neither source bytes nor extracted text are cached.
    assert [path.name for path in store.parent.iterdir()] == ["imports.sqlite3"]


def test_imported_tools_are_offline_and_do_not_read_arbitrary_files(tmp_path, monkeypatch):
    source = tmp_path / "fictional.pdf"
    source.write_bytes(pdf_bytes())
    store = tmp_path / "imports.sqlite3"
    report = import_file(source, profile="fictional", study_right_id="test-right", store_path=store)
    def forbidden(*args, **kwargs):
        pytest.fail("Imported operations must not connect to the network")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    source.unlink()  # Stored reads must not depend on the PDF remaining at its original path.
    app = Application(ImportedSource("fictional", report["snapshot_id"], store))
    for name in app.tools:
        args = {"study_right_id": "test-right"} if name in {"list_achievements", "get_credit_summary"} else {}
        response = app.call(name, args)
        assert not response.is_error and response.structured_content["source_mode"] == "imported"
    status = app.call("get_connection_status", {}).structured_content["data"]
    assert status["sources"][0]["source_sha256"] == report["source_sha256"]
    assert status["sources"][0]["source_issued_on"] == "2026-03-01"
    assert status["personal_connection"] == "not_enabled" and not status["sign_in_needed"]
    assert app.call("read_file", {"path": str(source)}).is_error
    assert app.call("list_achievements", {"study_right_id": "test-right", "file": str(source)}).is_error
    assert app.call("list_achievements", {"study_right_id": "test-right", "status": "unknown"}).structured_content["data"]["items"] == []


@pytest.mark.parametrize("config", [dict(mode="imported"), dict(mode="imported", profile="x"),
    dict(mode="imported", profile="../x", snapshot="import:test"), dict(mode="imported", profile="x", snapshot="latest"),
    dict(mode="synthetic", profile="x"), dict(mode="synthetic", snapshot="import:test")])
def test_invalid_import_selection_fails_without_fallback(config):
    with pytest.raises(ValueError, match="CONFIGURATION_ERROR"):
        Config(**config)


def test_invalid_source_cannot_create_or_change_store(tmp_path):
    source = tmp_path / "private.pdf"
    source.write_bytes(b"PRIVATE INVALID CONTENT")
    store = tmp_path / "imports.sqlite3"
    process = subprocess.run([sys.executable, "-m", "peppi_mcp.import_cli", str(source), "--profile", "test", "--study-right", "test", "--store", str(store)], capture_output=True, text=True, timeout=40)
    assert process.returncode != 0 and process.stderr == ""
    assert json.loads(process.stdout)["error"]["code"] == "IMPORT_UNSUPPORTED_FORMAT"
    assert "PRIVATE INVALID" not in process.stdout and str(source) not in process.stdout
    assert not store.exists() and source.read_bytes() == b"PRIVATE INVALID CONTENT"


def test_repo_source_is_rejected_and_same_source_store_is_rejected(tmp_path):
    repo = tmp_path / "repository"
    repo.mkdir()
    (repo / ".git").mkdir()
    source = repo / "fictional.pdf"
    source.write_bytes(pdf_bytes())
    with pytest.raises(PeppiError) as error:
        import_file(source, profile="test", study_right_id="test", store_path=tmp_path / "imports.sqlite3")
    assert error.value.code == "IMPORT_LOCATION_UNSAFE"
    outside = tmp_path / "fictional.pdf"
    outside.write_bytes(source.read_bytes())
    with pytest.raises(PeppiError) as error:
        import_file(outside, profile="test", study_right_id="test", store_path=outside)
    assert error.value.code == "IMPORT_LOCATION_UNSAFE"
    assert outside.read_bytes() == source.read_bytes()

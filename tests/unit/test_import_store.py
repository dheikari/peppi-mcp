"""Invented input verifies storage only, not a university transcript parser."""

import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from peppi_mcp.adapters.synthetic import SyntheticSource
from peppi_mcp.errors import PeppiError
from peppi_mcp.import_store import MAX_DOCUMENT_BYTES, MAX_SNAPSHOT_BYTES, ImportStore
from peppi_mcp.models import Snapshot
from peppi_mcp.services.achievements import credit_summary


@pytest.fixture
def imported_records():
    raw = SyntheticSource().snapshot().model_dump(mode="json")
    for row in (*raw["study_rights"], *raw["achievements"]):
        row["provenance"]["source_mode"] = "imported"
        row["provenance"]["warnings"] = ["Fictional import storage test; no university format verified."]
    return Snapshot.model_validate(raw)


def save(store, records, source=b"Fictional source bytes", **kwargs):
    return store.save(records, source, profile_id=kwargs.get("profile_id", "test-profile"),
                      source_format="fictional-storage-fixture", parser_version=kwargs.get("parser_version", "1"))


def test_reimport_preserves_first_timestamp_snapshot_and_credit_total(tmp_path, imported_records):
    clock = [datetime(2026, 10, 3, tzinfo=timezone.utc)]
    store = ImportStore(tmp_path / "private" / "imports.sqlite3", now=lambda: clock[0])
    first, created = save(store, imported_records)
    assert created
    clock[0] += timedelta(days=1)
    again, created = save(store, imported_records)
    assert not created and again == first
    assert first.source_sha256 == hashlib.sha256(b"Fictional source bytes").hexdigest()
    assert first.imported_at == datetime(2026, 10, 3, tzinfo=timezone.utc)
    loaded = ImportStore(store.path).load("test-profile", first.snapshot.id)
    assert loaded == first
    assert credit_summary(loaded.snapshot, "demo-main").total_credits == 15.5
    assert all(row.provenance.source_id == first.snapshot.id for row in loaded.snapshot.achievements)


def test_real_clock_is_sampled_once_per_save(tmp_path, imported_records):
    calls = []
    def now():
        calls.append(1)
        return datetime.now(timezone.utc)
    result, created = save(ImportStore(tmp_path / "imports.sqlite3", now=now), imported_records)
    assert created and len(calls) == 1
    assert result.imported_at == result.snapshot.study_rights[0].provenance.retrieved_at


def test_new_document_and_parser_version_are_explicit_separate_snapshots(tmp_path, imported_records):
    store = ImportStore(tmp_path / "imports.sqlite3")
    old, _ = save(store, imported_records)
    newer, _ = save(store, imported_records, source=b"Fictional newer document")
    remapped, _ = save(store, imported_records, parser_version="2")
    assert len({item.snapshot.id for item in (old, newer, remapped)}) == 3
    for document in (old, newer, remapped):
        loaded = store.load("test-profile", document.snapshot.id)
        assert loaded == document
        assert len(loaded.snapshot.achievements) == len(imported_records.achievements)
    with pytest.raises(PeppiError) as error:
        store.load("test-profile", "latest")
    assert error.value.code == "IMPORT_NOT_FOUND"


def test_profiles_and_study_rights_are_not_silently_combined(tmp_path, imported_records):
    store = ImportStore(tmp_path / "imports.sqlite3")
    first, _ = save(store, imported_records, profile_id="first")
    second, _ = save(store, imported_records, profile_id="second")
    assert first.snapshot.id != second.snapshot.id
    with pytest.raises(PeppiError) as error:
        store.load("second", first.snapshot.id)
    assert error.value.code == "IMPORT_NOT_FOUND"
    assert credit_summary(first.snapshot, "demo-main").total_credits == 15.5
    assert credit_summary(first.snapshot, "demo-other").total_credits == 5
    assert credit_summary(first.snapshot, "demo-ambiguous").total_credits is None


def test_changed_mapping_cannot_overwrite_same_document(tmp_path, imported_records):
    store = ImportStore(tmp_path / "imports.sqlite3")
    first, _ = save(store, imported_records)
    raw = imported_records.model_dump(mode="json")
    raw["achievements"][0]["title"] = "Changed fictional mapping"
    with pytest.raises(PeppiError) as error:
        save(store, Snapshot.model_validate(raw))
    assert error.value.code == "IMPORT_CONFLICT"
    assert store.load("test-profile", first.snapshot.id) == first


def test_concurrent_reimport_commits_exactly_one_snapshot(tmp_path, imported_records):
    path = tmp_path / "imports.sqlite3"
    def import_once(_):
        return save(ImportStore(path), imported_records)
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(import_once, range(4)))
    assert sum(created for _, created in results) == 1
    assert all(document == results[0][0] for document, _ in results)


@pytest.mark.parametrize("source", [b"", b"x" * (MAX_DOCUMENT_BYTES + 1), "not bytes"], ids=["empty", "oversized", "wrong-type"])
def test_bad_source_size_does_not_create_store(tmp_path, imported_records, source):
    store = ImportStore(tmp_path / "imports.sqlite3")
    with pytest.raises(PeppiError) as error:
        save(store, imported_records, source=source)
    assert error.value.code == "IMPORT_SIZE_INVALID" and not store.path.exists()


def test_synthetic_records_and_invalid_profiles_are_rejected_before_storage(tmp_path, imported_records):
    store = ImportStore(tmp_path / "imports.sqlite3")
    with pytest.raises(PeppiError) as error:
        save(store, SyntheticSource().snapshot())
    assert error.value.code == "IMPORT_INVALID"
    with pytest.raises(PeppiError) as error:
        save(store, imported_records, profile_id="../unsafe")
    assert error.value.code == "IMPORT_INVALID" and not store.path.exists()


def test_repository_locations_are_refused(tmp_path):
    project = tmp_path / "repository"
    project.mkdir()
    (project / ".git").mkdir()
    with pytest.raises(PeppiError) as error:
        ImportStore(project / "private" / "imports.sqlite3")
    assert error.value.code == "IMPORT_LOCATION_UNSAFE"
    assert not (project / "private").exists()


def test_missing_store_is_not_created_by_read(tmp_path):
    store = ImportStore(tmp_path / "private" / "imports.sqlite3")
    with pytest.raises(PeppiError) as error:
        store.load("test-profile", "import:missing")
    assert error.value.code == "IMPORT_NOT_FOUND" and not store.path.parent.exists()


@pytest.mark.parametrize("payload", ['{"unexpected":"secret"}', "x" * (MAX_SNAPSHOT_BYTES + 1)], ids=["invalid-schema", "oversized"])
def test_corrupt_stored_payload_has_safe_error(tmp_path, imported_records, payload):
    store = ImportStore(tmp_path / "imports.sqlite3")
    first, _ = save(store, imported_records)
    with sqlite3.connect(store.path) as connection:
        connection.execute("UPDATE imports SET payload=?", (payload,))
    with pytest.raises(PeppiError) as error:
        store.load("test-profile", first.snapshot.id)
    assert error.value.code == "IMPORT_STORE_INVALID" and "secret" not in error.value.message


def test_non_database_file_is_neither_overwritten_nor_exposed(tmp_path, imported_records):
    path = tmp_path / "imports.sqlite3"
    path.write_bytes(b"private-looking existing file content")
    store = ImportStore(path)
    with pytest.raises(PeppiError) as error:
        save(store, imported_records)
    assert error.value.code == "IMPORT_STORE_ERROR" and "private-looking" not in error.value.message
    assert path.read_bytes() == b"private-looking existing file content"

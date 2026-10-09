"""Explicit local PDF import. No file-reading or import tool is exposed over MCP."""

import argparse
import json
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from peppi_mcp.adapters.lapland_transcript import FORMAT, PARSER_VERSION, parse_pdf
from peppi_mcp.errors import PeppiError
from peppi_mcp.import_store import MAX_DOCUMENT_BYTES, ImportStore, ProfileId, outside_repository
from peppi_mcp.models import ScopedArguments
from peppi_mcp.services.achievements import credit_summary


def import_file(path: Path, *, profile: str, study_right_id: str, store_path: Path | None = None):
    try:
        TypeAdapter(ProfileId).validate_python(profile)
        ScopedArguments(study_right_id=study_right_id)
    except ValidationError:
        raise PeppiError("IMPORT_INVALID", "Select a valid local profile and study-right alias.") from None
    store = ImportStore(store_path)
    try:
        source_path = outside_repository(path)
        if source_path == store.path:
            raise PeppiError("IMPORT_LOCATION_UNSAFE", "The source PDF and import store must be different files.")
        if not source_path.is_file():
            raise PeppiError("IMPORT_FILE_UNAVAILABLE", "The selected source is not a readable regular file.")
        with source_path.open("rb") as stream:
            source = stream.read(MAX_DOCUMENT_BYTES + 1)
    except OSError:
        raise PeppiError("IMPORT_FILE_UNAVAILABLE", "The selected source file could not be read.") from None
    snapshot = parse_pdf(source, study_right_id=study_right_id)
    document, created = store.save(snapshot, source, profile_id=profile, source_format=FORMAT, parser_version=PARSER_VERSION)
    summary = credit_summary(document.snapshot, study_right_id)
    return {
        "ok": True, "created": created, "source_mode": "imported", "profile": profile,
        "snapshot_id": document.snapshot.id, "study_right_id": study_right_id,
        "source_sha256": document.source_sha256, "source_size": document.source_size,
        "source_format": document.source_format, "parser_version": document.parser_version,
        "source_issued_on": document.snapshot.study_rights[0].provenance.source_issued_on.isoformat(),
        "imported_at": document.imported_at.isoformat(), "achievement_count": len(document.snapshot.achievements),
        "source_group_count": len(document.snapshot.source_groups),
        "credit_summary": summary.model_dump(mode="json", exclude={"decisions", "provenance", "source_groups"}),
    }


def main():
    parser = argparse.ArgumentParser(description="Import a supported Finnish Lapland transcript PDF into a private local snapshot")
    parser.add_argument("file", type=Path, help="Deliberately selected PDF outside a source repository")
    parser.add_argument("--profile", required=True, help="Local profile alias (lowercase letters, digits, hyphens or underscores)")
    parser.add_argument("--study-right", required=True, help="Local study-right alias; not an authenticated university identifier")
    parser.add_argument("--store", type=Path, help="Optional private store; defaults to the user data directory")
    args = parser.parse_args()
    try:
        report = import_file(args.file, profile=args.profile, study_right_id=args.study_right, store_path=args.store)
    except PeppiError as exc:
        print(json.dumps({"ok": False, "error": {"code": exc.code, "message": exc.message}}))
        raise SystemExit(1) from None
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()

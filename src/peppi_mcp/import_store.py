"""Private immutable import snapshots; parsing is a separate verified boundary.

This module accepts validated records from a parser, not arbitrary transcript JSON
from MCP clients. It never stores or modifies the original document. A caller must
explicitly choose a profile and snapshot; no newest-file selection or merging occurs.
"""

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, ValidationError, model_validator

from peppi_mcp.errors import PeppiError
from peppi_mcp.models import Identifier, Record, Snapshot

MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
MAX_SNAPSHOT_BYTES = 8 * 1024 * 1024
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
ProfileId = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$")]


class ImportDocument(Record):
    schema_version: Literal[1] = 1
    profile_id: ProfileId
    source_sha256: Digest
    source_size: int = Field(gt=0, le=MAX_DOCUMENT_BYTES, strict=True)
    source_format: Identifier
    parser_version: Identifier
    imported_at: AwareDatetime
    snapshot: Snapshot

    @model_validator(mode="after")
    def import_provenance_is_consistent(self):
        records = (*self.snapshot.study_rights, *self.snapshot.achievements, *self.snapshot.source_groups)
        if not self.snapshot.study_rights:
            raise ValueError("An import must identify at least one study right")
        if len({row.provenance.institution_id for row in records}) != 1:
            raise ValueError("An import must belong to exactly one institution")
        if any(row.provenance.source_mode != "imported" or row.provenance.source_id != self.snapshot.id
               or row.provenance.retrieved_at != self.imported_at
               or row.provenance.source_sha256 not in (None, self.source_sha256) for row in records):
            raise ValueError("Import provenance does not match its immutable snapshot")
        expected = snapshot_identifier(self.profile_id, self.source_sha256, self.source_format,
                                       self.parser_version, self.snapshot)
        if self.snapshot.id != expected:
            raise ValueError("Import snapshot identity does not match its source and context")
        return self


def snapshot_identifier(profile_id, checksum, source_format, parser_version, snapshot):
    contexts = sorted((right.provenance.institution_id, right.id) for right in snapshot.study_rights)
    body = json.dumps([profile_id, checksum, source_format, parser_version, contexts], separators=(",", ":"))
    return "import:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def default_store_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "peppi-mcp" / "imports.sqlite3"


def outside_repository(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if any((parent / ".git").exists() for parent in (resolved.parent, *resolved.parent.parents)):
        raise PeppiError("IMPORT_LOCATION_UNSAFE", "Import data must be stored outside source repositories.")
    # Installed/editable package location may be a source copy without Git metadata.
    package = Path(__file__).resolve().parent
    project = package.parent.parent if package.parent.name == "src" else package
    if resolved.is_relative_to(project):
        raise PeppiError("IMPORT_LOCATION_UNSAFE", "Import data must be stored outside the application directory.")
    return resolved


def _stamp(snapshot, identity, imported_at):
    raw = snapshot.model_dump(mode="json")
    raw["id"] = identity
    for row in (*raw["study_rights"], *raw["achievements"], *raw["source_groups"]):
        if row["provenance"]["source_mode"] != "imported":
            raise PeppiError("IMPORT_INVALID", "Only explicitly imported records can enter the import store.")
        row["provenance"].update(source_id=identity, retrieved_at=imported_at.isoformat())
    return Snapshot.model_validate(raw)


class ImportStore:
    """SQLite gives atomic duplicate handling without custom lock files.

    Storage is local plaintext in the selected private directory. No encryption,
    credential storage, automatic import, retention timer or background work exists.
    """

    def __init__(self, path: Path | None = None, *, now=None):
        self.path = outside_repository(path or default_store_path())
        self.now = now or (lambda: datetime.now(timezone.utc))

    def _connect(self, *, write):
        # Recheck resolved destination before each open, including symlink changes.
        path = outside_repository(self.path)
        if write:
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if not path.exists():
                try:
                    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                except FileExistsError:
                    pass
                else:
                    os.close(fd)
        elif not path.is_file():
            raise PeppiError("IMPORT_NOT_FOUND", "The selected private import store does not exist.")
        connection = sqlite3.connect(path.as_uri() + ("?mode=rw" if write else "?mode=ro"), uri=True, timeout=5)
        connection.execute("PRAGMA trusted_schema=OFF")
        if not write:
            connection.execute("PRAGMA query_only=ON")
        return connection

    def save(self, snapshot: Snapshot, source_bytes: bytes, *, profile_id: str,
             source_format: str, parser_version: str) -> tuple[ImportDocument, bool]:
        """Return (document, created). Same bytes/mapping return the original time.

        A changed mapping under the same parser version is a conflict, never an
        overwrite. Parser changes require a new version and explicit selection.
        """
        if not isinstance(source_bytes, bytes) or not 0 < len(source_bytes) <= MAX_DOCUMENT_BYTES:
            raise PeppiError("IMPORT_SIZE_INVALID", "Source document must contain between 1 byte and 20 MiB.")
        checksum = hashlib.sha256(source_bytes).hexdigest()
        try:
            identity = snapshot_identifier(profile_id, checksum, source_format, parser_version, snapshot)
            imported_at = self.now()
            document = ImportDocument(profile_id=profile_id, source_sha256=checksum, source_size=len(source_bytes),
                                      source_format=source_format, parser_version=parser_version, imported_at=imported_at,
                                      snapshot=_stamp(snapshot, identity, imported_at))
        except (ValidationError, ValueError, TypeError):
            raise PeppiError("IMPORT_INVALID", "Parsed records or import metadata failed validation.") from None
        payload = document.model_dump_json()
        if len(payload.encode("utf-8")) > MAX_SNAPSHOT_BYTES:
            raise PeppiError("IMPORT_SIZE_INVALID", "Normalized import exceeded the 8 MiB snapshot limit.")
        connection = None
        try:
            connection = self._connect(write=True)
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute("CREATE TABLE IF NOT EXISTS imports (profile_id TEXT NOT NULL, snapshot_id TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(profile_id, snapshot_id))")
                existing = connection.execute("SELECT CASE WHEN length(CAST(payload AS BLOB))<=? THEN payload ELSE NULL END FROM imports WHERE profile_id=? AND snapshot_id=?",
                                              (MAX_SNAPSHOT_BYTES, profile_id, identity)).fetchone()
                if existing:
                    if existing[0] is None:
                        raise PeppiError("IMPORT_STORE_INVALID", "Stored snapshot exceeds the supported size limit.")
                    prior = self._validate(existing[0], profile_id, identity)
                    restamped = _stamp(document.snapshot, identity, prior.imported_at)
                    candidate = document.model_copy(update={"imported_at": prior.imported_at, "snapshot": restamped})
                    if candidate != prior:
                        raise PeppiError("IMPORT_CONFLICT", "The same document and parser version produced different records. Existing data was not changed.")
                    return prior, False
                connection.execute("INSERT INTO imports (profile_id, snapshot_id, payload) VALUES (?, ?, ?)",
                                   (profile_id, identity, payload))
            return document, True
        except (sqlite3.Error, OSError):
            raise PeppiError("IMPORT_STORE_ERROR", "The private import store could not be written. No source document was changed.") from None
        finally:
            if connection:
                connection.close()

    @staticmethod
    def _validate(payload, profile_id, identity):
        try:
            document = ImportDocument.model_validate_json(payload)
            if document.profile_id != profile_id or document.snapshot.id != identity:
                raise ValueError("Context mismatch")
            return document
        except (ValidationError, ValueError, TypeError):
            raise PeppiError("IMPORT_STORE_INVALID", "Stored import metadata or records failed validation.") from None

    def load(self, profile_id: str, snapshot_id: str) -> ImportDocument:
        connection = None
        try:
            connection = self._connect(write=False)
            row = connection.execute("SELECT CASE WHEN length(CAST(payload AS BLOB))<=? THEN payload ELSE NULL END FROM imports WHERE profile_id=? AND snapshot_id=?",
                                     (MAX_SNAPSHOT_BYTES, profile_id, snapshot_id)).fetchone()
            if not row:
                raise PeppiError("IMPORT_NOT_FOUND", "No snapshot matches the selected profile and identifier.")
            if row[0] is None:
                raise PeppiError("IMPORT_STORE_INVALID", "Stored snapshot exceeds the supported size limit.")
            return self._validate(row[0], profile_id, snapshot_id)
        except (sqlite3.Error, OSError):
            raise PeppiError("IMPORT_STORE_ERROR", "The private import store could not be read.") from None
        finally:
            if connection:
                connection.close()

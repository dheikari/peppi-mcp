"""Read one explicitly selected immutable local snapshot; never auto-import."""

from pathlib import Path

from peppi_mcp.import_store import ImportStore
from peppi_mcp.models import Snapshot


class ImportedSource:
    def __init__(self, profile: str, snapshot_id: str, store_path: Path | None = None):
        self.document = ImportStore(store_path).load(profile, snapshot_id)

    def snapshot(self) -> Snapshot:
        return self.document.snapshot

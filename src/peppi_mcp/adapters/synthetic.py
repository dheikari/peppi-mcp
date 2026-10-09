"""Only read the bundled fixture. No user-supplied paths or network access."""

import hashlib
from importlib.resources import files
from typing import Protocol

from peppi_mcp.models import Snapshot


class StudySource(Protocol):
    def snapshot(self) -> Snapshot: ...


class SyntheticSource:
    def __init__(self):
        raw = files("peppi_mcp").joinpath("data/synthetic.json").read_bytes()
        self._snapshot = Snapshot.model_validate_json(raw)
        records = (*self._snapshot.study_rights, *self._snapshot.achievements)
        if any(r.provenance.source_mode != "synthetic" for r in records):
            raise ValueError("The demonstration must contain synthetic records only")
        self.fingerprint = hashlib.sha256(raw).hexdigest()

    def snapshot(self) -> Snapshot:
        return self._snapshot

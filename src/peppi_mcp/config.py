"""Explicit startup configuration; no credential discovery or source fallback."""

import argparse
import os
from dataclasses import dataclass
from pathlib import Path

from pydantic import TypeAdapter, ValidationError
from peppi_mcp.import_store import ProfileId
from peppi_mcp.models import Identifier


@dataclass(frozen=True)
class Config:
    mode: str = "synthetic"
    public_catalogue: bool = False
    profile: str | None = None
    snapshot: str | None = None
    import_store: Path | None = None
    browser: str | None = None

    def __post_init__(self):
        if self.mode not in {"synthetic", "imported", "live"}:
            raise ValueError("CONFIGURATION_ERROR: supported modes are synthetic, imported and live")
        if self.browser not in {None, "firefox", "chrome"}:
            raise ValueError("CONFIGURATION_ERROR: supported browsers are firefox and chrome")
        if self.mode != "live" and self.browser is not None:
            raise ValueError("CONFIGURATION_ERROR: browser selection requires --mode live")
        if self.mode != "imported" and any(value is not None for value in (self.profile, self.snapshot, self.import_store)):
            raise ValueError("CONFIGURATION_ERROR: import selection requires --mode imported")
        if self.mode == "imported":
            try:
                TypeAdapter(ProfileId).validate_python(self.profile)
                TypeAdapter(Identifier).validate_python(self.snapshot)
                if not self.snapshot.startswith("import:"):
                    raise ValueError
            except (ValidationError, ValueError):
                raise ValueError("CONFIGURATION_ERROR: imported mode requires a valid --profile and explicit --snapshot import:... identifier") from None


def parse_config() -> Config:
    parser = argparse.ArgumentParser(description="Unofficial read-only Peppi MCP")
    parser.add_argument("--mode", default=os.environ.get("PEPPI_MCP_MODE", "synthetic"))
    parser.add_argument("--browser", choices=("firefox", "chrome"), help="Live browser; Firefox is the default. Chrome uses a separate disposable profile.")
    parser.add_argument("--public-catalogue", action="store_true", help="Enable experimental anonymous reads from the Lapland public study guide")
    parser.add_argument("--profile", help="Local profile selected during import")
    parser.add_argument("--snapshot", help="Exact import:... snapshot identifier returned by the import command")
    parser.add_argument("--import-store", type=Path, help="Optional private SQLite store outside the repository")
    args = parser.parse_args()
    try:
        return Config(mode=args.mode, public_catalogue=args.public_catalogue, profile=args.profile,
                      snapshot=args.snapshot, import_store=args.import_store, browser=args.browser)
    except ValueError as exc:
        parser.error(str(exc))

"""Category-only fictional cleanup evidence, never packaged with the worker."""
import json
import time
from pathlib import Path

from peppi_mcp.runtime_storage import filesystem_path


def removal_record(error, path, attempt, started):
    depth = None
    filename = getattr(error, "filename", None)
    if filename:
        try:
            depth = len(filesystem_path(filename).relative_to(filesystem_path(path)).parts)
        except ValueError:
            pass
    category = type(error).__name__ if error else None
    if category not in {None, "PermissionError", "FileNotFoundError", "OSError", "ValueError"}:
        category = "unclassified"
    code = getattr(error, "winerror", None)
    return {"stage": "profile removal", "attempt": attempt,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "success": error is None, "error_type": category,
            "winerror": code if type(code) is int else None, "owned_directory_depth": depth}


def cleanup_evidence(path, *, after=0):
    if not path.exists():
        return []
    return json.loads(path.read_text()).get("attempts", [])[after:]

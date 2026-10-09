"""Owned disposable profile roots. No discovery or reuse of normal Firefox data."""

import json
import os
import re
import shutil
import stat
import uuid
import asyncio
import threading
from pathlib import Path


def runtime_root():
    return Path(os.environ["LOCALAPPDATA"]) / "peppi-mcp" / "runtime"


def filesystem_path(path):
    """Use Windows extended-length APIs without changing the ownership scope."""
    path = Path(path).absolute()
    value = str(path)
    if os.name == "nt" and not value.startswith("\\\\?\\"):
        value = "\\\\?\\UNC\\" + value[2:] if value.startswith("\\\\") else "\\\\?\\" + value
    return Path(value)


def safe_path(path):
    path = Path(path).absolute()
    native = filesystem_path(path)
    for part in (native, *native.parents):
        if part.exists() or part.is_symlink():
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise ValueError("Unsafe runtime path")
    return path


def process_identity(pid):
    """None proves absence; access errors do not prove a process is dead."""
    import win32api
    import win32process
    try:
        handle = win32api.OpenProcess(0x1000, False, pid)
    except Exception as exc:
        if getattr(exc, "winerror", None) == 87:
            return None
        raise
    try:
        if win32process.GetExitCodeProcess(handle) != 259:
            return None
        return win32process.GetProcessTimes(handle)["CreationTime"].isoformat()
    finally:
        handle.Close()


def remove_owned(root, path, owner):
    root, path = filesystem_path(safe_path(root)), filesystem_path(safe_path(path))
    if path.parent != root or not re.fullmatch(r"run-[a-f0-9]{32}", path.name):
        raise ValueError("Unowned runtime directory")
    if not path.exists():
        return
    marker = safe_path(path / "owner.json")
    if marker.stat().st_size > 1024 or json.loads(marker.read_text(encoding="utf-8")) != owner:
        raise ValueError("Invalid runtime ownership")
    for folder, dirs, files in os.walk(path, followlinks=False):
        for name in (*dirs, *files):
            safe_path(Path(folder) / name)
    # Python's Windows rmtree does not descend directory junctions. The explicit
    # preflight additionally refuses them rather than removing the link itself.
    # A locked file must not destroy the proof needed for the next attempt.
    # Keep the root marker until every other entry has been removed.
    for entry in path.iterdir():
        if entry == marker:
            continue
        safe_path(entry)
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()
    marker.unlink()
    try:
        path.rmdir()
    except OSError:
        if path.exists():
            safe_path(path)
            marker.write_text(json.dumps(owner), encoding="utf-8")
        raise
    if path.exists():
        raise OSError("Owned runtime removal is incomplete")


def recover_abandoned(root=None):
    """Return cleanup_pending; retain anything whose ownership cannot be proven."""
    if os.name != "nt":
        return False
    try:
        root = safe_path(root or runtime_root())
        if not root.exists():
            return False
        pending = False
        for path in root.iterdir():
            try:
                safe_path(path)
                if not re.fullmatch(r"run-[a-f0-9]{32}", path.name):
                    pending = True
                    continue
                marker = safe_path(path / "owner.json")
                if marker.stat().st_size > 1024:
                    raise ValueError
                owner = json.loads(marker.read_text(encoding="utf-8"))
                if (set(owner) != {"version", "pid", "created", "run"} or owner["version"] != 1
                        or type(owner["pid"]) is not int or owner["pid"] <= 0
                        or not isinstance(owner["created"], str) or owner["run"] != path.name):
                    raise ValueError
                if process_identity(owner["pid"]) != owner["created"]:
                    remove_owned(root, path, owner)
            except Exception:
                pending = True
        return pending
    except Exception:
        return True


class CleanupWorker:
    """One tracked daemon job; cancellation of a waiter never loses its work.

    Unlike asyncio's default executor, this worker cannot prolong interpreter
    shutdown indefinitely on a locked filesystem operation. Its ownership marker
    remains available for the next process if shutdown interrupts removal.
    """
    def __init__(self):
        self.job = None

    async def run(self, function, *args):
        if self.job is not None and not self.job.done():
            raise RuntimeError("Owned cleanup is already running")
        loop = asyncio.get_running_loop()
        job = loop.create_future()
        self.job = job
        def deliver(value, failed):
            if not job.done():
                job.set_result((value, failed))
        def work():
            try:
                value, failed = function(*args), False
            except BaseException:
                value, failed = None, True
            try:
                loop.call_soon_threadsafe(deliver, value, failed)
            except RuntimeError:
                pass  # The server has exited; startup recovery owns the marker.
        try:
            threading.Thread(target=work, name="peppi-owned-cleanup", daemon=True).start()
        except Exception:
            self.job = None
            job.cancel()
            raise OSError("Owned cleanup worker could not start") from None
        value, failed = await asyncio.shield(job)
        if failed:
            raise OSError("Owned runtime cleanup failed") from None
        return value


class RuntimeLeaseCreationError(OSError):
    def __init__(self, lease):
        super().__init__("Owned runtime initialization cleanup is incomplete")
        self.lease = lease


class RuntimeLease:
    def __init__(self, root=None, *, recover=True):
        self.root = safe_path(root or runtime_root())
        self.root.mkdir(parents=True, exist_ok=True)
        self.cleanup_pending = recover_abandoned(self.root) if recover else False
        self.path = self.root / ("run-" + uuid.uuid4().hex)
        self.owner = {"version": 1, "pid": os.getpid(), "created": process_identity(os.getpid()), "run": self.path.name}
        self.path.mkdir(mode=0o700)
        info = self.path.stat()
        self._directory_identity = (info.st_dev, info.st_ino, getattr(info, "st_birthtime_ns", None))
        self._initialized = False
        marker = self.path / "owner.json"
        try:
            marker.write_text(json.dumps(self.owner), encoding="utf-8")
            self._initialized = True
        except Exception:
            # No browser has started. Roll back only the newly created empty
            # directory and its nonsecret marker, without recursive deletion.
            try:
                self._rollback_initialization()
            except Exception:
                self.cleanup_pending = True
                raise RuntimeLeaseCreationError(self) from None
            raise

    def _known_directory(self):
        root, path = safe_path(self.root), safe_path(self.path)
        if path.parent != root or path.name != self.owner["run"] or not re.fullmatch(r"run-[a-f0-9]{32}", path.name):
            raise ValueError("Unowned runtime directory")
        if not path.exists():
            return False
        info = path.stat()
        identity = (info.st_dev, info.st_ino, getattr(info, "st_birthtime_ns", None))
        if not info.st_ino or identity != self._directory_identity:
            raise ValueError("Runtime directory identity changed")
        return True

    def _rollback_initialization(self):
        if not self._known_directory():
            return
        marker = self.path / "owner.json"
        if any(entry != marker for entry in self.path.iterdir()):
            raise ValueError("Unexpected runtime initialization contents")
        safe_path(marker)
        if marker.exists():
            if marker.stat().st_size > 1024:
                raise ValueError("Invalid runtime initialization marker")
            raw = marker.read_bytes()
            if not json.dumps(self.owner).encode("utf-8").startswith(raw):
                raise ValueError("Runtime initialization marker changed")
            marker.unlink()
        self.path.rmdir()

    def remove(self):
        if not self._initialized:
            self._rollback_initialization()
            return
        try:
            remove_owned(self.root, self.path, self.owner)
        except FileNotFoundError:
            # A failed final rmdir/marker restore can leave an empty directory.
            # Only this retained lease's original filesystem identity proves it
            # belongs to us. Startup recovery never applies this exception.
            if self._known_directory():
                self.path.rmdir()  # Nonempty or replaced directories stay refused.

    def close(self):
        try:
            self.remove()
            self.cleanup_pending = False
        except Exception:
            self.cleanup_pending = True
        return not self.cleanup_pending

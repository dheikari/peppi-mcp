import json
import os
from pathlib import Path

import pytest

from peppi_mcp.runtime_storage import RuntimeLease, recover_abandoned, remove_owned, filesystem_path


@pytest.mark.skipif(os.name != "nt", reason="Windows junction and long-path protection")
def test_long_path_junction_is_refused_and_its_target_is_protected(tmp_path):
    from _winapi import CreateJunction
    from peppi_mcp.runtime_storage import safe_path
    lease = RuntimeLease(tmp_path / "runtime")
    outside = tmp_path / "unrelated"
    outside.mkdir()
    sentinel = outside / "keep"
    sentinel.write_text("PRIVATE_FICTIONAL_SECRET")
    link = lease.path / ("a" * 90) / ("b" * 90) / "junction"
    native = filesystem_path(link)
    native.parent.mkdir(parents=True)
    CreateJunction(str(outside), str(native))
    try:
        with pytest.raises(ValueError, match="Unsafe runtime path"):
            safe_path(link)
        assert not lease.close() and lease.cleanup_pending
        assert sentinel.read_text() == "PRIVATE_FICTIONAL_SECRET"
        assert (lease.path / "owner.json").exists()
    finally:
        native.rmdir()  # Removes only this link, never the unrelated target.
        remove_owned(lease.root, lease.path, lease.owner)


@pytest.mark.skipif(os.name != "nt", reason="Windows extended-length filesystem paths")
def test_nested_long_profile_files_are_removed_without_losing_ownership(tmp_path):
    lease = RuntimeLease(tmp_path / "runtime")
    nested = lease.path / ("a" * 90) / ("b" * 90) / "fictional-cache"
    extended = Path("\\\\?\\" + str(nested))
    extended.parent.mkdir(parents=True)
    extended.write_text("PRIVATE_FICTIONAL_SECRET")
    assert len(str(nested)) > 260 and extended.is_file()
    try:
        assert lease.close() and not lease.path.exists()
    finally:
        if lease.path.exists():
            # Verified exact owned paths, never a sweep of temporary storage.
            remove_owned(Path("\\\\?\\" + str(lease.root)), Path("\\\\?\\" + str(lease.path)), lease.owner)


@pytest.mark.skipif(os.name != "nt", reason="Windows runtime ownership")
def test_owned_runtime_cleanup_preserves_live_runs_and_unrelated_files(tmp_path):
    root = tmp_path / "runtime"
    first, second = RuntimeLease(root), RuntimeLease(root)
    (first.path / "fictional-profile").mkdir()
    (first.path / "fictional-profile" / "fictional-secret").write_text("PRIVATE_COOKIE")
    assert not recover_abandoned(root)
    assert first.path.exists() and second.path.exists()
    first.owner["created"] = "old-process-identity"
    (first.path / "owner.json").write_text(json.dumps(first.owner))
    assert not recover_abandoned(root) and not first.path.exists() and second.path.exists()
    unrelated = root / "not-ours"
    unrelated.mkdir()
    (unrelated / "keep").write_text("sentinel")
    assert recover_abandoned(root) and (unrelated / "keep").exists()
    assert second.close() and not second.path.exists()
    with pytest.raises(ValueError): remove_owned(root, unrelated, {})


@pytest.mark.skipif(os.name != "nt", reason="Windows runtime ownership")
def test_untrusted_owner_and_directory_junction_are_never_traversed(tmp_path):
    import subprocess
    lease = RuntimeLease(tmp_path / "runtime")
    outside = tmp_path / "unrelated"
    outside.mkdir()
    sentinel = outside / "keep"
    sentinel.write_text("PRIVATE_SECRET")
    link = lease.path / "junction"
    # Fixed verified test paths; one shell creates a junction, never deletes it.
    subprocess.run(["powershell.exe","-NoProfile","-NonInteractive","-Command",
        "New-Item -ItemType Junction -Path $env:PEPPI_TEST_LINK -Target $env:PEPPI_TEST_TARGET | Out-Null"],
        env={**os.environ,"PEPPI_TEST_LINK":str(link),"PEPPI_TEST_TARGET":str(outside)},check=True,capture_output=True)
    assert not lease.close() and lease.cleanup_pending
    assert sentinel.read_text() == "PRIVATE_SECRET"
    link.rmdir()  # Windows removes the junction itself, not its target.
    (lease.path / "owner.json").write_text('{"pid":0}')
    assert recover_abandoned(lease.root) and lease.path.exists()
    (lease.path / "owner.json").write_text(json.dumps(lease.owner))
    remove_owned(lease.root, lease.path, lease.owner)
    assert sentinel.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows runtime ownership")
def test_abrupt_server_exit_kills_owned_children_and_recovers_its_profile(tmp_path):
    import subprocess
    import sys
    import time
    import win32api
    import win32process
    process = subprocess.Popen([sys.executable,"-u","-m","tests.crash_parent"],stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,env={**os.environ,"LOCALAPPDATA":str(tmp_path)},creationflags=subprocess.CREATE_NO_WINDOW)
    handles = []
    try:
        record = json.loads(process.stdout.readline())
        handles = [win32api.OpenProcess(0x1000,False,record[k]) for k in ("worker","child")]
        profile_root = Path(record["root"])
        assert profile_root.is_relative_to(tmp_path) and profile_root.exists()
        process.kill()
        process.wait(5)
        for _ in range(50):
            if all(win32process.GetExitCodeProcess(h)!=259 for h in handles): break
            time.sleep(.1)
        assert all(win32process.GetExitCodeProcess(h)!=259 for h in handles)
        assert not recover_abandoned(tmp_path/"peppi-mcp"/"runtime")
        assert not profile_root.exists()
    finally:
        if process.poll() is None: process.kill(); process.wait(5)
        for handle in handles: handle.Close()
        process.stdout.close(); process.stderr.close()


@pytest.mark.skipif(os.name != "nt", reason="Windows file locks")
def test_locked_file_preserves_ownership_and_retry_clears_pending(tmp_path):
    import win32file
    import win32con
    lease = RuntimeLease(tmp_path / "runtime")
    file = lease.path / "profile" / "cookie-store"
    file.parent.mkdir()
    file.write_text("PRIVATE_SECRET")
    handle = win32file.CreateFile(str(file), win32con.GENERIC_READ, 0, None,
                                 win32con.OPEN_EXISTING, 0, None)
    try:
        assert not lease.close() and lease.cleanup_pending
        assert json.loads((lease.path / "owner.json").read_text()) == lease.owner
        assert file.exists()
    finally:
        handle.Close()
    assert lease.close() and not lease.cleanup_pending and not lease.path.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows profile ownership")
def test_failed_final_directory_removal_restores_validated_marker(tmp_path, monkeypatch):
    lease = RuntimeLease(tmp_path / "runtime")
    rmdir = Path.rmdir
    def fail(path):
        if filesystem_path(path) == filesystem_path(lease.path):
            raise PermissionError("PRIVATE_SECRET")
        return rmdir(path)
    monkeypatch.setattr(Path, "rmdir", fail)
    assert not lease.close()
    assert json.loads((lease.path / "owner.json").read_text()) == lease.owner
    monkeypatch.setattr(Path, "rmdir", rmdir)
    assert lease.close() and not lease.path.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows process identity")
def test_stuck_daemon_removal_does_not_block_exit_and_next_start_recovers(tmp_path):
    import subprocess
    import sys
    process = subprocess.Popen([sys.executable,"-u","-m","tests.daemon_cleanup_exit"],
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,env={**os.environ,"LOCALAPPDATA":str(tmp_path)},
        creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        stdout, stderr = process.communicate(timeout=5)
        assert process.returncode == 0 and not stderr
        result = json.loads(stdout)
        path = Path(result["path"])
        assert path.is_relative_to(tmp_path) and result["pending"] and path.exists()
        assert not recover_abandoned(path.parent) and not path.exists()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(5)


def test_shutdown_cancellation_does_not_start_new_recovery_work():
    import subprocess
    import sys
    process = subprocess.Popen([sys.executable,"-u","-m","tests.cancelled_cleanup_exit"],
        stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        stdout, stderr = process.communicate(timeout=3)
        assert process.returncode == 0 and not stdout and not stderr
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(5)


@pytest.mark.skipif(os.name != "nt", reason="Windows process identity")
def test_failed_marker_creation_removes_only_its_new_empty_directory(tmp_path, monkeypatch):
    write = Path.write_text
    def fail(path, *args, **kwargs):
        if path.name == "owner.json":
            raise OSError("PRIVATE_SECRET")
        return write(path, *args, **kwargs)
    monkeypatch.setattr(Path, "write_text", fail)
    root = tmp_path / "runtime"
    try:
        with pytest.raises(OSError):
            RuntimeLease(root)
        assert not list(root.glob("run-*"))
    finally:
        for path in root.glob("run-*"):
            assert not list(path.iterdir())
            path.rmdir()


def test_cleanup_thread_start_failure_can_be_retried(monkeypatch):
    import asyncio
    import threading
    from peppi_mcp.runtime_storage import CleanupWorker
    start = threading.Thread.start
    def fail(*args):
        raise RuntimeError("PRIVATE_SECRET")
    async def run():
        worker = CleanupWorker()
        monkeypatch.setattr(threading.Thread, "start", fail)
        try:
            with pytest.raises(OSError):
                await worker.run(lambda: True)
        finally:
            monkeypatch.setattr(threading.Thread, "start", start)
        assert await worker.run(lambda: True)
    asyncio.run(run())


@pytest.mark.skipif(os.name != "nt", reason="Windows filesystem identity")
def test_live_lease_missing_marker_retry_requires_empty_original_directory(tmp_path):
    lease = RuntimeLease(tmp_path / "runtime")
    (lease.path / "owner.json").unlink()
    foreign = lease.path / "unrecognized"
    foreign.write_text("PRIVATE_SECRET")
    assert not lease.close() and foreign.read_text() == "PRIVATE_SECRET"
    foreign.unlink()
    assert lease.close() and not lease.path.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows filesystem identity")
def test_retained_lease_refuses_a_replacement_directory(tmp_path):
    lease = RuntimeLease(tmp_path / "runtime")
    (lease.path / "owner.json").unlink()
    lease.path.rmdir()
    lease.path.mkdir()
    try:
        assert not lease.close() and lease.path.exists()
    finally:
        lease.path.rmdir()  # Empty fictional directory created by this test.


@pytest.mark.skipif(os.name != "nt", reason="Windows runtime ownership")
def test_startup_preserves_even_empty_directories_with_unknown_ownership(tmp_path):
    root = tmp_path / "runtime"
    unknown = root / ("run-" + "a" * 32)
    unknown.mkdir(parents=True)
    assert recover_abandoned(root) and unknown.exists()
    unknown.rmdir()

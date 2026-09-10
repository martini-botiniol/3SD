import errno
import os
from pathlib import Path
import subprocess
import sys
from threading import Event, Thread
from unittest.mock import patch

import pytest

from cartridge_launcher.domain.errors import CartridgeError, ErrorCode
from cartridge_launcher.infrastructure.storage import fileLock
from tests.unit.test_cartridge_repair_service import repairService
from cartridge_launcher.services.cartridge_creation_service import CartridgeCreationService
from cartridge_launcher.infrastructure.steam_client import SteamClient


def test_thread_contention_times_out_and_can_retry(tmp_path):
    path = tmp_path / "write.lock"
    ready, release = Event(), Event()

    def hold():
        with fileLock(path):
            ready.set()
            release.wait(5)

    worker = Thread(target=hold)
    worker.start()
    try:
        assert ready.wait(2)
        with pytest.raises(CartridgeError) as exc:
            with fileLock(path, timeoutSeconds=0.05):
                pytest.fail("Concurrent transaction entered")
        assert exc.value.code == ErrorCode.STORAGE_BUSY
    finally:
        release.set()
        worker.join(2)
    assert not worker.is_alive()
    with fileLock(path, timeoutSeconds=0.1):
        pass


def test_existing_lock_file_and_exception_do_not_block_games_or_retry(tmp_path):
    path = tmp_path / ".cartridge" / "write.lock"
    path.parent.mkdir()
    path.write_bytes(b"0")
    game = tmp_path / "SteamLibrary" / "steamapps" / "common" / "Game" / "data"
    game.parent.mkdir(parents=True)
    with pytest.raises(ValueError, match="repair failed"):
        with fileLock(path):
            game.write_bytes(b"game update")
            raise ValueError("repair failed")
    assert game.read_bytes() == b"game update"
    assert path.exists()
    with fileLock(path, timeoutSeconds=0.1):
        pass


def test_readonly_lock_error_is_immediate_and_releases_thread_lock(tmp_path):
    path = tmp_path / "write.lock"
    with patch.object(Path, "open", side_effect=PermissionError(errno.EACCES, "readonly")):
        with pytest.raises(CartridgeError) as exc:
            with fileLock(path):
                pytest.fail("Cannot enter readonly storage")
    assert exc.value.code == ErrorCode.STORAGE_WRITE_ERROR
    assert str(path) in exc.value.message
    with fileLock(path, timeoutSeconds=0.1):
        pass


def test_repair_busy_preserves_manifest_and_succeeds_on_retry(tmp_path):
    root = tmp_path / "ssd"
    service = repairService(tmp_path, root)
    service.repair(root, "Original", "111")
    manifest = root / ".cartridge" / "manifest.json"
    original = manifest.read_bytes()
    ready, release = Event(), Event()

    def hold():
        with fileLock(root / ".cartridge" / "write.lock"):
            ready.set()
            release.wait(5)

    worker = Thread(target=hold)
    worker.start()
    try:
        assert ready.wait(2)
        with patch("cartridge_launcher.services.cartridge_writer.fileLock",
                   side_effect=lambda path: fileLock(path, timeoutSeconds=0.05)):
            with pytest.raises(CartridgeError) as exc:
                service.repair(root, "Repaired", "222")
        assert exc.value.code == ErrorCode.STORAGE_BUSY
        assert manifest.read_bytes() == original
    finally:
        release.set()
        worker.join(2)
    assert service.repair(root, "Repaired", "222").appId == "222"


def test_created_cartridge_allows_steam_write_and_repair_with_lock_file(tmp_path):
    root = tmp_path / "ssd"
    repair = repairService(tmp_path, root)
    creator = CartridgeCreationService(repair.security, repair.registry, repair.deviceScanner)
    creator.create(root, "Game", "111")
    assert (root / ".cartridge" / "write.lock").exists()
    SteamClient().ensureLibraryWritable(root / "SteamLibrary")
    assert repair.repair(root, "Game", "111").appId == "111"
    SteamClient().ensureLibraryWritable(root / "SteamLibrary")


def test_process_contention_and_exit_release_lock(tmp_path):
    path = tmp_path / "write.lock"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[2] / "src")
    script = """
import os, sys
from pathlib import Path
from cartridge_launcher.infrastructure.storage import fileLock
with fileLock(Path(sys.argv[1])):
    print('locked', flush=True)
    sys.stdin.readline()
    os._exit(0)
"""
    process = subprocess.Popen([sys.executable, "-u", "-c", script, str(path)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, env=environment)
    ready = Event()
    def read_ready():
        if process.stdout.readline().strip() == "locked":
            ready.set()
    reader = Thread(target=read_ready, daemon=True)
    reader.start()
    try:
        assert ready.wait(5)
        with pytest.raises(CartridgeError) as exc:
            with fileLock(path, timeoutSeconds=0.05):
                pytest.fail("Concurrent process entered")
        assert exc.value.code == ErrorCode.STORAGE_BUSY
        process.communicate("exit\n", timeout=5)
        assert process.returncode == 0
        with fileLock(path, timeoutSeconds=0.1):
            pass
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)
        reader.join(1)

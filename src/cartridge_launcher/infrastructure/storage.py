from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import tempfile
import threading
import time

from cartridge_launcher.domain.errors import CartridgeError, ErrorCode

_threads: dict[str, threading.RLock] = {}
_guard = threading.Lock()


@contextmanager
def fileLock(path: Path):
    """Serialize read/modify/write transactions across threads and processes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with _guard:
        lock = _threads.setdefault(str(path.resolve()).casefold(), threading.RLock())
    with lock, path.open("a+b") as stream:
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        deadline = time.monotonic() + 10
        while True:
            try:
                stream.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise CartridgeError(ErrorCode.STORAGE_ERROR, "Los datos estan ocupados. Intenta de nuevo.") from exc
                time.sleep(0.05)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def atomicWrite(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def writePortableManifest(root: Path, payload: dict) -> None:
    from cartridge_launcher.services.portable_authorization import canonical
    metadata = root / ".cartridge"
    metadata.mkdir(exist_ok=True)
    (root / "SteamLibrary").mkdir(exist_ok=True)
    manifest = metadata / "manifest.json"
    if manifest.is_file():
        atomicWrite(metadata / "manifest.previous.json", manifest.read_bytes())
    # V2 is a single atomic commit: no detached signature can get out of sync.
    atomicWrite(manifest, canonical(payload))

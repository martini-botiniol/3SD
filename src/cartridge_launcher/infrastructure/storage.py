from __future__ import annotations

from contextlib import contextmanager
import errno
import os
from pathlib import Path
import tempfile
import threading
import time

from cartridge_launcher.domain.errors import CartridgeError, ErrorCode

_threads: dict[str, threading.RLock] = {}
_guard = threading.Lock()


@contextmanager
def fileLock(path: Path, timeoutSeconds: float = 10.0):
    """Bound lock contention across threads and processes; never lock a volume.

    The file stays in place to preserve one shared lock identity. Its presence
    does not mean a transaction is active; the OS releases the lock on close.
    """
    deadline = time.monotonic() + timeoutSeconds

    def busy():
        return CartridgeError(ErrorCode.STORAGE_BUSY,
            f"Otra operacion esta usando {path}. Espera a que termine y vuelve a intentar.")

    with _guard:
        lock = _threads.setdefault(str(path.resolve()).casefold(), threading.RLock())
    if not lock.acquire(timeout=max(0.0, deadline - time.monotonic())):
        raise busy()
    try:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            stream = path.open("a+b")
        except OSError as exc:
            raise CartridgeError(ErrorCode.STORAGE_WRITE_ERROR,
                f"No se puede abrir {path} para escribir. Revisa la proteccion de escritura "
                "y los permisos del disco.") from exc
        with stream:
            try:
                if stream.tell() == 0:
                    stream.write(b"0")
                    stream.flush()
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
                        if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                            raise
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise busy() from exc
                        time.sleep(min(0.05, remaining))
            except OSError as exc:
                raise CartridgeError(ErrorCode.STORAGE_WRITE_ERROR,
                    f"No se puede preparar {path} para guardar. Revisa el disco, "
                    "sus permisos y el espacio disponible.") from exc
            try:
                yield
            finally:
                stream.seek(0)
                if os.name == "nt":
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    finally:
        lock.release()


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
    (root / "SteamLibrary" / "steamapps").mkdir(exist_ok=True)
    manifest = metadata / "manifest.json"
    if manifest.is_file():
        atomicWrite(metadata / "manifest.previous.json", manifest.read_bytes())
    # V2 is a single atomic commit: no detached signature can get out of sync.
    atomicWrite(manifest, canonical(payload))

from __future__ import annotations

from pathlib import Path


ERROR_ALREADY_EXISTS = 183


class SingleInstanceLock:
    def __init__(self, path: Path, mutexName: str = "Local\\CartridgeLauncherSingleInstance"):
        self.path = path
        self.acquired = False
        self.mutexName = mutexName
        self.mutex = None

    def acquire(self) -> bool:
        if self._acquireWindowsMutex():
            self.acquired = True
            return True
        if self.mutex is not None:
            return False

        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            return False
        self.path.write_text("locked", encoding="utf-8")
        self.acquired = True
        return True

    def release(self) -> None:
        if self.mutex is not None:
            self._releaseWindowsMutex()
            self.acquired = False
            return

        if self.acquired and self.path.exists():
            self.path.unlink()
        self.acquired = False

    def _acquireWindowsMutex(self) -> bool:
        try:
            import win32api
            import win32event
        except ModuleNotFoundError:
            return False

        mutex = win32event.CreateMutex(None, False, self.mutexName)
        lastError = win32api.GetLastError()
        self.mutex = mutex
        return lastError != ERROR_ALREADY_EXISTS

    def _releaseWindowsMutex(self) -> None:
        try:
            import win32api
            import win32event

            win32event.ReleaseMutex(self.mutex)
            win32api.CloseHandle(self.mutex)
        except Exception:
            pass
        self.mutex = None


class SingleInstanceSignal:
    def __init__(self, path: Path | None = None):
        self.path = path or (Path.home() / ".cartridge-launcher" / "open.signal")

    def create(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def close(self) -> None:
        pass

    def signalExisting(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("open", encoding="utf-8")
        return True

    def wasSignaled(self) -> bool:
        if not self.path.exists():
            return False
        self.path.unlink()
        return True

"""One operation dialog per library, plus a process-wide notification gate."""
from __future__ import annotations


class OperationWindowGate:
    NAME = "Local\\3SDOperationDialog"

    def __init__(self):
        self.handle = None

    def acquire(self):
        import win32api
        import win32event
        handle = win32event.CreateMutex(None, False, self.NAME)
        if win32api.GetLastError() == 183:
            win32api.CloseHandle(handle)
            return False
        self.handle = handle
        return True

    def release(self):
        if self.handle is not None:
            import win32api
            # We hold the handle, not ownership of the mutex.
            win32api.CloseHandle(self.handle)
            self.handle = None

    @classmethod
    def isActive(cls):
        import win32api
        import win32event
        import pywintypes
        try:
            handle = win32event.OpenMutex(0x00100000, False, cls.NAME)
        except pywintypes.error:
            return False
        win32api.CloseHandle(handle)
        return True


class DialogController:
    def __init__(self, factory, beforeOpen=lambda: None, gate=None):
        self.factory = factory
        self.beforeOpen = beforeOpen
        self.gate = gate or OperationWindowGate()
        self.dialog = None
        self.opening = False

    @property
    def active(self):
        return self.dialog is not None or self.opening

    def open(self, operation):
        if self.dialog is not None:
            self.dialog.focus()
            return self.dialog
        if self.opening:
            return None
        self.opening = True
        try:
            if not self.gate.acquire():
                return None
            self.beforeOpen()
            dialog = self.factory(operation, self._closed)
            self.dialog = dialog
            dialog.show()
            return dialog
        except Exception:
            if self.dialog is not None:
                self.dialog.close()
            self._closed()
            raise
        finally:
            self.opening = False

    def _closed(self):
        self.dialog = None
        self.gate.release()

    def close(self):
        if self.dialog is None:
            return True
        return self.dialog.close()

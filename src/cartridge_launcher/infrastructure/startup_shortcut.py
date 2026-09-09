from __future__ import annotations

import sys
import os
import subprocess
from pathlib import Path


def startupShortcutPath() -> Path:
    from win32com.shell import shell, shellcon

    return Path(shell.SHGetFolderPath(0, shellcon.CSIDL_STARTUP, None, 0)) / "3SD.lnk"


def windowPython() -> Path:
    executable = Path(sys.executable)
    candidate = executable.with_name("pythonw.exe")
    return candidate if os.name == "nt" and candidate.is_file() else executable


def startupCommand() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "tray", "--steam-action", "auto"]
    return [str(windowPython()), "-I", "-m", "cartridge_launcher.app.main", "tray", "--steam-action", "auto"]


def isStartupEnabled() -> bool:
    path = startupShortcutPath()
    if not path.is_file():
        return False
    try:
        import win32com.client

        shortcut = win32com.client.Dispatch("WScript.Shell").CreateShortcut(str(path))
        return Path(shortcut.TargetPath).is_file() and "tray" in shortcut.Arguments
    except Exception:
        return False


def createShortcut(path: Path, command: list[str], workingDirectory: Path) -> None:
    import win32com.client

    path.parent.mkdir(parents=True, exist_ok=True)
    shortcut = win32com.client.Dispatch("WScript.Shell").CreateShortcut(str(path))
    shortcut.TargetPath = command[0]
    shortcut.Arguments = subprocess.list2cmdline(command[1:])
    shortcut.WorkingDirectory = str(workingDirectory)
    shortcut.IconLocation = command[0]
    shortcut.Save()


def enableStartup() -> Path:
    path = startupShortcutPath()
    createShortcut(path, startupCommand(), Path(sys.executable).parent)
    return path


def disableStartup() -> None:
    path = startupShortcutPath()
    if path.exists():
        path.unlink()

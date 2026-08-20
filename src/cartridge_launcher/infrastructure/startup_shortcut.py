from __future__ import annotations

import sys
from pathlib import Path


def startupShortcutPath() -> Path:
    return Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "3SD.lnk"


def startupCommand() -> list[str]:
    executable = Path(sys.executable)
    if executable.name.lower() == "3sd.exe":
        return [str(executable), "tray", "--steam-action", "open"]
    return [str(executable), "-m", "cartridge_launcher.app.main", "tray", "--steam-action", "open"]


def isStartupEnabled() -> bool:
    return startupShortcutPath().is_file()


def enableStartup() -> Path:
    path = startupShortcutPath()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import win32com.client

        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(str(path))
        command = startupCommand()
        shortcut.TargetPath = command[0]
        shortcut.Arguments = " ".join(command[1:])
        shortcut.WorkingDirectory = str(Path(command[0]).parent)
        shortcut.IconLocation = command[0]
        shortcut.Save()
    except Exception:
        path.write_text(" ".join(startupCommand()), encoding="utf-8")
    return path


def disableStartup() -> None:
    path = startupShortcutPath()
    if path.exists():
        path.unlink()

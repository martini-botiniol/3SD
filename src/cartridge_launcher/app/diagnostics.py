"""Read-only runtime checks, also used before publishing an installation."""
from __future__ import annotations

import argparse
import sys
import tkinter as tk
from importlib.metadata import version


def check() -> None:
    import pystray
    import win32api
    import win32com.client
    from cartridge_launcher.app.main import buildParser
    from cartridge_launcher.ui.tray_app import createTrayIcon

    print(f"Python: {sys.executable} ({sys.version.split()[0]})")
    for package in ("3sd", "Pillow", "pystray", "pywin32", "six"):
        print(f"{package}: {version(package)}")
    root = tk.Tk()
    root.withdraw()
    root.update()
    root.destroy()
    win32com.client.Dispatch("WScript.Shell")
    icon = pystray.Icon("3sd-diagnostic", createTrayIcon())
    assert icon is not None and buildParser() is not None
    print("Tkinter, bandeja e integracion Windows: OK")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true", help="Abrir 3SD conservando la consola")
    args = parser.parse_args()
    check()
    if args.run:
        from cartridge_launcher.app.main import main as launch
        raise SystemExit(launch(["tray", "--open-window", "--steam-action", "open"]))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        from pathlib import Path
        from cartridge_launcher.infrastructure.logging_config import configureLogging
        configureLogging(Path.home() / ".3sd" / "launcher.log").exception("Diagnostico fallido")
        raise

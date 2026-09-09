"""Opt-in desktop smoke test. Run with installed Python after exiting 3SD.

Does not launch Steam or prepare/repair cartridges. Writes a JSON result.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


def main() -> None:
    import win32con
    import win32gui
    from cartridge_launcher.app.main import services, defaultDataDirectory
    from cartridge_launcher.infrastructure.single_instance import SingleInstanceLock
    from cartridge_launcher.ui.tray_app import TrayApp

    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    lock = SingleInstanceLock(defaultDataDirectory() / "3sd.lock")
    if not lock.acquire():
        raise RuntimeError("Cierra 3SD antes de la prueba de escritorio.")
    results = {}
    security, registry, scanner, logger = services()
    app = TrayApp(security, registry, scanner, logger, steamAction="none")
    originalLoop = app._mainLoop

    def finish(code: int) -> None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(results, indent=2), encoding="utf-8")
        app.exitApp()

    def guarded(callback):
        def run():
            try:
                callback()
            except Exception as exc:
                results["error"] = repr(exc)
                args.report.parent.mkdir(parents=True, exist_ok=True)
                args.report.write_text(json.dumps(results, indent=2), encoding="utf-8")
                app.exitProcess = lambda code: sys.exit(1)
                app.exitApp()
        return run

    def requestLibrary():
        assert app.running and app.icon.visible and not app.libraryOpen
        results["residentWithoutLibrary"] = True
        child = subprocess.run([str(Path(sys.executable).with_name("pythonw.exe")), "-I", "-m",
                                "cartridge_launcher.app.main", "tray", "--open-window", "--steam-action", "none"],
                               timeout=15, check=True)
        results["secondInstanceExited"] = child.returncode == 0

    def closeLibrary():
        assert app.libraryProcess is not None and app.libraryProcess.poll() is None
        windows = []
        win32gui.EnumWindows(lambda hwnd, _: windows.append(hwnd) if win32gui.GetWindowText(hwnd) == "3SD"
                             and win32gui.IsWindowVisible(hwnd) else None, None)
        assert len(windows) == 1, f"Se esperaba una biblioteca visible; hay {len(windows)}"
        results["oneVisibleLibrary"] = True
        win32gui.PostMessage(windows[0], win32con.WM_CLOSE, 0, 0)

    def complete():
        assert app.running and app.icon.visible and app.libraryProcess is None
        results["closingLibraryKeepsTray"] = True
        results["success"] = True
        finish(0)

    def timedLoop():
        app.statusRoot.after(1000, guarded(requestLibrary))
        app.statusRoot.after(6000, guarded(closeLibrary))
        app.statusRoot.after(9000, guarded(complete))
        originalLoop()

    app._mainLoop = timedLoop
    try:
        app.run()
    finally:
        lock.release()


if __name__ == "__main__":
    main()

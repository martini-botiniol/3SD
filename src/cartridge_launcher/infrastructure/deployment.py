"""Publish checked installations with rollback of shortcuts and entrypoints."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

from cartridge_launcher.infrastructure.startup_shortcut import createShortcut, startupShortcutPath


def startupWanted(previous: bool, legacy: bool, shortcutExists: bool) -> bool:
    return shortcutExists if previous or legacy else True


def shortcutPaths() -> tuple[Path, Path, Path]:
    from win32com.shell import shell, shellcon
    desktop = Path(shell.SHGetFolderPath(0, shellcon.CSIDL_DESKTOPDIRECTORY, None, 0))
    programs = Path(shell.SHGetFolderPath(0, shellcon.CSIDL_PROGRAMS, None, 0))
    return desktop / "3SD.lnk", programs / "3SD" / "3SD.lnk", startupShortcutPath()


def publish(root: Path, runtime: Path, source: Path) -> None:
    root, runtime = root.resolve(), runtime.resolve()
    if runtime.parent != root / "runtimes" or not (runtime / "Scripts" / "pythonw.exe").is_file():
        raise ValueError("Entorno fuera de la instalacion o incompleto.")
    manifest = root / "installation.json"
    previous = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else None
    desktop, menu, startup = shortcutPaths()
    legacy = (root / "3SD.exe").exists() or desktop.exists() or menu.exists()
    enabled = startupWanted(previous is not None, legacy, startup.exists())
    launcher = root / "Abrir-3SD.bat"
    diagnostic = root / "Diagnosticar-3SD.bat"
    cleanup = source / "scripts" / "cleanup_legacy.ps1"
    cleanupTarget = root / "cleanup_legacy.ps1"
    targets = [desktop, menu, startup, launcher, diagnostic, manifest, cleanupTarget]
    snapshot = {path: path.read_bytes() if path.exists() else None for path in targets}
    # Inventory stays outside user data and survives rollback for troubleshooting.
    (runtime / "migration-inventory.json").write_text(json.dumps({
        "legacyExe": str(root / "3SD.exe"), "legacyExeExists": (root / "3SD.exe").exists(),
        "shortcuts": {str(path): path.exists() for path in (desktop, menu, startup)},
        "startupEnabled": enabled, "previous": previous,
    }, indent=2), encoding="utf-8")
    pythonw = runtime / "Scripts" / "pythonw.exe"
    command = [str(pythonw), "-I", "-m", "cartridge_launcher.app.main", "tray", "--steam-action", "open"]
    try:
        if cleanup.is_file():
            shutil.copy2(cleanup, cleanupTarget)
        createShortcut(desktop, command + ["--open-window"], root)
        createShortcut(menu, command + ["--open-window"], root)
        if enabled:
            createShortcut(startup, command, root)
        else:
            startup.unlink(missing_ok=True)
        # Only a generated hex generation name is embedded in batch code; user paths use %~dp0.
        relative = runtime.relative_to(root)
        launcher.write_text(
            '@echo off\nsetlocal\nstart "" "%~dp0' + str(relative / "Scripts" / "pythonw.exe") +
            '" -I -m cartridge_launcher.app.main tray --open-window --steam-action open\n', encoding="utf-8")
        diagnostic.write_text(
            '@echo off\nsetlocal\n"%~dp0' + str(relative / "Scripts" / "python.exe") +
            '" -I -m cartridge_launcher.app.diagnostics %*\nset "RESULT=%ERRORLEVEL%"\npause\nexit /b %RESULT%\n', encoding="utf-8")
        state = {"schemaVersion": 1, "runtime": str(runtime),
                 "previousRuntime": previous["runtime"] if previous else None}
        temporary = manifest.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
        temporary.replace(manifest)
    except Exception:
        for path, content in snapshot.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
        raise
    print(f"Publicada: {runtime}. Inicio con Windows: {'activado' if enabled else 'desactivado'}")
    if previous or legacy:
        print("Si 3SD estaba abierto, sal desde la bandeja y vuelve a abrirlo para usar la nueva version.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    publish(args.root, Path(sys.prefix), args.source)

"""Versioned standalone installation; user data and SSDs are never removed."""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

from cartridge_launcher.infrastructure.deployment import shortcutPaths
from cartridge_launcher.infrastructure.startup_shortcut import createShortcut
from cartridge_launcher.infrastructure.storage import atomicWrite, fileLock


def install(root: Path, source: Path) -> None:
    root, source = root.resolve(), source.resolve()
    if not (source / "3SD.exe").is_file() or not (source / "_internal").is_dir():
        raise ValueError("Paquete incompleto: conserva 3SD.exe junto a _internal.")
    if root == source or root.is_relative_to(source) or source.is_relative_to(root):
        raise ValueError("Extrae el paquete fuera de la carpeta de instalacion antes de actualizar.")
    with fileLock(root / "install.lock"):
        manifest = root / "standalone.json"
        previous = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else None
        candidate = root / "packages" / uuid.uuid4().hex
        shutil.copytree(source, candidate)
        # Never activate an unchecked executable. Previous generation survives failure.
        subprocess.run([str(candidate / "3SD.exe"), "self-check"], check=True, timeout=30,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        desktop, menu, startup = shortcutPaths()
        uninstallShortcut = menu.with_name("Desinstalar 3SD.lnk")
        targets = (desktop, menu, startup, uninstallShortcut, manifest)
        before = {path: path.read_bytes() if path.exists() else None for path in targets}
        existing = previous is not None or desktop.exists() or menu.exists()
        enableStartup = startup.exists() if existing else True
        command = [str(candidate / "3SD.exe"), "tray", "--steam-action", "auto"]
        try:
            createShortcut(desktop, command + ["--open-window"], candidate)
            createShortcut(menu, command + ["--open-window"], candidate)
            if enableStartup:
                createShortcut(startup, command, candidate)
            createShortcut(uninstallShortcut, [str(candidate / "3SD.exe"), "uninstall", "--install-directory", str(root)], candidate)
            atomicWrite(manifest, json.dumps({"schemaVersion": 1, "package": str(candidate),
                "previousPackage": previous.get("package") if previous else None}).encode("utf-8"))
        except Exception:
            for path, content in before.items():
                if content is None:
                    path.unlink(missing_ok=True)
                else:
                    atomicWrite(path, content)
            raise


def uninstall(root: Path) -> None:
    """Deactivate owned shortcuts. Keep packages for explicit removal after exit."""
    root = root.resolve()
    manifest = root / "standalone.json"
    if not manifest.is_file():
        raise ValueError("No se encontro una instalacion autonoma en esta carpeta.")
    with fileLock(root / "install.lock"):
        import win32com.client
        desktop, menu, startup = shortcutPaths()
        for path in (desktop, menu, startup, menu.with_name("Desinstalar 3SD.lnk")):
            if path.exists():
                target = Path(win32com.client.Dispatch("WScript.Shell").CreateShortcut(str(path)).TargetPath).resolve()
                if target.is_relative_to(root / "packages"):
                    path.unlink()
        atomicWrite(root / "standalone.removed.json", manifest.read_bytes())
        manifest.unlink()
    # Windows cannot remove this running executable. Tell the user exactly what remains.
    import ctypes
    ctypes.windll.user32.MessageBoxW(None,
        f"Se quitaron los accesos directos y el inicio automatico.\nCierra 3SD desde la bandeja y elimina esta carpeta para liberar espacio:\n{root}\n\nTu biblioteca en .3sd y los SSD se conservan.",
        "3SD desinstalado", 0)


def selfCheck() -> None:
    import tkinter
    import win32api
    import win32com.client
    import pystray
    from cartridge_launcher.services.portable_authorization import authorize, verifyAuthorization
    tkinter.Tcl().eval("info patchlevel")
    root = tkinter.Tk()
    root.withdraw()
    try:
        root.update_idletasks()
    finally:
        root.destroy()
    verifyAuthorization(authorize({"schemaVersion": 2, "cartridgeId": "self-check", "appId": "1"}))

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from cartridge_launcher.infrastructure.logging_config import configureLogging
from cartridge_launcher.infrastructure.single_instance import SingleInstanceLock, SingleInstanceSignal
from cartridge_launcher.infrastructure.startup_shortcut import disableStartup, enableStartup, isStartupEnabled
from cartridge_launcher.infrastructure.windows_devices import WindowsDeviceScanner
from cartridge_launcher.services.cartridge_creation_service import CartridgeCreationService
from cartridge_launcher.services.cartridge_conversion_service import CartridgeConversionService
from cartridge_launcher.services.cartridge_repair_service import CartridgeRepairService
from cartridge_launcher.services.cartridge_update_service import CartridgeUpdateService
from cartridge_launcher.services.local_registry import LocalRegistry
from cartridge_launcher.services.security_service import SecurityService
from cartridge_launcher.ui.main_window import runLauncherUi
from cartridge_launcher.ui.tray_app import TrayApp


def defaultDataDirectory() -> Path:
    return Path.home() / ".3sd"


def defaultArgs() -> argparse.Namespace:
    return buildParser().parse_args([])


def buildParser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="3SD")
    subparsers = parser.add_subparsers(dest="command")
    ui = subparsers.add_parser("ui")
    ui.add_argument("--from-tray", action="store_true", help=argparse.SUPPRESS)
    tray = subparsers.add_parser("tray")
    tray.add_argument("--steam-action", choices=("auto", "open", "install", "none"), default="auto")
    tray.add_argument("--open-window", action="store_true")
    for name in ("create", "update", "repair"):
        command = subparsers.add_parser(name)
        command.add_argument("--root", required=True)
        command.add_argument("--display-name", required=True)
        command.add_argument("--app-id", required=True)
    convert = subparsers.add_parser("convert")
    convert.add_argument("--root", required=True)
    subparsers.add_parser("self-check")
    for name in ("install", "uninstall"):
        command = subparsers.add_parser(name)
        command.add_argument("--install-directory", type=Path,
            default=Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Programs" / "3SD")
    startup = subparsers.add_parser("startup")
    startup.add_argument("action", choices=("enable", "disable", "status"))
    return parser


def requiresSingleInstance(command: str | None, args: argparse.Namespace | None = None) -> bool:
    if command == "ui" and args is not None and getattr(args, "from_tray", False):
        return False
    return command in (None, "tray", "ui")


def services():
    dataDirectory = defaultDataDirectory()
    security = SecurityService(dataDirectory / "launcher.secret")
    registry = LocalRegistry(dataDirectory / "registry.json")
    scanner = WindowsDeviceScanner()
    logger = configureLogging(dataDirectory / "launcher.log")
    return security, registry, scanner, logger


def main(argv: list[str] | None = None) -> int:
    args = buildParser().parse_args(argv)
    if args.command == "self-check":
        from cartridge_launcher.infrastructure.standalone_install import selfCheck
        selfCheck()
        return 0
    if args.command in ("install", "uninstall"):
        from cartridge_launcher.infrastructure.standalone_install import install, uninstall
        if not getattr(sys, "frozen", False):
            raise ValueError("Usa estos comandos desde el paquete autonomo 3SD.exe.")
        if args.command == "install":
            install(args.install_directory, Path(sys.executable).parent)
        else:
            uninstall(args.install_directory)
        return 0
    if args.command is None:
        args = buildParser().parse_args(["tray", "--open-window"])
    command = args.command or defaultCommand()
    lock: SingleInstanceLock | None = None
    if requiresSingleInstance(command, args):
        lock = SingleInstanceLock(defaultDataDirectory() / "3sd.lock")
        if not lock.acquire():
            if command != "tray" or args.open_window:
                SingleInstanceSignal().signalExisting()
            return 0

    security, registry, scanner, logger = services()
    try:
        if command == "ui":
            runLauncherUi(security, registry, scanner, logger, suppressStatePopups=getattr(args, "from_tray", False))
            return 0
        if command == "tray":
            TrayApp(security, registry, scanner, logger, steamAction=args.steam_action, openWindowOnStart=args.open_window).run()
            return 0
        if command == "create":
            manifest = CartridgeCreationService(security, registry, scanner).create(Path(args.root), args.display_name, args.app_id)
            print(f"Cartucho creado: {manifest.displayName}")
            return 0
        if command == "convert":
            manifest = CartridgeConversionService(security, registry, scanner).convert(Path(args.root))
            print(f"Cartucho portable: {manifest.displayName}")
            return 0
        if command == "update":
            manifest = CartridgeUpdateService(security, registry, scanner).update(Path(args.root), args.display_name, args.app_id)
            print(f"Cartucho actualizado: {manifest.displayName}")
            return 0
        if command == "repair":
            manifest = CartridgeRepairService(security, registry, scanner).repair(Path(args.root), args.display_name, args.app_id)
            print(f"Cartucho reparado: {manifest.displayName}")
            return 0
        if command == "startup":
            if args.action == "enable":
                print(enableStartup())
            elif args.action == "disable":
                disableStartup()
                print("Desactivado")
            else:
                print("Activado" if isStartupEnabled() else "Desactivado")
            return 0
        return 1
    finally:
        if lock is not None:
            lock.release()


def defaultCommand() -> str:
    return "tray"


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        configureLogging(defaultDataDirectory() / "launcher.log").exception("No se pudo iniciar 3SD")
        raise

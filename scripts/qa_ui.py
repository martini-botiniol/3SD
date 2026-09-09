"""Opt-in hidden Tk smoke test: temporary cartridges, no Steam/network/startup writes."""
import logging
from pathlib import Path
import tempfile
import time
import tkinter as tk
from unittest.mock import Mock, patch

from cartridge_launcher.app.state import AppState
from cartridge_launcher.domain.models import DeviceInfo
from cartridge_launcher.services.cartridge_creation_service import CartridgeCreationService
from cartridge_launcher.services.cartridge_session_service import CartridgeSessionService
from cartridge_launcher.services.cartridge_validator import CartridgeValidator
from cartridge_launcher.services.cartridge_watch_service import CartridgeWatchService
from cartridge_launcher.services.local_registry import LocalRegistry
from cartridge_launcher.services.runtime_status import RuntimeStatusStore
from cartridge_launcher.services.security_service import SecurityService
from cartridge_launcher.services.steam_integration import SteamIntegration
from cartridge_launcher.services.steam_action_service import ActionResult
from cartridge_launcher.ui.main_window import LauncherWindow


def main():
    with tempfile.TemporaryDirectory(prefix="3sd-ui-") as directory:
        base = Path(directory)
        disk = base / "ssd"
        disk.mkdir()
        security, registry = SecurityService(base / "secret"), LocalRegistry(base / "registry.json")
        scanner = Mock()
        device = DeviceInfo(str(disk), "TEST", 100)
        scanner.scan.return_value = {str(disk): device}
        scanner.findDeviceByRoot.return_value = device
        CartridgeCreationService(security, registry, scanner).create(disk, "Juego de prueba", "111")
        service = CartridgeSessionService(CartridgeWatchService(CartridgeValidator(security, registry)))
        root = tk.Tk()
        root.withdraw()
        errors = []
        root.report_callback_exception = lambda *args: errors.append(args)
        try:
            with patch("cartridge_launcher.ui.main_window.defaultRuntimeStatusStore", return_value=RuntimeStatusStore(base / "status.json")), \
                 patch("cartridge_launcher.ui.main_window.isStartupEnabled", return_value=False), \
                 patch("cartridge_launcher.ui.cover_cache.downloadCover", return_value=False), \
                 patch("cartridge_launcher.ui.main_window.Path.home", return_value=base):
                window = LauncherWindow(root, security, registry, scanner, service,
                    SteamIntegration(Mock()), logging.getLogger("qa"), suppressStatePopups=True)
                window.actions = Mock()
                window.actions.execute.return_value = ActionResult("open", "running", "Prueba")
                for width, height in ((1080, 680), (720, 480)):
                    root.geometry(f"{width}x{height}")
                    window._toggleSidebar()
                    deadline = time.monotonic() + 0.3
                    while time.monotonic() < deadline:
                        root.update()
                        time.sleep(0.01)
                assert window.currentState.manifest.appId == "111"
                window._runSteamAction("auto")
                deadline = time.monotonic() + 0.3
                while time.monotonic() < deadline:
                    root.update()
                    time.sleep(0.01)
                window.actions.execute.assert_called_once()
                assert not errors, errors
                print("Hidden Tk smoke: library, sidebar, async action, two window sizes OK")
        finally:
            root.destroy()


if __name__ == "__main__":
    main()

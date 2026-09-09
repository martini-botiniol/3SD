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
                assert list(window.sidebarSections) == ["cartridges", "repair", "windows", "activity"]
                assert not any(window.sidebarSectionVisible.values())
                assert not hasattr(window, "selectedGameTitleText")
                assert not hasattr(window, "deviceCombo")
                root.geometry("720x480+20000+20000")
                root.deiconify()
                root.update()
                for operation in ("create", "update", "repair", "convert"):
                    dialog = window._openCartridgeDialog(operation)
                    root.update()
                    assert root.grab_current() == dialog.window
                    for other in ("create", "update", "repair", "convert"):
                        assert window._openCartridgeDialog(other) is dialog
                    assert dialog.operation == operation
                    assert len([child for child in root.winfo_children() if isinstance(child, tk.Toplevel)]) == 1
                    for width, height in ((560, 640), (420, 360)):
                        dialog.window.geometry(f"{width}x{height}")
                        root.update()
                        confirm = dialog.confirmButton
                        assert confirm.winfo_rooty() + confirm.winfo_height() <= dialog.window.winfo_rooty() + height
                    if operation == "create":
                        dialog.cancelButton.command()
                    elif operation == "update":
                        dialog.window.tk.call(dialog.window.protocol("WM_DELETE_WINDOW"))
                    elif operation == "repair":
                        dialog.window.focus_force()
                        dialog.window.event_generate("<Escape>")
                        root.update()
                    else:
                        dialog.close()
                    assert dialog.closed, operation
                    assert not window.dialogController.active
                    assert root.grab_current() is None
                assert not errors, errors
                print("Tk smoke: library, collapsed sidebar, async action, single modal, Cancel/Escape/X, small windows OK")
        finally:
            root.destroy()


if __name__ == "__main__":
    main()

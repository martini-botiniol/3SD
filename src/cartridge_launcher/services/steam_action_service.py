"""A cancellable action shared by UI and tray; contains no Tk calls."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time

from cartridge_launcher.domain.errors import CartridgeError, ErrorCode
from cartridge_launcher.infrastructure.storage import fileLock
from cartridge_launcher.services.runtime_status import RuntimeStatus


@dataclass(frozen=True)
class ActionResult:
    action: str
    phase: str
    message: str


class SteamActionService:
    def __init__(self, validator, scanner, steamClient, statusStore):
        self.validator, self.scanner = validator, scanner
        self.client, self.statusStore = steamClient, statusStore

    def execute(self, state, action: str, cancelled=lambda: False) -> ActionResult:
        if action not in ("auto", "open", "install"):
            raise ValueError("Accion Steam desconocida")
        root = Path(state.rootPath)
        device = self.scanner.findDeviceByRoot(root)
        if cancelled() or device is None:
            raise CartridgeError(ErrorCode.DEVICE_REMOVED, "El cartucho fue retirado.")

        def gone():
            return cancelled() or self.scanner.findDeviceByRoot(root) != device

        with fileLock(self.statusStore.path.with_suffix(".action.lock")):
            if gone():
                raise CartridgeError(ErrorCode.DEVICE_REMOVED, "El cartucho cambio.")
            manifest = self.validator.validate(root, device)
            if manifest != state.manifest:
                raise CartridgeError(ErrorCode.INVALID_MANIFEST, "El cartucho cambio; vuelve a escanear.")
            previous = self.statusStore.read()
            if previous and previous.cartridgeId == manifest.cartridgeId and previous.phase in ("accepted", "running"):
                return ActionResult(previous.action, previous.phase, "La solicitud ya fue enviada a Steam.")
            self.client.ensureAvailable()
            library = root / manifest.libraryPath
            if not self.client.isLibraryRegistered(library):
                raise CartridgeError(ErrorCode.LIBRARY_REQUIRED, f"En Steam > Parametros > Almacenamiento, añade {library} y vuelve a intentar.")
            installed = self.client.installationState(manifest.appId, library)
            if action == "auto":
                action = "open" if installed == "installed" else "install"
            if action == "open" and installed != "installed":
                raise CartridgeError(ErrorCode.GAME_NOT_INSTALLED, "Instala o completa la descarga en Steam.")
            if gone():
                raise CartridgeError(ErrorCode.DEVICE_REMOVED, "El cartucho fue retirado.")
            self.client.ensureLibraryWritable(library)

            def status(phase):
                if not gone():
                    self.statusStore.write(RuntimeStatus(manifest.cartridgeId, manifest.appId,
                        manifest.displayName, action, phase, time.time()))

            started = time.time()
            status("sending")
            if gone():
                raise CartridgeError(ErrorCode.DEVICE_REMOVED, "El cartucho fue retirado antes de enviar la solicitud.")
            if action == "open":
                self.client.openGame(manifest.appId)
            else:
                self.client.installGame(manifest.appId)
            status("accepted")
            if action == "open":
                running = self.client.waitForGameLaunch(manifest.appId, started, libraryRoot=library, cancelled=gone)
                if gone():
                    return ActionResult(action, "cancelled", "Cartucho retirado. Se cancelo la espera; el juego no se cerro a la fuerza.")
                phase = "running" if running else "unconfirmed"
                status(phase)
                return ActionResult(action, phase, "Juego iniciado." if running else "Solicitud enviada; inicio no confirmado. Revisa Steam.")
            return ActionResult(action, "accepted", "Completa o reanuda la instalacion en Steam y selecciona la biblioteca del SSD.")

from __future__ import annotations

import logging
from pathlib import Path

from cartridge_launcher.app.state import AppState
from cartridge_launcher.domain.errors import CartridgeError
from cartridge_launcher.domain.states import LauncherState
from cartridge_launcher.services.cartridge_validator import CartridgeValidator
from cartridge_launcher.services.device_monitor import DeviceChange


class CartridgeWatchService:
    def __init__(self, validator: CartridgeValidator, logger: logging.Logger | None = None):
        self.validator = validator
        self.logger = logger or logging.getLogger(__name__)

    def handleInserted(self, change: DeviceChange) -> AppState | None:
        states = self.handleInsertedStates(change)
        return states[-1] if states else None

    def handleInsertedStates(self, change: DeviceChange) -> tuple[AppState, ...]:
        root = Path(change.root)
        metadataDir = root / ".cartridge"
        if not metadataDir.exists():
            return ()

        validating = AppState(state=LauncherState.VALIDATING, rootPath=str(root))
        try:
            manifest = self.validator.validate(root, change.device)
            ready = AppState(
                state=LauncherState.READY,
                rootPath=str(root),
                cartridgeId=manifest.cartridgeId,
                manifest=manifest,
            )
            return (validating, ready)
        except CartridgeError as exc:
            self.logger.warning("Cartridge validation failed: %s %s", exc.code, exc.message)
            return (
                validating,
                AppState(state=LauncherState.INVALID_CARTRIDGE, rootPath=str(root), errorCode=exc.code, message=exc.message),
            )

    def handleRemoved(self, change: DeviceChange) -> AppState:
        return AppState(state=LauncherState.NOT_INSERTED, rootPath=str(change.root), message="waiting for cartridge")

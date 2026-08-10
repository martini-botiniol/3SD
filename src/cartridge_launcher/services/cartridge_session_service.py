from __future__ import annotations

import logging

from cartridge_launcher.app.state import AppState
from cartridge_launcher.domain.states import LauncherState
from cartridge_launcher.services.cartridge_watch_service import CartridgeWatchService
from cartridge_launcher.services.device_monitor import DeviceChange


class CartridgeSessionService:
    def __init__(self, watchService: CartridgeWatchService, logger: logging.Logger | None = None):
        self.watchService = watchService
        self.logger = logger or logging.getLogger(__name__)
        self.currentState = AppState(state=LauncherState.NOT_INSERTED, message="waiting for cartridge")
        self.lastSteamActionCartridgeId: str | None = None

    def initialState(self) -> AppState:
        return self.currentState

    def handleExisting(self, devices) -> tuple[AppState, ...]:
        states: list[AppState] = []
        for root, device in sorted(devices.items()):
            states.extend(self.handleInserted(DeviceChange(root=root, device=device)))
        return tuple(states)

    def handleInserted(self, change: DeviceChange) -> tuple[AppState, ...]:
        if self.isBlockedByActiveCartridge(change):
            self.logger.info("Ignoring inserted cartridge while another cartridge is active: %s", change.root)
            return ()
        states = self.watchService.handleInsertedStates(change)
        if states:
            self.currentState = states[-1]
        return states

    def handleRemoved(self, change: DeviceChange) -> tuple[AppState, ...]:
        if self.currentState.rootPath == str(change.root):
            self.currentState = self.watchService.handleRemoved(change)
            self.lastSteamActionCartridgeId = None
            return (self.currentState,)
        return ()

    def shouldRunSteamAction(self, state: AppState) -> bool:
        if state.state != LauncherState.READY or state.cartridgeId is None:
            return False
        if self.lastSteamActionCartridgeId == state.cartridgeId:
            return False
        return True

    def markSteamActionRun(self, state: AppState) -> None:
        if state.state == LauncherState.READY and state.cartridgeId is not None:
            self.lastSteamActionCartridgeId = state.cartridgeId

    def isBlockedByActiveCartridge(self, change: DeviceChange) -> bool:
        return self._hasActiveCartridge() and self.currentState.rootPath != str(change.root)

    def _hasActiveCartridge(self) -> bool:
        return self.currentState.state == LauncherState.READY and self.currentState.cartridgeId is not None

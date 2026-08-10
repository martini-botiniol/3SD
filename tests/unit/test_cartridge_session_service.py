from __future__ import annotations

import unittest
from pathlib import Path

from cartridge_launcher.app.state import AppState
from cartridge_launcher.domain.models import CartridgeManifest, DeviceInfo
from cartridge_launcher.domain.states import LauncherState
from cartridge_launcher.services.cartridge_session_service import CartridgeSessionService
from cartridge_launcher.services.device_monitor import DeviceChange


class CartridgeSessionServiceTests(unittest.TestCase):
    def testSteamActionRunsAgainAfterActiveCartridgeIsRemovedAndReinserted(self) -> None:
        service = CartridgeSessionService(FakeWatchService())
        inserted = service.handleInserted(deviceChange("G:\\", "cart-1"))[-1]

        self.assertTrue(service.shouldRunSteamAction(inserted))
        service.markSteamActionRun(inserted)
        self.assertFalse(service.shouldRunSteamAction(inserted))

        service.handleRemoved(deviceChange("G:\\", "cart-1"))
        reinserted = service.handleInserted(deviceChange("G:\\", "cart-1"))[-1]

        self.assertTrue(service.shouldRunSteamAction(reinserted))

    def testSecondCartridgeDoesNotReplaceActiveCartridge(self) -> None:
        service = CartridgeSessionService(FakeWatchService())
        first = service.handleInserted(deviceChange("G:\\", "cart-1"))[-1]

        states = service.handleInserted(deviceChange("H:\\", "cart-2"))

        self.assertEqual(states, ())
        self.assertEqual(service.currentState, first)
        self.assertTrue(service.shouldRunSteamAction(first))

    def testDetectsSecondCartridgeBlockedByActiveCartridge(self) -> None:
        service = CartridgeSessionService(FakeWatchService())
        service.handleInserted(deviceChange("G:\\", "cart-1"))

        self.assertTrue(service.isBlockedByActiveCartridge(deviceChange("H:\\", "cart-2")))


class FakeWatchService:
    def handleInsertedStates(self, change: DeviceChange) -> tuple[AppState, ...]:
        return (
            AppState(state=LauncherState.VALIDATING, rootPath=str(change.root)),
            AppState(
                state=LauncherState.READY,
                rootPath=str(change.root),
                cartridgeId=change.device.volumeSerialNumber,
                manifest=CartridgeManifest(1, change.device.volumeSerialNumber, f"{change.device.volumeSerialNumber} Game", "STEAM", "111", "SteamLibrary", "now"),
            ),
        )

    def handleRemoved(self, change: DeviceChange) -> AppState:
        return AppState(state=LauncherState.NOT_INSERTED, rootPath=str(change.root), message="waiting for cartridge")


def deviceChange(root: str, cartridgeId: str) -> DeviceChange:
    return DeviceChange(root=Path(root), device=DeviceInfo(root, cartridgeId, 100))


if __name__ == "__main__":
    unittest.main()

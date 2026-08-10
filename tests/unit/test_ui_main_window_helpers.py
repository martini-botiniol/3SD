from __future__ import annotations

import unittest

from cartridge_launcher.app.state import AppState
from cartridge_launcher.domain.errors import ErrorCode
from cartridge_launcher.domain.models import CartridgeManifest
from cartridge_launcher.domain.states import LauncherState
from cartridge_launcher.infrastructure.steam_store_search import SteamSearchResult
from cartridge_launcher.ui.main_window import LauncherWindow, activityTextFromState, steamSearchResultLabel
from cartridge_launcher.ui.status_messages import statusPopupKeyFromState, statusPopupMessageFromBlockedCartridge, statusPopupMessageFromState


class UiMainWindowHelperTests(unittest.TestCase):
    def testSteamSearchResultLabelShowsNameAndAppId(self) -> None:
        self.assertEqual(steamSearchResultLabel(SteamSearchResult("2531310", "Game A", "")), "Game A (2531310)")

    def testActivityTextFromReadyStateUsesGameName(self) -> None:
        text = activityTextFromState(AppState(state=LauncherState.READY, manifest=CartridgeManifest(1, "cart-1", "Game A", "STEAM", "111", "SteamLibrary", "now")))
        self.assertEqual(text, "Cartucho listo: Game A")

    def testActivityTextFromErrorStateUsesErrorCode(self) -> None:
        text = activityTextFromState(AppState(state=LauncherState.INVALID_CARTRIDGE, errorCode=ErrorCode.INVALID_SIGNATURE))
        self.assertEqual(text, "Error de cartucho: INVALID_SIGNATURE")

    def testStatusPopupKeyDeduplicatesSameState(self) -> None:
        state = AppState(state=LauncherState.INVALID_CARTRIDGE, rootPath="G:\\", errorCode=ErrorCode.INVALID_SIGNATURE, message="bad")

        self.assertEqual(statusPopupKeyFromState(state), statusPopupKeyFromState(state))

    def testValidatingPopupDismissesQuickly(self) -> None:
        message = statusPopupMessageFromState(AppState(state=LauncherState.VALIDATING, rootPath="G:\\"))

        self.assertEqual(message.dismissAfterMilliseconds, 1800)

    def testReadyPopupDismissesAfterShortDelay(self) -> None:
        message = statusPopupMessageFromState(
            AppState(
                state=LauncherState.READY,
                cartridgeId="cart-1",
                manifest=CartridgeManifest(1, "cart-1", "Game A", "STEAM", "111", "SteamLibrary", "now"),
            )
        )

        self.assertEqual(message.dismissAfterMilliseconds, 1200)

    def testRemovedCartridgePopupWaitsForUserAction(self) -> None:
        message = statusPopupMessageFromState(AppState(state=LauncherState.NOT_INSERTED, rootPath="G:\\"))

        self.assertEqual(message.title, "Cartucho expulsado")
        self.assertIn("El SSD cartucho fue expulsado.", message.message)
        self.assertIn("G:\\", message.message)
        self.assertIsNone(message.dismissAfterMilliseconds)

    def testBlockedCartridgePopupExplainsActiveCartridgeRule(self) -> None:
        message = statusPopupMessageFromBlockedCartridge("H:\\")

        self.assertEqual(message.title, "Cartucho en espera")
        self.assertIn("Ya hay un cartucho activo.", message.message)

    def testSelectedGameActionsRequireSelectedCartridgeToBeActive(self) -> None:
        window = object.__new__(LauncherWindow)
        window.selectedCartridgeId = "cart-1"
        window.currentState = AppState(state=LauncherState.READY, cartridgeId="cart-1")

        self.assertTrue(window._selectedCartridgeIsActive())

        window.currentState = AppState(state=LauncherState.NOT_INSERTED)

        self.assertFalse(window._selectedCartridgeIsActive())


if __name__ == "__main__":
    unittest.main()

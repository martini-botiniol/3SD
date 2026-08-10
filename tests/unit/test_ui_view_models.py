from __future__ import annotations

import unittest

from cartridge_launcher.app.state import AppState
from cartridge_launcher.domain.errors import ErrorCode
from cartridge_launcher.domain.models import CartridgeManifest, RegisteredCartridge
from cartridge_launcher.domain.states import LauncherState
from cartridge_launcher.ui.error_messages import friendlyErrorFromCode
from cartridge_launcher.ui.view_models import (
    cartridgeDisplayName,
    libraryAdvancedDetails,
    libraryCardsFromRegistry,
    libraryCardsWithState,
    libraryDetailFromRegistry,
    librarySelectionSummary,
    steamLibraryCoverUrl,
    viewModelFromState,
)


class UiViewModelTests(unittest.TestCase):
    def testNotInsertedViewModelDisablesActions(self) -> None:
        viewModel = viewModelFromState(AppState(state=LauncherState.NOT_INSERTED, message="waiting for cartridge"))
        self.assertEqual(viewModel.status, "Sin cartucho")
        self.assertNotIn("_", viewModel.status)
        self.assertFalse(viewModel.canRunSteamAction)

    def testReadyViewModelShowsGameAndEnablesActions(self) -> None:
        state = AppState(
            state=LauncherState.READY,
            rootPath="G:\\",
            manifest=CartridgeManifest(1, "cart-1", "The Last of Us Part II Remastered", "STEAM", "2531310", "SteamLibrary", "2026-07-23T00:00:00Z"),
        )
        viewModel = viewModelFromState(state)
        self.assertEqual(viewModel.title, "The Last of Us Part II Remastered")
        self.assertIn("2531310", viewModel.technicalDetail)
        self.assertTrue(viewModel.canRunSteamAction)

    def testErrorViewModelShowsFriendlyError(self) -> None:
        viewModel = viewModelFromState(AppState(state=LauncherState.INVALID_CARTRIDGE, errorCode=ErrorCode.INVALID_SIGNATURE))
        self.assertEqual(viewModel.title, "Cartucho modificado")
        self.assertFalse(viewModel.canRunSteamAction)

    def testOpeningViewModelShowsAutomaticLaunchState(self) -> None:
        state = AppState(
            state=LauncherState.OPENING,
            manifest=CartridgeManifest(1, "cart-1", "Game A", "STEAM", "111", "SteamLibrary", "now"),
            message="Steam esta abriendo Game A.",
        )

        viewModel = viewModelFromState(state)

        self.assertEqual(viewModel.subtitle, "Iniciando juego")
        self.assertFalse(viewModel.canRunSteamAction)

    def testLibraryCardsUseDisplayNameAndSteamCoverUrl(self) -> None:
        cards = libraryCardsFromRegistry((RegisteredCartridge("cart-1", "2531310", "ABC", 100, "Game A"),))
        self.assertEqual(cards[0].displayName, "Game A")
        self.assertEqual(cards[0].coverUrl, steamLibraryCoverUrl("2531310"))

    def testLibraryCardsHideAppIdWhenDisplayNameIsMissing(self) -> None:
        cards = libraryCardsFromRegistry((RegisteredCartridge("cart-1", "2531310", "ABC", 100),))
        self.assertEqual(cards[0].displayName, "Juego sin nombre")

    def testCartridgeDisplayNameTrimsSavedName(self) -> None:
        self.assertEqual(cartridgeDisplayName(RegisteredCartridge("cart-1", "1", "ABC", 100, "  Game A  ")), "Game A")

    def testLibraryDetailAndAdvancedDetails(self) -> None:
        detail = libraryDetailFromRegistry(RegisteredCartridge("cart-1", "2531310", "ABC", 1024**3, "Game A"))
        self.assertEqual(detail.capacityText, "1.0 GB")
        self.assertNotIn("2531310", librarySelectionSummary(detail))
        self.assertIn("2531310", libraryAdvancedDetails(detail))

    def testLibraryCardsWithStateMarksActiveCartridge(self) -> None:
        cards = libraryCardsWithState((RegisteredCartridge("cart-1", "111", "ABC", 100, "Game A"),), activeCartridgeId="cart-1")
        self.assertTrue(cards[0].isActive)
        self.assertEqual(cards[0].statusText, "Insertado")

    def testEveryErrorCodeHasFriendlyMessage(self) -> None:
        for errorCode in ErrorCode:
            friendly = friendlyErrorFromCode(errorCode)
            self.assertTrue(friendly.title)
            self.assertTrue(friendly.message)
            self.assertTrue(friendly.action)


if __name__ == "__main__":
    unittest.main()

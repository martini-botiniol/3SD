from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from cartridge_launcher.services.steam_integration import SteamIntegration


class SteamIntegrationTests(unittest.TestCase):
    def testAutoWaitsForInsertedLibraryBeforeInstalling(self) -> None:
        steamClient = DelayedInstallSteamClient()

        with patch("cartridge_launcher.services.steam_integration.time.sleep", lambda _seconds: None):
            action = SteamIntegration(steamClient).runAutoAction("111", Path("G:/SteamLibrary"))

        self.assertEqual(action, "open")
        self.assertEqual(steamClient.openedAppId, "111")
        self.assertIsNone(steamClient.installedAppId)
        self.assertGreaterEqual(steamClient.installChecks, 2)


class DelayedInstallSteamClient:
    def __init__(self):
        self.installChecks = 0
        self.openedAppId = None
        self.installedAppId = None

    def isGameInstalledInLibrary(self, _appId: str, _libraryRoot: Path) -> bool:
        self.installChecks += 1
        return self.installChecks >= 2

    def isGameInstalled(self, _appId: str) -> bool:
        return False

    def openGame(self, appId: str) -> None:
        self.openedAppId = appId

    def installGame(self, appId: str) -> None:
        self.installedAppId = appId


if __name__ == "__main__":
    unittest.main()

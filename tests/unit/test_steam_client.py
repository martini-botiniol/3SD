from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cartridge_launcher.infrastructure.steam_client import SteamClient, appInstallDirectory, appLastPlayed, appManifestPathInLibrary, isProcessRunningUnderDirectory


class SteamClientTests(unittest.TestCase):
    def testOpenGameUsesSteamExecutableWhenAvailable(self) -> None:
        with patch("cartridge_launcher.infrastructure.steam_client.steamExecutablePath", return_value=__import__("pathlib").Path("C:/Steam/steam.exe")), patch("subprocess.Popen") as popen:
            SteamClient().openGame("111")

        popen.assert_called_once_with(["C:\\Steam\\steam.exe", "-silent", "-applaunch", "111"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def testOpenGameFallsBackToSteamRunGameProtocol(self) -> None:
        with patch("cartridge_launcher.infrastructure.steam_client.steamExecutablePath", return_value=None), patch("cartridge_launcher.infrastructure.steam_client.os.startfile") as startfile:
            SteamClient().openGame("111")

        startfile.assert_called_once_with("steam://rungameid/111")

    def testAppLastPlayedReadsSteamManifest(self) -> None:
        with tempfile.TemporaryDirectory() as tempDir:
            steamRoot = Path(tempDir)
            steamapps = steamRoot / "steamapps"
            steamapps.mkdir()
            (steamapps / "appmanifest_111.acf").write_text('"AppState"\n{\n  "LastPlayed" "12345"\n}', encoding="utf-8")

            with patch("cartridge_launcher.infrastructure.steam_client.steamLibraryFolders", return_value=(steamRoot,)):
                self.assertEqual(appLastPlayed("111"), 12345)

    def testAppInstallDirectoryReadsSteamManifestInstallDir(self) -> None:
        with tempfile.TemporaryDirectory() as tempDir:
            steamRoot = Path(tempDir)
            steamapps = steamRoot / "steamapps"
            installDir = steamapps / "common" / "Game A"
            installDir.mkdir(parents=True)
            (steamapps / "appmanifest_111.acf").write_text('"AppState"\n{\n  "installdir" "Game A"\n}', encoding="utf-8")

            with patch("cartridge_launcher.infrastructure.steam_client.steamLibraryFolders", return_value=(steamRoot,)):
                self.assertEqual(appInstallDirectory("111"), installDir)

    def testAppManifestPathInLibraryFindsInsertedSsdLibraryManifest(self) -> None:
        with tempfile.TemporaryDirectory() as tempDir:
            libraryRoot = Path(tempDir) / "SteamLibrary"
            steamapps = libraryRoot / "steamapps"
            steamapps.mkdir(parents=True)
            manifestPath = steamapps / "appmanifest_111.acf"
            manifestPath.write_text('"AppState" {}', encoding="utf-8")

            self.assertEqual(appManifestPathInLibrary("111", libraryRoot), manifestPath)

    def testProcessDetectionUsesExecutablePathUnderInstallDirectory(self) -> None:
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="1234\n", stderr="")
        with patch("cartridge_launcher.infrastructure.steam_client.os.name", "nt"), patch("subprocess.run", return_value=completed) as run:
            self.assertTrue(isProcessRunningUnderDirectory(Path("C:/Steam/steamapps/common/Game A")))

        self.assertIn("Win32_Process", " ".join(run.call_args.args[0]))


if __name__ == "__main__":
    unittest.main()

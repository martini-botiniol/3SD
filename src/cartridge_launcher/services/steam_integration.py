from __future__ import annotations

from pathlib import Path
import time


class SteamIntegration:
    def __init__(self, steamClient):
        self.steamClient = steamClient

    def openGame(self, appId: str) -> None:
        self.steamClient.openGame(appId)

    def installGame(self, appId: str) -> None:
        self.steamClient.installGame(appId)

    def runAutoAction(self, appId: str, libraryRoot: Path | None = None) -> str:
        if self.waitForGameInstalled(appId, libraryRoot):
            self.openGame(appId)
            return "open"
        self.installGame(appId)
        return "install"

    def willOpenGame(self, appId: str) -> bool:
        return self.steamClient.isGameInstalled(appId)

    def waitForGameLaunch(self, appId: str, startedAt: float) -> bool:
        return self.steamClient.waitForGameLaunch(appId, startedAt)

    def waitForGameInstalled(self, appId: str, libraryRoot: Path | None = None, timeoutSeconds: float = 8.0, intervalSeconds: float = 0.5) -> bool:
        deadline = time.time() + timeoutSeconds
        while True:
            if libraryRoot is not None and self.steamClient.isGameInstalledInLibrary(appId, libraryRoot):
                return True
            if libraryRoot is None and self.steamClient.isGameInstalled(appId):
                return True
            if time.time() >= deadline:
                return False
            time.sleep(intervalSeconds)

from __future__ import annotations

import os
import re
import subprocess
import time
import webbrowser
from pathlib import Path


class SteamClient:
    def openGame(self, appId: str) -> None:
        steamPath = steamExecutablePath()
        if steamPath is not None:
            subprocess.Popen([str(steamPath), "-silent", "-applaunch", appId], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        openSteamUrl(f"steam://rungameid/{appId}")

    def installGame(self, appId: str) -> None:
        openSteamUrl(f"steam://install/{appId}")

    def isGameInstalled(self, appId: str) -> bool:
        return appManifestPath(appId) is not None

    def isGameInstalledInLibrary(self, appId: str, libraryRoot: Path) -> bool:
        return appManifestPathInLibrary(appId, libraryRoot) is not None

    def waitForGameLaunch(self, appId: str, startedAt: float, timeoutSeconds: float = 25.0) -> bool:
        deadline = time.time() + timeoutSeconds
        expectedLastPlayed = max(0, int(startedAt) - 2)
        installDirectory = appInstallDirectory(appId)
        while time.time() < deadline:
            if installDirectory is not None and isProcessRunningUnderDirectory(installDirectory):
                return True
            lastPlayed = appLastPlayed(appId)
            if lastPlayed is not None and lastPlayed >= expectedLastPlayed:
                return True
            time.sleep(0.5)
        return False


def appManifestPath(appId: str) -> Path | None:
    for library in steamLibraryFolders():
        manifestPath = appManifestPathInLibrary(appId, library)
        if manifestPath is not None:
            return manifestPath
    return None


def appManifestPathInLibrary(appId: str, libraryRoot: Path) -> Path | None:
    manifestPath = libraryRoot / "steamapps" / f"appmanifest_{appId}.acf"
    return manifestPath if manifestPath.is_file() else None


def appLastPlayed(appId: str) -> int | None:
    manifestText = appManifestText(appId)
    if manifestText is None:
        return None
    match = re.search(r'"LastPlayed"\s+"(\d+)"', manifestText)
    if match is None:
        return None
    return int(match.group(1))


def appInstallDirectory(appId: str) -> Path | None:
    manifestPath = appManifestPath(appId)
    if manifestPath is None:
        return None
    manifestText = appManifestText(appId)
    if manifestText is None:
        return None
    match = re.search(r'"installdir"\s+"([^"]+)"', manifestText, flags=re.IGNORECASE)
    if match is None:
        return None
    installDirectory = manifestPath.parent / "common" / match.group(1)
    return installDirectory if installDirectory.exists() else None


def appManifestText(appId: str) -> str | None:
    manifestPath = appManifestPath(appId)
    if manifestPath is None:
        return None
    try:
        return manifestPath.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None


def isProcessRunningUnderDirectory(directory: Path) -> bool:
    if os.name != "nt":
        return False
    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                (
                    "& { param([string]$Directory) "
                    "$prefix = [System.IO.Path]::GetFullPath($Directory).TrimEnd('\\') + '\\'; "
                    "Get-CimInstance Win32_Process | "
                    "Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase) } | "
                    "Select-Object -First 1 -ExpandProperty ProcessId }"
                ),
                str(directory),
            ],
            capture_output=True,
            text=True,
            timeout=3,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and result.stdout.strip() != ""


def steamLibraryFolders() -> tuple[Path, ...]:
    candidates = [
        Path("C:/Program Files (x86)/Steam"),
        Path("C:/Program Files/Steam"),
    ]
    return tuple(path for path in candidates if path.exists())


def steamExecutablePath() -> Path | None:
    for library in steamLibraryFolders():
        candidate = library / "steam.exe"
        if candidate.is_file():
            return candidate
    return None


def openPath(path: Path) -> None:
    subprocess.Popen(["explorer.exe", str(path)])


def openSteamUrl(url: str) -> None:
    try:
        os.startfile(url)
    except (AttributeError, OSError):
        webbrowser.open(url)

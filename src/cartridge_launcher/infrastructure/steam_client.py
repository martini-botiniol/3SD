from __future__ import annotations

import os
import re
import subprocess
import tempfile
import time
import webbrowser
from pathlib import Path
from cartridge_launcher.domain.errors import CartridgeError, ErrorCode
from cartridge_launcher.infrastructure.steam_vdf import parseVdf


class SteamClient:
    def ensureAvailable(self) -> None:
        if steamExecutablePath() is None:
            raise CartridgeError(ErrorCode.STEAM_NOT_FOUND, "Instala Steam para usar el cartucho.")

    def isLibraryRegistered(self, libraryRoot: Path) -> bool:
        return any(path.resolve() == libraryRoot.resolve() for path in steamLibraryFolders())

    def ensureLibraryWritable(self, libraryRoot: Path) -> None:
        steamapps = libraryRoot / "steamapps"
        try:
            # Older cartridges only created SteamLibrary. Prepare Steam's child
            # directory without recreating a missing/disconnected library root.
            steamapps.mkdir(exist_ok=True)
            # Probe the actual Steam directory, not the cartridge metadata folder.
            # A unique temporary file never overwrites game or Steam files.
            with tempfile.TemporaryFile(prefix=".3sd-write-", dir=steamapps) as probe:
                probe.write(b"3SD")
                probe.flush()
                os.fsync(probe.fileno())
        except OSError as exc:
            raise CartridgeError(
                ErrorCode.LIBRARY_NOT_WRITABLE,
                f"No se puede escribir en {steamapps}. Revisa si el SSD esta en solo lectura, "
                "los permisos de escritura y el espacio disponible. "
                "No se envio la solicitud a Steam.",
            ) from exc

    def installationState(self, appId: str, libraryRoot: Path) -> str:
        path = appManifestPathInLibrary(appId, libraryRoot)
        if path is None:
            return "missing"
        try:
            state = parseVdf(path.read_text(encoding="utf-8"))["AppState"]
            flags = int(state.get("StateFlags", "0"))
            installed = safeInstallDirectory(path, state.get("installdir", ""))
            return "installed" if flags == 4 and installed is not None else "partial"
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return "partial"

    def openGame(self, appId: str) -> None:
        steamPath = steamExecutablePath()
        if steamPath is not None:
            subprocess.Popen([str(steamPath), "-silent", "-applaunch", appId], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        openSteamUrl(f"steam://rungameid/{appId}")

    def installGame(self, appId: str) -> None:
        openSteamUrl(f"steam://install/{appId}")

    def isGameInstalled(self, appId: str) -> bool:
        return any(self.isGameInstalledInLibrary(appId, root) for root in steamLibraryFolders())

    def isGameInstalledInLibrary(self, appId: str, libraryRoot: Path) -> bool:
        return self.installationState(appId, libraryRoot) == "installed"

    def waitForGameLaunch(self, appId: str, startedAt: float, timeoutSeconds: float = 25.0, libraryRoot: Path | None = None, cancelled=lambda: False) -> bool:
        deadline = time.monotonic() + timeoutSeconds
        expectedLastPlayed = max(0, int(startedAt) - 2)
        installDirectory = appInstallDirectory(appId, libraryRoot)
        while time.monotonic() < deadline and not cancelled():
            if installDirectory is not None and isProcessRunningUnderDirectory(installDirectory):
                return True
            lastPlayed = appLastPlayed(appId, libraryRoot)
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


def appLastPlayed(appId: str, libraryRoot: Path | None = None) -> int | None:
    manifestText = appManifestText(appId, libraryRoot)
    if manifestText is None:
        return None
    match = re.search(r'"LastPlayed"\s+"(\d+)"', manifestText)
    if match is None:
        return None
    return int(match.group(1))


def appInstallDirectory(appId: str, libraryRoot: Path | None = None) -> Path | None:
    manifestPath = appManifestPathInLibrary(appId, libraryRoot) if libraryRoot else appManifestPath(appId)
    if manifestPath is None:
        return None
    manifestText = appManifestText(appId, libraryRoot)
    if manifestText is None:
        return None
    match = re.search(r'"installdir"\s+"([^"]+)"', manifestText, flags=re.IGNORECASE)
    if match is None:
        return None
    return safeInstallDirectory(manifestPath, match.group(1))


def safeInstallDirectory(manifestPath: Path, name: str) -> Path | None:
    if not name or Path(name).is_absolute():
        return None
    common = (manifestPath.parent / "common").resolve()
    directory = (common / name).resolve()
    return directory if directory != common and directory.is_relative_to(common) and directory.is_dir() else None


def appManifestText(appId: str, libraryRoot: Path | None = None) -> str | None:
    manifestPath = appManifestPathInLibrary(appId, libraryRoot) if libraryRoot else appManifestPath(appId)
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


def steamInstallRoots() -> tuple[Path, ...]:
    candidates = [
        Path("C:/Program Files (x86)/Steam"),
        Path("C:/Program Files/Steam"),
    ]
    if os.name == "nt":
        import winreg
        for hive, key, value in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                                 (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
                                 (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath")):
            try:
                with winreg.OpenKey(hive, key) as handle:
                    candidates.insert(0, Path(winreg.QueryValueEx(handle, value)[0]))
            except OSError:
                pass
    return tuple(dict.fromkeys(path for path in candidates if path.is_dir()))


def steamLibraryFolders() -> tuple[Path, ...]:
    roots = steamInstallRoots()
    libraries = list(roots)
    for root in roots:
        try:
            values = parseVdf((root / "steamapps" / "libraryfolders.vdf").read_text(encoding="utf-8"))
            folders = values.get("libraryfolders", values.get("LibraryFolders", {}))
            for key, item in folders.items():
                if key.isdigit():
                    location = item.get("path") if isinstance(item, dict) else item
                    if isinstance(location, str) and Path(location).is_absolute():
                        libraries.append(Path(location))
        except (OSError, ValueError, AttributeError):
            continue
    return tuple(dict.fromkeys(libraries))


def steamExecutablePath() -> Path | None:
    for library in steamInstallRoots():
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

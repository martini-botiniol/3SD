from __future__ import annotations

import ctypes
import subprocess
from pathlib import Path

from cartridge_launcher.domain.models import DeviceInfo


DRIVE_REMOTE = 4


class WindowsDeviceScanner:
    def scan(self) -> dict[str, DeviceInfo]:
        devices: dict[str, DeviceInfo] = {}
        for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
            root = Path(f"{letter}:\\")
            if root.exists() and isSupportedLocalDrive(str(root)):
                devices[str(root)] = DeviceInfo(
                    rootPath=str(root),
                    volumeSerialNumber=volumeSerialNumber(str(root)),
                    capacityBytes=volumeCapacityBytes(str(root)),
                )
        return devices

    def findDeviceByRoot(self, root: Path) -> DeviceInfo | None:
        normalized = str(root)
        return self.scan().get(normalized)


def isSupportedLocalDrive(rootPath: str) -> bool:
    driveType = driveTypeForRoot(rootPath)
    return driveType != DRIVE_REMOTE


def driveTypeForRoot(rootPath: str) -> int:
    rootPath = normalizedRootPath(rootPath)
    try:
        return int(ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(rootPath)))
    except (AttributeError, OSError):
        return 0


def volumeCapacityBytes(rootPath: str) -> int:
    rootPath = normalizedRootPath(rootPath)
    freeBytesAvailable = ctypes.c_ulonglong(0)
    totalNumberOfBytes = ctypes.c_ulonglong(0)
    totalNumberOfFreeBytes = ctypes.c_ulonglong(0)
    try:
        success = ctypes.windll.kernel32.GetDiskFreeSpaceExW(
            ctypes.c_wchar_p(rootPath),
            ctypes.byref(freeBytesAvailable),
            ctypes.byref(totalNumberOfBytes),
            ctypes.byref(totalNumberOfFreeBytes),
        )
    except (AttributeError, OSError):
        return 0
    if not success:
        return 0
    return int(totalNumberOfBytes.value)


def volumeSerialNumber(rootPath: str) -> str:
    rootPath = normalizedRootPath(rootPath)
    volumeSerial = ctypes.c_ulong(0)
    maxComponentLength = ctypes.c_ulong(0)
    fileSystemFlags = ctypes.c_ulong(0)
    volumeName = ctypes.create_unicode_buffer(261)
    fileSystemName = ctypes.create_unicode_buffer(261)
    try:
        success = ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(rootPath),
            volumeName,
            len(volumeName),
            ctypes.byref(volumeSerial),
            ctypes.byref(maxComponentLength),
            ctypes.byref(fileSystemFlags),
            fileSystemName,
            len(fileSystemName),
        )
    except (AttributeError, OSError):
        success = 0

    if not success:
        return powershellVolumeSerialNumber(rootPath) or "Desconocido"
    return f"{volumeSerial.value:08X}"


def normalizedRootPath(rootPath: str) -> str:
    drive = Path(rootPath).drive
    if drive:
        return f"{drive}\\"
    return rootPath if rootPath.endswith("\\") else f"{rootPath}\\"


def powershellVolumeSerialNumber(rootPath: str) -> str:
    driveLetter = normalizedRootPath(rootPath).rstrip("\\").rstrip(":")
    if not driveLetter:
        return ""

    command = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        f"(Get-CimInstance Win32_LogicalDisk -Filter \"DeviceID='{driveLetter}:'\" -ErrorAction Stop).VolumeSerialNumber",
    ]
    try:
        output = subprocess.check_output(
            command,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
    except (subprocess.SubprocessError, OSError):
        return ""

    return output.strip()

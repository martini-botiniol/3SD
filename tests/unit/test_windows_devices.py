from __future__ import annotations

import unittest
from unittest.mock import patch

from cartridge_launcher.infrastructure import windows_devices


class FakeKernel32:
    def GetDriveTypeW(self, _rootPath):
        return 3

    def GetDiskFreeSpaceExW(self, _rootPath, _freeBytesAvailable, totalNumberOfBytes, _totalNumberOfFreeBytes):
        totalNumberOfBytes._obj.value = 512 * 1024**3
        return 1

    def GetVolumeInformationW(self, _rootPath, _volumeName, _volumeNameSize, volumeSerial, _maxComponentLength, _fileSystemFlags, _fileSystemName, _fileSystemNameSize):
        volumeSerial._obj.value = 0xABC123
        return 1


class FailingKernel32:
    def GetDriveTypeW(self, _rootPath):
        return 0

    def GetVolumeInformationW(self, *_args):
        return 0


class WindowsDeviceTests(unittest.TestCase):
    def testReadsCapacityAndVolumeSerialFromWindows(self) -> None:
        with patch.object(windows_devices.ctypes, "windll", type("FakeWindll", (), {"kernel32": FakeKernel32()})()):
            self.assertEqual(windows_devices.volumeCapacityBytes("G:\\"), 512 * 1024**3)
            self.assertEqual(windows_devices.volumeSerialNumber("G:\\"), "00ABC123")

    def testSerialFallsBackToPowershellBeforeUnknown(self) -> None:
        with patch.object(windows_devices.ctypes, "windll", type("FakeWindll", (), {"kernel32": FailingKernel32()})()), patch(
            "cartridge_launcher.infrastructure.windows_devices.powershellVolumeSerialNumber",
            return_value="DEADBEEF",
        ):
            self.assertEqual(windows_devices.volumeSerialNumber("G:\\"), "DEADBEEF")

    def testSerialDoesNotFallBackToDriveLetter(self) -> None:
        with patch.object(windows_devices.ctypes, "windll", type("FakeWindll", (), {"kernel32": FailingKernel32()})()), patch(
            "cartridge_launcher.infrastructure.windows_devices.powershellVolumeSerialNumber",
            return_value="",
        ):
            self.assertEqual(windows_devices.volumeSerialNumber("G:\\"), "Desconocido")

    def testRemoteDriveIsNotSupported(self) -> None:
        with patch("cartridge_launcher.infrastructure.windows_devices.driveTypeForRoot", return_value=windows_devices.DRIVE_REMOTE):
            self.assertFalse(windows_devices.isSupportedLocalDrive("Z:\\"))

    def testScannerKeepsSupportedLocalDrive(self) -> None:
        with patch("pathlib.Path.exists", return_value=True), patch("cartridge_launcher.infrastructure.windows_devices.isSupportedLocalDrive", side_effect=lambda root: root == "G:\\"), patch(
            "cartridge_launcher.infrastructure.windows_devices.volumeSerialNumber",
            return_value="ABC",
        ), patch("cartridge_launcher.infrastructure.windows_devices.volumeCapacityBytes", return_value=100):
            devices = windows_devices.WindowsDeviceScanner().scan()

        self.assertEqual(tuple(devices), ("G:\\",))


if __name__ == "__main__":
    unittest.main()

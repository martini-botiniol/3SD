from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cartridge_launcher.domain.errors import CartridgeError, ErrorCode
from cartridge_launcher.domain.models import DeviceInfo
from cartridge_launcher.services.cartridge_creation_service import CartridgeCreationService
from cartridge_launcher.services.local_registry import LocalRegistry
from cartridge_launcher.services.security_service import SecurityService


class FakeDeviceScanner:
    def __init__(self, devices: dict[str, DeviceInfo]):
        self.devices = devices

    def findDeviceByRoot(self, root: Path) -> DeviceInfo | None:
        return self.devices.get(str(root))


class CartridgeCreationServiceTests(unittest.TestCase):
    def testCreateBlocksExistingCartridgeMetadata(self) -> None:
        with TemporaryDirectory() as directory:
            tmpPath = Path(directory)
            root = tmpPath / "ssd"
            metadataDir = root / ".cartridge"
            metadataDir.mkdir(parents=True)
            (metadataDir / "manifest.json").write_text("{}", encoding="utf-8")
            device = DeviceInfo(str(root), "ABC", 100)
            service = CartridgeCreationService(
                SecurityService(tmpPath / "secret"),
                LocalRegistry(tmpPath / "registry.json"),
                FakeDeviceScanner({str(root): device}),
            )

            with self.assertRaises(CartridgeError) as error:
                service.create(root, "Game A", "111")

            self.assertEqual(error.exception.code, ErrorCode.CARTRIDGE_ALREADY_EXISTS)


if __name__ == "__main__":
    unittest.main()

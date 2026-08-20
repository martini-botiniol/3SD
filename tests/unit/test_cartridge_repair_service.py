from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cartridge_launcher.domain.models import DeviceInfo
from cartridge_launcher.services.cartridge_repair_service import CartridgeRepairService
from cartridge_launcher.services.local_registry import LocalRegistry
from cartridge_launcher.services.security_service import SecurityService


class FakeDeviceScanner:
    def __init__(self, devices: dict[str, DeviceInfo]):
        self.devices = devices

    def findDeviceByRoot(self, root: Path) -> DeviceInfo | None:
        return self.devices.get(str(root))


class CartridgeRepairServiceTests(unittest.TestCase):
    def testRepairRegeneratesInvalidSignatureAndPreservesCartridgeId(self) -> None:
        with TemporaryDirectory() as directory:
            tmpPath = Path(directory)
            root = tmpPath / "ssd"
            metadata = root / ".cartridge"
            metadata.mkdir(parents=True)
            (root / "SteamLibrary").mkdir()
            manifest = {
                "schemaVersion": 1,
                "cartridgeId": "cart-1",
                "displayName": "Old Game",
                "platform": "STEAM",
                "appId": "111",
                "libraryPath": "SteamLibrary",
                "createdAt": "now",
            }
            (metadata / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (metadata / "signature.sig").write_text("bad-signature", encoding="utf-8")
            service = repairService(tmpPath, root)

            repaired = service.repair(root, "New Game", "222")

            self.assertEqual(repaired.cartridgeId, "cart-1")
            self.assertEqual(repaired.displayName, "New Game")
            self.assertEqual(repaired.appId, "222")
            self.assertTrue(service.security.verify((metadata / "manifest.json").read_bytes(), (metadata / "signature.sig").read_text(encoding="utf-8")))

    def testRepairRebuildsBrokenManifestWithNewCartridgeId(self) -> None:
        with TemporaryDirectory() as directory:
            tmpPath = Path(directory)
            root = tmpPath / "ssd"
            metadata = root / ".cartridge"
            metadata.mkdir(parents=True)
            (metadata / "manifest.json").write_text("{", encoding="utf-8")
            service = repairService(tmpPath, root)

            repaired = service.repair(root, "Game A", "111")

            self.assertNotEqual(repaired.cartridgeId, "")
            self.assertEqual(repaired.displayName, "Game A")
            self.assertTrue((root / "SteamLibrary").is_dir())

    def testRepairRemovesForbiddenMetadataFiles(self) -> None:
        with TemporaryDirectory() as directory:
            tmpPath = Path(directory)
            root = tmpPath / "ssd"
            forbidden = root / ".cartridge" / "fix.ps1"
            forbidden.parent.mkdir(parents=True)
            forbidden.write_text("Write-Host no", encoding="utf-8")
            service = repairService(tmpPath, root)

            service.repair(root, "Game A", "111")

            self.assertFalse(forbidden.exists())


def repairService(tmpPath: Path, root: Path) -> CartridgeRepairService:
    device = DeviceInfo(str(root), "ABC", 100)
    return CartridgeRepairService(
        SecurityService(tmpPath / "secret"),
        LocalRegistry(tmpPath / "registry.json"),
        FakeDeviceScanner({str(root): device}),
    )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cartridge_launcher.domain.errors import CartridgeError, ErrorCode
from cartridge_launcher.domain.models import DeviceInfo
from cartridge_launcher.services.cartridge_validator import CartridgeValidator
from cartridge_launcher.services.local_registry import LocalRegistry


class CartridgeValidatorTests(unittest.TestCase):
    def testAcceptsValidCartridgeMetadata(self) -> None:
        with TemporaryDirectory() as directory:
            root = preparedCartridge(Path(directory))

            manifest = CartridgeValidator(FakeSecurity(), LocalRegistry(root / "registry.json")).validate(root, DeviceInfo(str(root), "ABC", 100))

            self.assertEqual(manifest.appId, "111")

    def testRejectsExecutableMetadataFiles(self) -> None:
        with TemporaryDirectory() as directory:
            root = preparedCartridge(Path(directory))
            (root / ".cartridge" / "repair.PS1").write_text("Write-Host nope", encoding="utf-8")

            with self.assertRaises(CartridgeError) as error:
                CartridgeValidator(FakeSecurity(), LocalRegistry(root / "registry.json")).validate(root, DeviceInfo(str(root), "ABC", 100))

            self.assertEqual(error.exception.code, ErrorCode.INVALID_STRUCTURE)


class FakeSecurity:
    def verify(self, _rawManifest: bytes, _signature: str) -> bool:
        return True


def preparedCartridge(root: Path) -> Path:
    metadata = root / ".cartridge"
    metadata.mkdir()
    (root / "SteamLibrary").mkdir()
    manifest = {
        "schemaVersion": 1,
        "cartridgeId": "cart-1",
        "displayName": "Game A",
        "platform": "STEAM",
        "appId": "111",
        "libraryPath": "SteamLibrary",
        "createdAt": "now",
    }
    (metadata / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (metadata / "signature.sig").write_text("signature", encoding="utf-8")
    return root


if __name__ == "__main__":
    unittest.main()

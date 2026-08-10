from __future__ import annotations

import unittest

from cartridge_launcher.domain.errors import CartridgeError, ErrorCode
from cartridge_launcher.domain.manifest import manifestFromDict


class ManifestValidationTests(unittest.TestCase):
    def testRejectsInvalidAppId(self) -> None:
        with self.assertRaises(CartridgeError) as error:
            manifestFromDict(validManifest(appId="abc"))
        self.assertEqual(error.exception.code, ErrorCode.INVALID_APP_ID)

    def testRejectsZeroAppId(self) -> None:
        with self.assertRaises(CartridgeError) as error:
            manifestFromDict(validManifest(appId="0"))
        self.assertEqual(error.exception.code, ErrorCode.INVALID_APP_ID)

    def testRejectsAppIdAboveUnsigned32BitRange(self) -> None:
        with self.assertRaises(CartridgeError) as error:
            manifestFromDict(validManifest(appId="4294967296"))
        self.assertEqual(error.exception.code, ErrorCode.INVALID_APP_ID)

    def testRejectsLibraryPathOtherThanSteamLibrary(self) -> None:
        with self.assertRaises(CartridgeError) as error:
            manifestFromDict(validManifest(libraryPath="OtherLibrary"))
        self.assertEqual(error.exception.code, ErrorCode.INVALID_LIBRARY_PATH)


def validManifest(appId: str = "111", libraryPath: str = "SteamLibrary"):
    return {"schemaVersion": 1, "cartridgeId": "cart", "displayName": "Game", "platform": "STEAM", "appId": appId, "libraryPath": libraryPath, "createdAt": "now"}


if __name__ == "__main__":
    unittest.main()

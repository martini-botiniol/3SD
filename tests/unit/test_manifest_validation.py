from __future__ import annotations

import unittest

from cartridge_launcher.domain.errors import CartridgeError, ErrorCode
from cartridge_launcher.domain.manifest import manifestFromDict


class ManifestValidationTests(unittest.TestCase):
    def testRejectsInvalidIdentityPlatformDateAndTypes(self) -> None:
        for key, value in (("cartridgeId", "not-a-uuid"), ("displayName", " "),
                           ("platform", "OTHER"), ("createdAt", "2026-09-08"),
                           ("schemaVersion", True), ("schemaVersion", 3), ("appId", True)):
            with self.subTest(key=key, value=value), self.assertRaises(CartridgeError):
                manifestFromDict({**validManifest(), key: value})

    def testDuplicateKeysAndNonFiniteJsonAreRejected(self) -> None:
        from cartridge_launcher.domain.manifest import payloadFromBytes
        for raw in (b'{"schemaVersion":1,"schemaVersion":2}', b'{"extra":NaN}'):
            with self.assertRaises(CartridgeError):
                payloadFromBytes(raw)

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
    return {"schemaVersion": 1, "cartridgeId": "00000000-0000-4000-8000-000000000001", "displayName": "Game", "platform": "STEAM", "appId": appId, "libraryPath": libraryPath, "createdAt": "2026-09-08T00:00:00Z"}


if __name__ == "__main__":
    unittest.main()

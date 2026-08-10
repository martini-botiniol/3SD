from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cartridge_launcher.domain.models import RegisteredCartridge
from cartridge_launcher.services.local_registry import LocalRegistry


class LocalRegistryTests(unittest.TestCase):
    def testDeleteRemovesRegisteredCartridge(self) -> None:
        with TemporaryDirectory() as directory:
            registry = LocalRegistry(Path(directory) / "registry.json")
            registry.upsert(RegisteredCartridge("cart-1", "111", "ABC", 100, "Game A"))
            registry.upsert(RegisteredCartridge("cart-2", "222", "DEF", 100, "Game B"))

            self.assertTrue(registry.delete("cart-1"))

            self.assertIsNone(registry.get("cart-1"))
            self.assertIsNotNone(registry.get("cart-2"))

    def testDeleteReturnsFalseWhenMissing(self) -> None:
        with TemporaryDirectory() as directory:
            registry = LocalRegistry(Path(directory) / "registry.json")

            self.assertFalse(registry.delete("missing"))

    def testInvalidJsonLoadsAsEmptyRegistry(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            path.write_text("{", encoding="utf-8")

            self.assertEqual(LocalRegistry(path).all(), ())

    def testWriteReplacesTemporaryFileAtomically(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            registry = LocalRegistry(path)

            registry.upsert(RegisteredCartridge("cart-1", "111", "ABC", 100, "Game A"))

            self.assertTrue(path.is_file())
            self.assertFalse(path.with_suffix(".json.tmp").exists())


if __name__ == "__main__":
    unittest.main()

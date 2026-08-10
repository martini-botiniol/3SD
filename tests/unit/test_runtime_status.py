from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest

from cartridge_launcher.services.runtime_status import RuntimeStatus, RuntimeStatusStore


class RuntimeStatusTests(unittest.TestCase):
    def testRuntimeStatusRoundTrips(self) -> None:
        with TemporaryDirectory() as directory:
            store = RuntimeStatusStore(Path(directory) / "runtime.json")
            status = RuntimeStatus("cart-1", "111", "Game A", "open", "accepted", time.time())

            store.write(status)

            self.assertEqual(store.read(), status)


if __name__ == "__main__":
    unittest.main()

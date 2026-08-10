from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from cartridge_launcher.ui.cover_cache import downloadCover


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return b"image-bytes"


class CoverCacheTests(unittest.TestCase):
    def testDownloadCoverWritesAtomically(self) -> None:
        with TemporaryDirectory() as directory, patch("cartridge_launcher.ui.cover_cache.urlopen", return_value=FakeResponse()):
            imagePath = Path(directory) / "cover.jpg"

            self.assertTrue(downloadCover("https://example.test/cover.jpg", imagePath))

            self.assertEqual(imagePath.read_bytes(), b"image-bytes")
            self.assertFalse(imagePath.with_suffix(".tmp").exists())

    def testDownloadCoverRemovesTempFileOnFailure(self) -> None:
        with TemporaryDirectory() as directory, patch("cartridge_launcher.ui.cover_cache.urlopen", side_effect=OSError("offline")):
            imagePath = Path(directory) / "cover.jpg"

            self.assertFalse(downloadCover("https://example.test/cover.jpg", imagePath))

            self.assertFalse(imagePath.exists())
            self.assertFalse(imagePath.with_suffix(".tmp").exists())


if __name__ == "__main__":
    unittest.main()

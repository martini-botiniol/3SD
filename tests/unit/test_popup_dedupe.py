from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cartridge_launcher.ui.popup_dedupe import DEDUPLICATION_SECONDS, shouldShowPopupKey


class PopupDedupeTests(unittest.TestCase):
    def testSameKeyIsHiddenWithinDeduplicationWindow(self) -> None:
        with TemporaryDirectory() as directory:
            dataDirectory = Path(directory)

            self.assertTrue(shouldShowPopupKey("state:error:G", dataDirectory, now=10.0))
            self.assertFalse(shouldShowPopupKey("state:error:G", dataDirectory, now=12.0))

    def testSameKeyCanShowAgainAfterDeduplicationWindow(self) -> None:
        with TemporaryDirectory() as directory:
            dataDirectory = Path(directory)

            self.assertTrue(shouldShowPopupKey("state:error:G", dataDirectory, now=10.0))
            self.assertTrue(shouldShowPopupKey("state:error:G", dataDirectory, now=10.0 + DEDUPLICATION_SECONDS + 1.0))

    def testEmptyKeyAlwaysShows(self) -> None:
        with TemporaryDirectory() as directory:
            dataDirectory = Path(directory)

            self.assertTrue(shouldShowPopupKey("", dataDirectory, now=10.0))
            self.assertTrue(shouldShowPopupKey("", dataDirectory, now=10.0))


if __name__ == "__main__":
    unittest.main()

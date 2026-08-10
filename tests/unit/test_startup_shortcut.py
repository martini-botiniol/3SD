from __future__ import annotations

import unittest
from unittest.mock import patch

from cartridge_launcher.infrastructure.startup_shortcut import startupCommand


class StartupShortcutTests(unittest.TestCase):
    def testPackagedStartupCommandUsesTrayMode(self) -> None:
        with patch("sys.executable", "C:\\Users\\marti\\AppData\\Local\\Programs\\3SD\\3SD.exe"):
            self.assertEqual(startupCommand()[-3:], ["tray", "--steam-action", "open"])


if __name__ == "__main__":
    unittest.main()

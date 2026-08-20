from __future__ import annotations

import unittest
from unittest.mock import patch

from cartridge_launcher.app.main import defaultCommand, main, requiresSingleInstance


class AppMainTests(unittest.TestCase):
    def testSourceDefaultCommandOpensUi(self) -> None:
        self.assertEqual(defaultCommand(), "ui")

    def testPackagedExecutableDefaultCommandStartsTray(self) -> None:
        with patch("sys.executable", "C:\\Program Files\\3SD\\3SD.exe"):
            self.assertEqual(defaultCommand(), "tray")

    def testTrayRequiresSingleInstance(self) -> None:
        self.assertTrue(requiresSingleInstance("tray"))
        self.assertTrue(requiresSingleInstance("ui"))
        self.assertFalse(requiresSingleInstance("create"))

    def testUiLaunchedFromTrayDoesNotRequireSingleInstance(self) -> None:
        args = type("Args", (), {"from_tray": True})()

        self.assertFalse(requiresSingleInstance("ui", args))

    def testSecondSingleInstanceSignalsExistingProcess(self) -> None:
        with patch("cartridge_launcher.app.main.SingleInstanceLock") as lockClass, patch("cartridge_launcher.app.main.SingleInstanceSignal") as signalClass:
            lockClass.return_value.acquire.return_value = False

            result = main(["tray"])

        self.assertEqual(result, 0)
        signalClass.return_value.signalExisting.assert_called_once()

    def testUiFromTrayOpensWithoutTakingSingleInstanceLock(self) -> None:
        with patch("cartridge_launcher.app.main.SingleInstanceLock") as lockClass, patch("cartridge_launcher.app.main.services") as services, patch("cartridge_launcher.app.main.runLauncherUi") as runLauncherUi:
            services.return_value = ("security", "registry", "scanner", "logger")

            result = main(["ui", "--from-tray"])

        self.assertEqual(result, 0)
        lockClass.assert_not_called()
        runLauncherUi.assert_called_once_with("security", "registry", "scanner", "logger", suppressStatePopups=True)

    def testRepairCommandRepairsCartridge(self) -> None:
        with patch("cartridge_launcher.app.main.services") as services, patch("cartridge_launcher.app.main.CartridgeRepairService") as repairService:
            services.return_value = ("security", "registry", "scanner", "logger")
            repairService.return_value.repair.return_value.displayName = "Game A"

            result = main(["repair", "--root", "G:\\", "--display-name", "Game A", "--app-id", "111"])

        self.assertEqual(result, 0)
        repairService.return_value.repair.assert_called_once()


if __name__ == "__main__":
    unittest.main()

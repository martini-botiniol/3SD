from __future__ import annotations

import unittest
from unittest.mock import patch

from PIL import Image

from cartridge_launcher.app.state import AppState
from cartridge_launcher.domain.models import CartridgeManifest
from cartridge_launcher.domain.states import LauncherState
from cartridge_launcher.ui.tray_app import TrayApp, createTrayIcon, killPackagedProcesses, packagedKillCommand


class TrayAppTests(unittest.TestCase):
    def testCreateTrayIconReturnsPillowImage(self) -> None:
        self.assertIsInstance(createTrayIcon(), Image.Image)

    def testPackagedKillUsesDetachedProcess(self) -> None:
        with patch("cartridge_launcher.ui.tray_app.isPackagedExecutable", return_value=True), patch("subprocess.Popen") as popen:
            killPackagedProcesses()

        popen.assert_called_once()
        self.assertEqual(popen.call_args.args[0], packagedKillCommand())

    def testUiCommandMarksWindowAsLaunchedFromTray(self) -> None:
        app = object.__new__(TrayApp)

        command = app._uiCommand()

        self.assertEqual(command[-2:], ["ui", "--from-tray"])

    def testAutoSteamActionQueuesOpeningGameUntilSteamAcceptsCommand(self) -> None:
        app = object.__new__(TrayApp)
        app.steamAction = "auto"
        app.statusMessages = __import__("queue").Queue()
        app.queuedStatusPopupKeys = set()
        app.displayedStatusPopupKeys = set()
        app.steamActionPopupMinimumSeconds = 0
        app.sessionService = FakeSessionService()
        app.steamIntegration = FakeSteamIntegration("open")
        app.runtimeStatusStore = FakeRuntimeStatusStore()
        app.logger = type("Logger", (), {"warning": lambda *_args: None})()
        state = AppState(
            state=LauncherState.READY,
            cartridgeId="cart-1",
            manifest=CartridgeManifest(1, "cart-1", "Game A", "STEAM", "111", "SteamLibrary", "now"),
        )

        app._maybeRunSteamAction(state)

        message = app.statusMessages.get_nowait()
        dismiss = app.statusMessages.get_nowait()
        self.assertEqual(message.title, "Abriendo juego")
        self.assertEqual(dismiss.key, "popup:dismiss")
        self.assertTrue(app.statusMessages.empty())
        self.assertEqual(app.steamIntegration.openedAppId, "111")
        self.assertEqual(app.steamIntegration.waitedAppId, "111")

    def testAutoSteamFlowDoesNotQueueValidationPopups(self) -> None:
        app = object.__new__(TrayApp)
        app.steamAction = "auto"
        app.statusMessages = __import__("queue").Queue()
        app.queuedStatusPopupKeys = set()
        app.displayedStatusPopupKeys = set()
        app.steamActionPopupMinimumSeconds = 0
        app.lastStatusPopupKey = None
        app.libraryOpen = False
        app.sessionService = FakeSessionService()
        app.steamIntegration = FakeSteamIntegration("open")
        app.runtimeStatusStore = FakeRuntimeStatusStore()
        app.readyNotificationCartridgeId = None
        app.icon = type("Icon", (), {"notify": lambda *_args: None})()
        app.logger = type("Logger", (), {"warning": lambda *_args: None})()
        states = (
            AppState(state=LauncherState.VALIDATING, rootPath="G:\\"),
            AppState(
                state=LauncherState.READY,
                rootPath="G:\\",
                cartridgeId="cart-1",
                manifest=CartridgeManifest(1, "cart-1", "Game A", "STEAM", "111", "SteamLibrary", "now"),
            ),
        )

        app._handleStates(states)

        message = app.statusMessages.get_nowait()
        dismiss = app.statusMessages.get_nowait()
        self.assertEqual(message.title, "Abriendo juego")
        self.assertNotEqual(message.title, "Validando cartucho")
        self.assertEqual(dismiss.key, "popup:dismiss")
        self.assertTrue(app.statusMessages.empty())
        self.assertEqual(app.steamIntegration.openedAppId, "111")

    def testExistingCartridgeShownOnAppOpenDoesNotAutoLaunch(self) -> None:
        app = object.__new__(TrayApp)
        app.steamAction = "auto"
        app.statusMessages = __import__("queue").Queue()
        app.queuedStatusPopupKeys = set()
        app.displayedStatusPopupKeys = set()
        app.steamActionPopupMinimumSeconds = 0
        app.lastStatusPopupKey = None
        app.libraryOpen = False
        app.sessionService = FakeSessionService()
        app.steamIntegration = FakeSteamIntegration("open")
        app.runtimeStatusStore = FakeRuntimeStatusStore()
        app.readyNotificationCartridgeId = None
        app.icon = type("Icon", (), {"notify": lambda *_args: None})()
        app.logger = type("Logger", (), {"warning": lambda *_args: None})()
        states = (
            AppState(state=LauncherState.VALIDATING, rootPath="G:\\"),
            AppState(
                state=LauncherState.READY,
                rootPath="G:\\",
                cartridgeId="cart-1",
                manifest=CartridgeManifest(1, "cart-1", "Game A", "STEAM", "111", "SteamLibrary", "now"),
            ),
        )

        app._handleStates(states, allowSteamAction=False, showStatePopups=False, notifyReady=False)

        self.assertTrue(app.statusMessages.empty())
        self.assertIsNone(app.steamIntegration.openedAppId)

    def testRemovedCartridgeSendsNotification(self) -> None:
        notifications = []
        app = object.__new__(TrayApp)
        app.steamAction = "none"
        app.statusMessages = __import__("queue").Queue()
        app.queuedStatusPopupKeys = set()
        app.displayedStatusPopupKeys = set()
        app.lastStatusPopupKey = None
        app.libraryOpen = False
        app.readyNotificationCartridgeId = "cart-1"
        app.icon = type("Icon", (), {"notify": lambda _self, message, title: notifications.append((title, message))})()
        app.logger = type("Logger", (), {"warning": lambda *_args: None})()

        app._handleStates((AppState(state=LauncherState.NOT_INSERTED, rootPath="G:\\"),))

        self.assertEqual(notifications, [("Cartucho expulsado", "El SSD cartucho fue expulsado.\nG:\\")])
        self.assertIsNone(app.readyNotificationCartridgeId)

    def testRepeatedRemovedCartridgePopupsAreNotDeduplicated(self) -> None:
        app = object.__new__(TrayApp)
        app.statusMessages = __import__("queue").Queue()
        app.queuedStatusPopupKeys = set()
        app.displayedStatusPopupKeys = {"NOT_INSERTED:G\\:::waiting for cartridge"}
        message = __import__("cartridge_launcher.ui.status_messages", fromlist=["statusPopupMessageFromState"]).statusPopupMessageFromState(
            AppState(state=LauncherState.NOT_INSERTED, rootPath="G:\\", message="waiting for cartridge")
        )

        app._queueStatusPopup(message)

        self.assertFalse(app.statusMessages.empty())

    def testFailedSteamActionDoesNotConsumeSessionAction(self) -> None:
        app = object.__new__(TrayApp)
        app.steamAction = "open"
        app.statusMessages = __import__("queue").Queue()
        app.queuedStatusPopupKeys = set()
        app.displayedStatusPopupKeys = set()
        app.steamActionPopupMinimumSeconds = 0
        app.sessionService = FakeSessionService()
        app.steamIntegration = FailingSteamIntegration()
        app.runtimeStatusStore = FakeRuntimeStatusStore()
        app.logger = type("Logger", (), {"warning": lambda *_args: None})()
        state = AppState(
            state=LauncherState.READY,
            cartridgeId="cart-1",
            manifest=CartridgeManifest(1, "cart-1", "Game A", "STEAM", "111", "SteamLibrary", "now"),
        )

        app._maybeRunSteamAction(state)

        self.assertFalse(app.sessionService.marked)


class FakeSessionService:
    def __init__(self):
        self.marked = False

    def shouldRunSteamAction(self, _state):
        return True

    def markSteamActionRun(self, _state):
        self.marked = True


class FakeSteamIntegration:
    def __init__(self, action: str):
        self.action = action
        self.openedAppId = None
        self.waitedAppId = None

    def runAutoAction(self, appId: str, _libraryRoot=None) -> str:
        self.openedAppId = appId
        return self.action

    def willOpenGame(self, _appId: str) -> bool:
        return self.action == "open"

    def waitForGameLaunch(self, appId: str, _startedAt: float) -> bool:
        self.waitedAppId = appId
        return True


class FailingSteamIntegration:
    def willOpenGame(self, _appId: str) -> bool:
        return True

    def openGame(self, _appId: str) -> None:
        from cartridge_launcher.domain.errors import CartridgeError, ErrorCode

        raise CartridgeError(ErrorCode.STEAM_NOT_FOUND, "Steam failed")


class FakeRuntimeStatusStore:
    def __init__(self):
        self.statuses = []

    def write(self, status):
        self.statuses.append(status)


if __name__ == "__main__":
    unittest.main()

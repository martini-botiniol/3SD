import logging
import queue
from unittest.mock import Mock, patch

import pytest

from cartridge_launcher.app.state import AppState
from cartridge_launcher.domain.models import CartridgeManifest
from cartridge_launcher.domain.states import LauncherState
from cartridge_launcher.ui.status_messages import statusPopupKeyFromState
from cartridge_launcher.ui.tray_app import TrayApp


def tray(libraryOpen=False, steamAction="auto"):
    app = object.__new__(TrayApp)
    app.steamAction = steamAction
    app.libraryOpen = libraryOpen
    app.currentState = AppState(state=LauncherState.NOT_INSERTED)
    app.statusMessages = queue.Queue()
    app.queuedStatusPopupKeys = set()
    app.displayedStatusPopupKeys = set()
    app.lastStatusPopupKey = None
    app.statusPopup = Mock()
    app.logger = logging.getLogger("test")
    app._notifyRemoved = Mock()
    app._notifyReady = Mock()
    app._maybeRunSteamAction = Mock()
    return app


REMOVED = AppState(state=LauncherState.NOT_INSERTED, rootPath="G:\\")
READY = AppState(state=LauncherState.READY, rootPath="H:\\", cartridgeId="next",
    manifest=CartridgeManifest(1, "next", "Next", "STEAM", "111", "SteamLibrary", "now"))


@pytest.mark.parametrize("libraryOpen", [False, True])
def test_removal_popup_with_library_open_or_closed(libraryOpen):
    app = tray(libraryOpen)
    app._handleStates((REMOVED,))
    with patch("cartridge_launcher.ui.tray_app.OperationWindowGate.isActive", return_value=False):
        app._processStatusMessages()
    assert app.statusPopup.show.call_args.args[0].key == statusPopupKeyFromState(REMOVED)


def test_reinsertion_and_second_removal_of_same_disk_not_deduplicated():
    app = tray()
    with patch("cartridge_launcher.ui.tray_app.OperationWindowGate.isActive", return_value=False), \
         patch("cartridge_launcher.ui.tray_app.time.monotonic", return_value=10) as clock:
        app._handleStates((REMOVED,))
        app._processStatusMessages()
        app._handleStates((READY,))
        # Automatic Steam action suppresses the ready popup, leaving the last key unchanged.
        assert app.lastStatusPopupKey == statusPopupKeyFromState(REMOVED)
        clock.return_value = 20
        app._handleStates((REMOVED,))
        app._processStatusMessages()
    assert app.statusPopup.show.call_count == 2


def test_waiting_cartridge_auto_launch_does_not_suppress_removal():
    app = tray()
    app._handleStates((REMOVED, READY))
    assert app.statusMessages.get_nowait().key == statusPopupKeyFromState(REMOVED)
    app._maybeRunSteamAction.assert_called_once_with(READY)


def test_following_event_does_not_immediately_replace_removal_popup():
    app = tray(steamAction="none")
    app._handleStates((REMOVED, READY))
    with patch("cartridge_launcher.ui.tray_app.OperationWindowGate.isActive", return_value=False), \
         patch("cartridge_launcher.ui.tray_app.time.monotonic", return_value=10) as clock:
        app._processStatusMessages()
        app._processStatusMessages()
        assert app.statusPopup.show.call_count == 1
        assert app.statusPopup.show.call_args.args[0].key == statusPopupKeyFromState(REMOVED)
        clock.return_value = 13.1
        app._processStatusMessages()
    assert app.statusPopup.show.call_count == 2


def test_form_suppresses_removal_without_replaying_it_after_close():
    app = tray(libraryOpen=True)
    app._handleStates((REMOVED,))
    with patch("cartridge_launcher.ui.tray_app.OperationWindowGate.isActive", return_value=True):
        app._processStatusMessages()
    app.statusPopup.show.assert_not_called()
    assert app.statusMessages.empty()
    app._handleStates((READY, REMOVED))
    with patch("cartridge_launcher.ui.tray_app.OperationWindowGate.isActive", return_value=False):
        app._processStatusMessages()
    app.statusPopup.show.assert_called_once()


def test_empty_startup_does_not_notify_a_removal():
    app = tray()
    app._handleStates((AppState(state=LauncherState.NOT_INSERTED),))
    assert app.statusMessages.empty()

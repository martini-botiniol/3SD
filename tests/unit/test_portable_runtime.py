from pathlib import Path
from threading import Event
from unittest.mock import Mock, patch
import time

import pytest

from cartridge_launcher.app.state import AppState
from cartridge_launcher.domain.errors import CartridgeError, ErrorCode
from cartridge_launcher.domain.models import CartridgeManifest, DeviceInfo
from cartridge_launcher.domain.states import LauncherState
from cartridge_launcher.infrastructure.steam_client import SteamClient, steamLibraryFolders, appInstallDirectory
from cartridge_launcher.services.cartridge_session_service import CartridgeSessionService
from cartridge_launcher.services.device_monitor import DeviceMonitor, DeviceChange
from cartridge_launcher.services.runtime_status import RuntimeStatusStore
from cartridge_launcher.services.steam_action_service import SteamActionService
from cartridge_launcher.ui.background_tasks import BackgroundTasks


def test_same_letter_replacement_and_metadata_update(tmp_path):
    first = DeviceInfo(str(tmp_path), "A", 100)
    second = DeviceInfo(str(tmp_path), "B", 100)
    scanner = Mock()
    scanner.scan.return_value = {str(tmp_path): first}
    monitor = DeviceMonitor(scanner)
    monitor.captureInitialState()
    scanner.scan.return_value = {str(tmp_path): second}
    snapshot = monitor.pollOnce()
    assert snapshot.removed[0].device == first
    assert snapshot.inserted[0].device == second
    metadata = tmp_path / ".cartridge"
    metadata.mkdir()
    (metadata / "manifest.json").write_text("{}")
    assert monitor.pollOnce().updated[0].device == second


def test_waiting_cartridge_promoted_on_removal():
    from tests.unit.test_cartridge_session_service import FakeWatchService, deviceChange
    service = CartridgeSessionService(FakeWatchService())
    service.handleInserted(deviceChange("G:\\", "one"))
    service.handleInserted(deviceChange("H:\\", "two"))
    result = service.handleRemoved(deviceChange("G:\\", "one"))
    assert result[0].state == LauncherState.NOT_INSERTED
    assert result[-1].cartridgeId == "two"


def test_disconnected_waiting_cartridge_is_not_promoted():
    from tests.unit.test_cartridge_session_service import FakeWatchService, deviceChange
    service = CartridgeSessionService(FakeWatchService())
    service.handleInserted(deviceChange("G:\\", "one"))
    service.handleInserted(deviceChange("H:\\", "two"))
    service.handleRemoved(deviceChange("H:\\", "two"))
    assert service.handleRemoved(deviceChange("G:\\", "one"))[-1].state == LauncherState.NOT_INSERTED


def test_discovers_external_library_and_reads_install_state(tmp_path):
    steam = tmp_path / "custom steam"
    library = tmp_path / "external" / "SteamLibrary"
    (steam / "steamapps").mkdir(parents=True)
    (library / "steamapps" / "common" / "Game").mkdir(parents=True)
    location = str(library).replace("\\", "\\\\")
    (steam / "steamapps" / "libraryfolders.vdf").write_text('"libraryfolders" { "1" { "label" "" "path" "' + location + '" } }')
    manifest = library / "steamapps" / "appmanifest_111.acf"
    manifest.write_text('"AppState" { "StateFlags" "4" "installdir" "Game" }')
    client = SteamClient()
    with patch("cartridge_launcher.infrastructure.steam_client.steamInstallRoots", return_value=(steam,)):
        assert library in steamLibraryFolders()
        assert client.isLibraryRegistered(library)
        assert client.isGameInstalled("111")
        assert appInstallDirectory("111", library) == library / "steamapps" / "common" / "Game"
    manifest.write_text('"AppState" { "StateFlags" "6" "installdir" "Game" }')
    assert client.installationState("111", library) == "partial"
    manifest.unlink()
    assert client.installationState("111", library) == "missing"


@pytest.fixture
def action(tmp_path):
    device = DeviceInfo(str(tmp_path), "A", 100)
    scanner = Mock()
    scanner.findDeviceByRoot.return_value = device
    manifest = CartridgeManifest(2, "id", "Game", "STEAM", "111", "SteamLibrary", "2026-09-08T00:00:00Z", {})
    validator = Mock()
    validator.validate.return_value = manifest
    client = Mock()
    client.isLibraryRegistered.return_value = True
    client.installationState.return_value = "installed"
    client.waitForGameLaunch.return_value = True
    state = AppState(LauncherState.READY, str(tmp_path), "id", manifest)
    service = SteamActionService(validator, scanner, client, RuntimeStatusStore(tmp_path / "status.json"))
    return service, scanner, client, validator, state


def test_action_checks_inserted_library_and_revalidates(action):
    service, scanner, client, validator, state = action
    result = service.execute(state, "auto")
    assert result.phase == "running"
    validator.validate.assert_called_once()
    client.openGame.assert_called_once_with("111")
    assert client.waitForGameLaunch.call_args.kwargs["libraryRoot"] == Path(state.rootPath) / "SteamLibrary"


@pytest.mark.parametrize("failure,expected", [("library", ErrorCode.LIBRARY_REQUIRED),
    ("removed", ErrorCode.DEVICE_REMOVED), ("changed", ErrorCode.INVALID_MANIFEST),
    ("steam", ErrorCode.STEAM_NOT_FOUND)])
def test_action_does_not_launch_when_preflight_fails(action, failure, expected):
    service, scanner, client, validator, state = action
    if failure == "library":
        client.isLibraryRegistered.return_value = False
    elif failure == "removed":
        scanner.findDeviceByRoot.return_value = None
    elif failure == "changed":
        validator.validate.return_value = Mock()
    else:
        client.ensureAvailable.side_effect = CartridgeError(ErrorCode.STEAM_NOT_FOUND, "No Steam")
    with pytest.raises(CartridgeError) as exc:
        service.execute(state, "auto")
    assert exc.value.code == expected
    client.openGame.assert_not_called()
    client.installGame.assert_not_called()


def test_partial_install_is_sent_to_steam_for_completion(action):
    service, _, client, _, state = action
    client.installationState.return_value = "partial"
    assert service.execute(state, "auto").action == "install"
    client.installGame.assert_called_once_with("111")
    client.openGame.assert_not_called()


def test_launch_timeout_is_not_reported_as_running(action):
    service, _, client, _, state = action
    client.waitForGameLaunch.return_value = False
    assert service.execute(state, "open").phase == "unconfirmed"


def test_removal_during_wait_never_publishes_running(action):
    service, _, client, _, state = action
    cancelled = Event()
    def wait(*args, **kwargs):
        cancelled.set()
        return True
    client.waitForGameLaunch.side_effect = wait
    assert service.execute(state, "open", cancelled.is_set).phase == "cancelled"
    assert service.statusStore.read().phase != "running"


def test_background_results_are_applied_only_on_main_thread():
    root = Mock()
    runner = BackgroundTasks(root)
    gate = Event()
    complete = Mock()
    try:
        assert runner.submit("slow", lambda: gate.wait(1), complete, Mock())
        assert not runner.submit("slow", lambda: None, complete, Mock())
        complete.assert_not_called()
        gate.set()
        deadline = time.monotonic() + 2
        while runner.results.empty() and time.monotonic() < deadline:
            time.sleep(0.005)
        complete.assert_not_called()
        runner._drain()
        complete.assert_called_once_with(True)
    finally:
        runner._destroy(type("Event", (), {"widget": root})())


def test_cover_downloads_cannot_starve_device_detection_or_steam():
    root = Mock()
    runner = BackgroundTasks(root)
    release = Event()
    scanned, launched = Event(), Event()
    try:
        for index in range(8):
            runner.submit(("cover", index), lambda: release.wait(3), Mock(), Mock())
        runner.submit("poll", scanned.set, Mock(), Mock())
        runner.submit(("steam", 1), launched.set, Mock(), Mock())
        assert scanned.wait(1) and launched.wait(1)
    finally:
        release.set()
        runner._destroy(type("Event", (), {"widget": root})())


def test_new_cartridge_action_can_queue_while_old_action_cancels():
    root = Mock()
    runner = BackgroundTasks(root)
    release, launched = Event(), Event()
    try:
        assert runner.submit(("steam", 1), lambda: release.wait(2), Mock(), Mock())
        assert runner.submit(("steam", 2), launched.set, Mock(), Mock())
        release.set()
        assert launched.wait(1)
    finally:
        release.set()
        runner._destroy(type("Event", (), {"widget": root})())

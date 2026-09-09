from types import SimpleNamespace
from unittest.mock import Mock, patch
import tkinter as tk

import pytest

from cartridge_launcher.domain.models import DeviceInfo
from cartridge_launcher.infrastructure.steam_store_search import SteamSearchResult
from cartridge_launcher.ui.cartridge_dialog import CartridgeDialog
from cartridge_launcher.ui.dialog_controller import DialogController, OperationWindowGate
from cartridge_launcher.ui.status_popup import StatusPopup
from cartridge_launcher.ui.status_messages import StatusPopupMessage


def test_controller_keeps_original_operation_and_releases_after_close():
    gate = Mock()
    factory = Mock()
    controller = DialogController(factory, gate=gate)
    window = factory.return_value
    window.close.side_effect = lambda: (controller._closed() or True)
    assert controller.open("create") is window
    for operation in ("create", "update", "repair", "convert"):
        assert controller.open(operation) is window
    factory.assert_called_once_with("create", controller._closed)
    assert window.focus.call_count == 4
    assert controller.close()
    assert not controller.active
    gate.release.assert_called_once()
    controller.open("update")
    assert factory.call_count == 2


def test_controller_reentrancy_and_busy_close():
    controller = DialogController(Mock(), gate=Mock())
    def factory(operation, closed):
        assert controller.open("repair") is None
        return Mock(close=Mock(return_value=False))
    controller.factory = factory
    controller.open("create")
    assert not controller.close()
    assert controller.active


def test_controller_releases_gate_on_construction_failure():
    gate = Mock()
    controller = DialogController(Mock(side_effect=RuntimeError("failure")), gate=gate)
    with pytest.raises(RuntimeError):
        controller.open("create")
    assert not controller.active
    gate.release.assert_called_once()


def test_process_gate_excludes_other_library_and_recovers():
    first, second = OperationWindowGate(), OperationWindowGate()
    try:
        assert first.acquire()
        assert OperationWindowGate.isActive()
        assert not second.acquire()
        first.release()
        assert second.acquire()
    finally:
        first.release()
        second.release()
    assert not OperationWindowGate.isActive()


def test_tray_records_events_without_popups_or_toasts_during_form():
    import queue
    from cartridge_launcher.ui.tray_app import TrayApp
    app = object.__new__(TrayApp)
    app.statusPopup, app.icon, app.logger = Mock(), Mock(), Mock()
    app.statusMessages = queue.Queue()
    app.statusMessages.put(StatusPopupMessage("Test", "Connected", key="test"))
    app.queuedStatusPopupKeys = {"test"}
    app.displayedStatusPopupKeys = set()
    with patch.object(OperationWindowGate, "isActive", return_value=True):
        app._processStatusMessages()
        app._notify("Test", "Connected")
    app.statusPopup.show.assert_not_called()
    app.statusPopup.dismiss.assert_called_once()
    app.icon.notify.assert_not_called()
    assert app.statusMessages.empty()
    assert not app.queuedStatusPopupKeys
    assert not app.displayedStatusPopupKeys
    assert app.logger.info.call_count == 2


class Tasks:
    def __init__(self):
        self.jobs = []

    def submit(self, key, work, done, failed):
        self.jobs.append(SimpleNamespace(key=key, work=work, done=done, failed=failed))
        return True


@pytest.fixture(scope="module")
def tk_root():
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk runtime unavailable: {exc}")
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def form(tk_root):
    root = tk_root
    tasks, scanner, success = Tasks(), Mock(), Mock()
    dialogs = []
    def make(operation="create"):
        dialog = CartridgeDialog(root, operation, Mock(), Mock(), scanner, Mock(), tasks, success, Mock())
        dialogs.append(dialog)
        return dialog
    yield make, tasks, scanner, success, root
    for dialog in dialogs:
        dialog.busy = False
        dialog.close()


def select_disk(dialog, tasks, path="G:\\"):
    dialog._scanDevices()
    device = DeviceInfo(path, "SERIAL", 1024**3)
    tasks.jobs[-1].done({path: device})
    assert dialog.selectedDevice is None
    dialog.deviceText.set(next(iter(dialog.devices)))
    dialog._selectDevice()
    return device


@pytest.mark.parametrize("operation", ["create", "update", "repair", "convert"])
def test_fresh_forms_and_inline_validation(form, operation):
    make, tasks, _, _, _ = form
    dialog = make(operation)
    assert not dialog.deviceText.get() and not dialog.appIdText.get()
    dialog.submit()
    assert "Selecciona" in dialog.messageText.get()
    assert not tasks.jobs
    select_disk(dialog, tasks)
    if operation != "create":
        tasks.jobs[-1].done(SimpleNamespace(displayName="Original", appId="111"))
        assert "Original" in dialog.currentText.get()
        assert dialog.nameText.get() == ("Original" if operation == "repair" else "")
    assert bool(dialog.gameInputs) == (operation != "convert")
    if operation == "repair":
        count = len(tasks.jobs)
        dialog.submit()
        assert "confirmación" in dialog.messageText.get()
        assert len(tasks.jobs) == count


def test_write_is_unique_cannot_close_and_scan_error_does_not_unlock(form):
    make, tasks, scanner, success, _ = form
    dialog = make()
    scanner.findDeviceByRoot.return_value = select_disk(dialog, tasks)
    scan = tasks.jobs[-1]
    dialog.nameText.set("Test")
    dialog.appIdText.set("111")
    dialog.submit()
    write = tasks.jobs[-1]
    count = len(tasks.jobs)
    dialog.submit()
    assert len(tasks.jobs) == count
    assert not dialog.close()
    scan.failed(RuntimeError("late scan error"))
    assert dialog.busy
    write.failed(RuntimeError("write error"))
    assert not dialog.busy
    assert "write error" in dialog.messageText.get()
    dialog.submit()
    assert len(tasks.jobs) == count + 1
    tasks.jobs[-1].done(SimpleNamespace(displayName="Test"))
    assert dialog.closed
    success.assert_called_once()


def test_search_results_discarded_after_query_change_disk_change_or_close(form):
    make, tasks, _, _, _ = form
    dialog = make()
    select_disk(dialog, tasks)
    dialog.queryText.set("old")
    dialog._search()
    search = tasks.jobs[-1]
    results = [SteamSearchResult("111", "Old", "")]
    dialog.queryText.set("new")
    search.done(results)
    assert not dialog.results
    dialog._search()
    search = tasks.jobs[-1]
    dialog._selectDevice()
    search.done(results)
    assert not dialog.results
    dialog.queryText.set("again")
    dialog._search()
    search = tasks.jobs[-1]
    dialog.close()
    search.done(results)
    search.failed(RuntimeError())
    assert not dialog.results


def test_disconnect_resets_selection_and_prevents_writing_to_replacement(form):
    make, tasks, scanner, _, _ = form
    dialog = make()
    select_disk(dialog, tasks)
    dialog.nameText.set("Test")
    dialog.appIdText.set("111")
    dialog.submit()
    scanner.findDeviceByRoot.return_value = DeviceInfo("G:\\", "OTHER", 1024**3)
    with pytest.raises(Exception, match="desconectó|reemplazado"):
        tasks.jobs[-1].work()
    tasks.jobs[-1].failed(RuntimeError("removed"))
    dialog._scanDevices()
    tasks.jobs[-1].done({})
    assert dialog.selectedDevice is None
    assert not dialog.appIdText.get()


def test_status_popup_does_not_open_during_operation(form):
    _, _, _, _, root = form
    gate = OperationWindowGate()
    popup = StatusPopup(root)
    try:
        assert gate.acquire()
        popup.show(StatusPopupMessage("Test", "Notification"))
        assert popup.window is None
    finally:
        gate.release()

from __future__ import annotations

import logging
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from typing import Callable
from tkinter import ttk

from PIL import Image, ImageDraw

from cartridge_launcher.app.state import AppState
from cartridge_launcher.domain.errors import CartridgeError
from cartridge_launcher.domain.states import LauncherState
from cartridge_launcher.infrastructure.single_instance import SingleInstanceSignal
from cartridge_launcher.infrastructure.steam_client import SteamClient
from cartridge_launcher.infrastructure.windows_devices import WindowsDeviceScanner
from cartridge_launcher.services.cartridge_session_service import CartridgeSessionService
from cartridge_launcher.services.cartridge_validator import CartridgeValidator
from cartridge_launcher.services.cartridge_watch_service import CartridgeWatchService
from cartridge_launcher.services.device_monitor import DeviceMonitor
from cartridge_launcher.services.local_registry import LocalRegistry
from cartridge_launcher.services.runtime_status import RuntimeStatus, defaultRuntimeStatusStore
from cartridge_launcher.services.security_service import SecurityService
from cartridge_launcher.services.steam_integration import SteamIntegration
from cartridge_launcher.ui.app_icon import appIconPath
from cartridge_launcher.ui.status_messages import StatusPopupMessage, statusPopupDismissMessage, statusPopupKeyFromState, statusPopupMessageFromBlockedCartridge, statusPopupMessageFromState, statusPopupMessageFromSteamAction
from cartridge_launcher.ui.status_popup import StatusPopup


class TrayApp:
    def __init__(self, security: SecurityService, registry: LocalRegistry, deviceScanner: WindowsDeviceScanner, logger: logging.Logger, intervalSeconds: float = 2.0, steamAction: str = "auto", openWindowOnStart: bool = False, iconFactory: Callable[[], Image.Image] | None = None, exitProcess: Callable[[int], None] | None = None, killProcessGroup: Callable[[], None] | None = None):
        self.security = security
        self.registry = registry
        self.deviceScanner = deviceScanner
        self.logger = logger
        self.intervalSeconds = intervalSeconds
        self.steamAction = steamAction
        self.steamActionPopupMinimumSeconds = 2
        self.openWindowOnStart = openWindowOnStart
        self.exitProcess = exitProcess or os._exit
        self.killProcessGroup = killProcessGroup or killPackagedProcesses
        self.monitor = DeviceMonitor(deviceScanner)
        self.steamIntegration = SteamIntegration(SteamClient())
        self.runtimeStatusStore = defaultRuntimeStatusStore()
        validator = CartridgeValidator(security, registry)
        self.sessionService = CartridgeSessionService(CartridgeWatchService(validator, logger), logger)
        self.currentState = self.sessionService.initialState()
        self.running = False
        self.workerThread: threading.Thread | None = None
        self.libraryRequested = threading.Event()
        self.libraryOpen = False
        self.libraryProcess: subprocess.Popen | None = None
        self.readyNotificationCartridgeId: str | None = None
        self.lastStatusPopupKey: str | None = None
        self.queuedStatusPopupKeys: set[str] = set()
        self.displayedStatusPopupKeys: set[str] = set()
        self.statusMessages: queue.Queue[StatusPopupMessage] = queue.Queue()
        self.statusRoot: tk.Tk | None = None
        self.statusPopup: StatusPopup | None = None
        self.instanceSignal = SingleInstanceSignal()
        self.pystray = loadPystray()
        self.icon = self.pystray.Icon("3sd", (iconFactory or createTrayIcon)(), "3SD", self._menu())

    def run(self) -> None:
        self.running = True
        self.instanceSignal.create()
        self._setupStatusWindow()
        self._scanExisting(
            allowSteamAction=not self.openWindowOnStart,
            showStatePopups=not self.openWindowOnStart,
            notifyReady=not self.openWindowOnStart,
        )
        self.monitor.captureInitialState()
        self.workerThread = threading.Thread(target=self._monitorLoop, daemon=True)
        self.workerThread.start()
        if self.openWindowOnStart:
            self.openLibrary()
        self.icon.run_detached()
        self._mainLoop()

    def stop(self, trayIcon=None) -> None:
        self.running = False
        self.instanceSignal.close()
        self._closeLibraryProcess()
        self._destroyStatusWindow()
        iconToStop = trayIcon or self.icon
        try:
            iconToStop.visible = False
        except (AttributeError, NotImplementedError):
            pass
        iconToStop.stop()

    def exitApp(self, trayIcon=None) -> None:
        self.running = False
        self.instanceSignal.close()
        self._hideTrayIcon(trayIcon)
        self._stopTrayIcon(trayIcon)
        self._closeLibraryProcess(timeoutSeconds=0.25)
        self._destroyStatusWindow()
        self.killProcessGroup()
        try:
            self.exitProcess(0)
        except SystemExit:
            raise

    def statusText(self) -> str:
        state = self.currentState
        if state.state == LauncherState.READY and state.manifest is not None:
            return f"Ready: {state.manifest.displayName}"
        if state.errorCode is not None:
            return f"{state.errorCode}"
        return state.state.value

    def scanExisting(self) -> None:
        self._scanExisting()

    def openLibrary(self) -> None:
        if not self.libraryOpen:
            self.libraryRequested.set()

    def _openLibrarySafely(self) -> None:
        try:
            self.libraryProcess = subprocess.Popen(self._uiCommand())
            self.libraryOpen = True
        except Exception as exc:
            self.logger.exception("Could not open UI: %s", exc)

    def _uiCommand(self) -> list[str]:
        executablePath = Path(sys.executable)
        if executablePath.name.lower().endswith(".exe") and executablePath.stem.lower() == "3sd":
            return [str(executablePath), "ui", "--from-tray"]
        return [str(executablePath), "-m", "cartridge_launcher.app.main", "ui", "--from-tray"]

    def _menu(self):
        return self.pystray.Menu(
            self.pystray.MenuItem(lambda item: self.statusText(), None, enabled=False),
            self.pystray.MenuItem("Open Library", lambda icon, item: self.openLibrary()),
            self.pystray.MenuItem("Scan Existing Cartridge", lambda icon, item: self.scanExisting()),
            self.pystray.MenuItem("Exit", lambda icon, item: self.exitApp(icon)),
        )

    def _monitorLoop(self) -> None:
        while self.running:
            time.sleep(self.intervalSeconds)
            snapshot = self.monitor.pollOnce()
            for change in snapshot.removed:
                self._handleStates(self.sessionService.handleRemoved(change))
            for change in snapshot.inserted:
                if self.sessionService.isBlockedByActiveCartridge(change):
                    self._queueStatusPopup(statusPopupMessageFromBlockedCartridge(str(change.root)))
                    continue
                self._handleStates(self.sessionService.handleInserted(change))

    def _mainLoop(self) -> None:
        while self.running:
            self._refreshLibraryProcessState()
            self._processStatusMessages()
            if self.statusRoot is not None:
                try:
                    self.statusRoot.update()
                except tk.TclError:
                    self.statusRoot = None
                    self.statusPopup = None
            if self.libraryRequested.is_set() and not self.libraryOpen:
                self.libraryRequested.clear()
                self._openLibrarySafely()
            if self.instanceSignal.wasSignaled() and not self.libraryOpen:
                self.openLibrary()
            time.sleep(0.2)

    def _refreshLibraryProcessState(self) -> None:
        if self.libraryProcess is None:
            self.libraryOpen = False
            return
        if self.libraryProcess.poll() is not None:
            self.libraryProcess = None
            self.libraryOpen = False

    def _closeLibraryProcess(self, timeoutSeconds: float = 1.0) -> None:
        if self.libraryProcess is not None and self.libraryProcess.poll() is None:
            self.libraryProcess.terminate()
            try:
                self.libraryProcess.wait(timeout=timeoutSeconds)
            except subprocess.TimeoutExpired:
                self.libraryProcess.kill()
        self.libraryProcess = None
        self.libraryOpen = False

    def _destroyStatusWindow(self) -> None:
        if self.statusRoot is not None:
            self.statusRoot.destroy()
        self.statusRoot = None
        self.statusPopup = None

    def _hideTrayIcon(self, trayIcon=None) -> None:
        try:
            (trayIcon or self.icon).visible = False
        except (AttributeError, NotImplementedError):
            pass

    def _stopTrayIcon(self, trayIcon=None) -> None:
        try:
            (trayIcon or self.icon).stop()
        except RuntimeError:
            pass

    def _setupStatusWindow(self) -> None:
        try:
            root = tk.Tk()
            root.withdraw()
            applyTkWindowIcon(root, self.logger)
            style = ttk.Style(root)
            style.theme_use("clam")
            style.configure("Panel.TFrame", background="#1c2024")
            style.configure("Panel.TLabel", background="#1c2024", foreground="#eff1ee")
            style.configure("PanelMuted.TLabel", background="#1c2024", foreground="#aab0ad")
            self.statusRoot = root
            self.statusPopup = StatusPopup(root, self.openLibrary)
        except tk.TclError as exc:
            self.logger.warning("Tray status window unavailable: %s", exc)

    def _processStatusMessages(self) -> None:
        if self.statusPopup is None:
            return
        while True:
            try:
                message = self.statusMessages.get_nowait()
            except queue.Empty:
                return
            if message.key == "popup:dismiss":
                self.statusPopup.dismiss()
                continue
            messageKey = message.key or f"{message.title}:{message.message}"
            self.queuedStatusPopupKeys.discard(messageKey)
            if messageKey in self.displayedStatusPopupKeys and not messageKey.startswith("NOT_INSERTED:"):
                continue
            self.displayedStatusPopupKeys.add(messageKey)
            self.lastStatusPopupKey = messageKey
            self.statusPopup.show(message)

    def _scanExisting(self, allowSteamAction: bool = True, showStatePopups: bool = True, notifyReady: bool = True) -> None:
        self._handleStates(
            self.sessionService.handleExisting(self.deviceScanner.scan()),
            allowSteamAction=allowSteamAction,
            showStatePopups=showStatePopups,
            notifyReady=notifyReady,
        )

    def _handleStates(self, states: tuple[AppState, ...], allowSteamAction: bool = True, showStatePopups: bool = True, notifyReady: bool = True) -> None:
        willRunSteamAction = (
            allowSteamAction
            and self.steamAction != "none"
            and len(states) > 0
            and states[-1].state == LauncherState.READY
            and states[-1].manifest is not None
        )
        for state in states:
            self.currentState = state
            statusMessage = statusPopupMessageFromState(state)
            popupKey = statusPopupKeyFromState(state)
            if showStatePopups and not willRunSteamAction and statusMessage is not None and popupKey is not None and popupKey != self.lastStatusPopupKey and not self.libraryOpen:
                self._queueStatusPopup(statusMessage)
            if state.state == LauncherState.NOT_INSERTED:
                self.readyNotificationCartridgeId = None
                self._notifyRemoved(state)
            if state.state == LauncherState.READY:
                if notifyReady:
                    self._notifyReady(state)
                if allowSteamAction:
                    self._maybeRunSteamAction(state)

    def _notifyReady(self, state: AppState) -> None:
        if state.manifest is None or state.cartridgeId == self.readyNotificationCartridgeId:
            return
        self.readyNotificationCartridgeId = state.cartridgeId
        self._notify("Cartucho insertado", f"{state.manifest.displayName} detectado.")

    def _notifyRemoved(self, state: AppState) -> None:
        if state.rootPath is None:
            return
        self._notify("Cartucho expulsado", f"El SSD cartucho fue expulsado.\n{state.rootPath}")

    def _maybeRunSteamAction(self, state: AppState) -> None:
        if self.steamAction == "none" or state.manifest is None or not self.sessionService.shouldRunSteamAction(state):
            return
        action = "open" if self.steamAction == "auto" else self.steamAction
        willOpenGame = action == "open" or (self.steamAction == "auto" and self.steamIntegration.willOpenGame(state.manifest.appId))
        startedAt = time.time()
        try:
            self._writeRuntimeStatus(state, self.steamAction, "sending")
            if willOpenGame:
                self._queueStatusPopup(statusPopupMessageFromSteamAction(state.manifest.displayName, "open", str(startedAt)))
            if self.steamAction == "open":
                self.steamIntegration.openGame(state.manifest.appId)
                action = "open"
            elif self.steamAction == "install":
                self.steamIntegration.installGame(state.manifest.appId)
                action = "install"
            else:
                libraryRoot = Path(state.rootPath) / state.manifest.libraryPath if state.rootPath is not None else None
                action = self.steamIntegration.runAutoAction(state.manifest.appId, libraryRoot)
            self._writeRuntimeStatus(state, action, "accepted")
            self.sessionService.markSteamActionRun(state)
            if action == "open" and self.steamIntegration.waitForGameLaunch(state.manifest.appId, startedAt):
                self._writeRuntimeStatus(state, action, "running")
        except CartridgeError as exc:
            self.logger.warning("Tray Steam action failed: %s %s", exc.code, exc)
        finally:
            if willOpenGame:
                self._waitBeforeDismissingSteamPopup(startedAt)
                self._queueStatusDismiss()

    def _writeRuntimeStatus(self, state: AppState, action: str, phase: str) -> None:
        if state.manifest is None or state.cartridgeId is None:
            return
        self.runtimeStatusStore.write(
            RuntimeStatus(
                cartridgeId=state.cartridgeId,
                appId=state.manifest.appId,
                displayName=state.manifest.displayName,
                action=action,
                phase=phase,
                timestamp=time.time(),
            )
        )

    def _queueStatusPopup(self, message: StatusPopupMessage) -> None:
        messageKey = message.key or f"{message.title}:{message.message}"
        if not messageKey.startswith("NOT_INSERTED:") and (messageKey in self.displayedStatusPopupKeys or messageKey in self.queuedStatusPopupKeys):
            return
        self.queuedStatusPopupKeys.add(messageKey)
        self.statusMessages.put(message)

    def _queueStatusDismiss(self) -> None:
        self.statusMessages.put(statusPopupDismissMessage())

    def _waitBeforeDismissingSteamPopup(self, startedAt: float) -> None:
        remaining = getattr(self, "steamActionPopupMinimumSeconds", 2) - (time.time() - startedAt)
        if remaining > 0:
            time.sleep(remaining)

    def _notify(self, title: str, message: str) -> None:
        try:
            self.icon.notify(message, title)
        except (AttributeError, NotImplementedError):
            pass


def createTrayIcon() -> Image.Image:
    iconPath = appIconPath()
    if iconPath is not None:
        return Image.open(iconPath).convert("RGBA")
    image = Image.new("RGBA", (64, 64), "#111315")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((10, 8, 54, 56), radius=8, fill="#2f7d5c")
    draw.rectangle((18, 16, 46, 24), fill="#eff1ee")
    draw.rectangle((20, 34, 44, 46), fill="#111315")
    return image


def applyTkWindowIcon(root: tk.Tk, logger: logging.Logger) -> None:
    iconPath = appIconPath()
    if iconPath is None:
        return
    try:
        root.iconbitmap(str(iconPath))
    except tk.TclError:
        logger.warning("Could not apply tray status window icon: %s", iconPath)


def loadPystray():
    try:
        import pystray
    except ModuleNotFoundError as exc:
        raise RuntimeError("pystray is required for tray mode. Run: py -m pip install -e .") from exc
    return pystray


def isPackagedExecutable() -> bool:
    executablePath = Path(sys.executable)
    return executablePath.name.lower().endswith(".exe") and executablePath.stem.lower() == "3sd"


def killPackagedProcesses() -> None:
    if not isPackagedExecutable():
        return
    subprocess.Popen(
        packagedKillCommand(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
    )


def packagedKillCommand() -> list[str]:
    return [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        "Get-Process -Name '3SD' -ErrorAction SilentlyContinue | Stop-Process -Force",
    ]

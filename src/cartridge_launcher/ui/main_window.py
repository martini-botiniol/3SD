from __future__ import annotations

import logging
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from cartridge_launcher.app.state import AppState
from cartridge_launcher.domain.errors import CartridgeError
from cartridge_launcher.services.steam_action_service import SteamActionService
from cartridge_launcher.ui.background_tasks import BackgroundTasks
from cartridge_launcher.ui.cartridge_dialog import CartridgeDialog
from cartridge_launcher.ui.dialog_controller import DialogController
from cartridge_launcher.domain.states import LauncherState
from cartridge_launcher.infrastructure.steam_client import SteamClient
from cartridge_launcher.infrastructure.steam_store_search import SteamSearchResult, SteamStoreSearchClient
from cartridge_launcher.infrastructure.startup_shortcut import disableStartup, enableStartup, isStartupEnabled
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
from cartridge_launcher.ui.cover_cache import CoverCache
from cartridge_launcher.ui.error_messages import friendlyErrorFromCode
from cartridge_launcher.ui.help_content import helpText, helpTitle
from cartridge_launcher.ui.modern_button import ModernButton
from cartridge_launcher.ui.status_messages import StatusPopupMessage, statusPopupKeyFromState, statusPopupMessageFromState
from cartridge_launcher.ui.status_popup import StatusPopup
from cartridge_launcher.ui.view_models import LibraryCardViewModel, libraryCardsWithState, libraryDetailFromRegistry, librarySelectionSummary, steamLibraryCoverUrl, viewModelFromState


class LauncherWindow:
    def __init__(self, root: tk.Tk, security: SecurityService, registry: LocalRegistry, deviceScanner: WindowsDeviceScanner, sessionService: CartridgeSessionService, steamIntegration: SteamIntegration, logger: logging.Logger, intervalMilliseconds: int = 2000, steamSearchClient: SteamStoreSearchClient | None = None, suppressStatePopups: bool = False):
        self.root = root
        self.security = security
        self.registry = registry
        self.deviceScanner = deviceScanner
        self.monitor = DeviceMonitor(deviceScanner)
        self.sessionService = sessionService
        self.steamIntegration = steamIntegration
        self.runtimeStatusStore = defaultRuntimeStatusStore()
        self.steamSearchClient = steamSearchClient or SteamStoreSearchClient()
        self.logger = logger
        self.intervalMilliseconds = intervalMilliseconds
        self.suppressStatePopups = suppressStatePopups
        self.tasks = BackgroundTasks(root)
        self.generation = 0
        self.coverCache = CoverCache(Path.home() / ".3sd" / "covers", self.tasks, self._refreshLibrary)
        self.actions = SteamActionService(CartridgeValidator(security, registry), deviceScanner,
            steamIntegration.steamClient, self.runtimeStatusStore)
        self.currentState = self.sessionService.initialState()
        self.sidebarVisible = False
        self.libraryCards: tuple[LibraryCardViewModel, ...] = ()
        self.libraryColumnCount = 0
        self.statusPopup = StatusPopup(root)
        self.dialogController = DialogController(self._makeCartridgeDialog, self.statusPopup.dismiss)
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.titleText = tk.StringVar()
        self.subtitleText = tk.StringVar()
        self.detailText = tk.StringVar()
        self.statusText = tk.StringVar()
        self.actionText = tk.StringVar(value="")
        self.stateTechnicalDetailText = tk.StringVar(value="")
        self.stateTechnicalVisible = False
        self.startupStatusText = tk.StringVar(value="")
        self.startupEnabledValue = tk.BooleanVar(value=False)
        self.sidebarSections: dict[str, ttk.Frame] = {}
        self.sidebarSectionLabels: dict[str, tk.StringVar] = {}
        self.sidebarSectionVisible: dict[str, bool] = {}
        self.activityItems: list[str] = []
        self.lastActivityKey: str | None = None
        self.lastStatusPopupKey: str | None = None

        self.root.title("3SD")
        self.root.geometry("1080x680")
        self.root.minsize(720, 480)
        self._applyWindowIcon()
        self._configureStyles()
        self._build()
        self._refreshStartupState()
        self._render(self.currentState)
        self._refreshLibrary()
        self._scanExisting()
        self.monitor.captureInitialState()
        self.root.after(self.intervalMilliseconds, self._poll)

    def _configureStyles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        for name, bg, fg in [
            ("App.TFrame", "#0f1418", "#f4f7f5"), ("Panel.TFrame", "#1a2228", "#f4f7f5"), ("Status.TFrame", "#202b32", "#f4f7f5"), ("Slot.TFrame", "#151c21", "#f4f7f5"), ("Card.TFrame", "#20282f", "#f4f7f5"), ("ActiveCard.TFrame", "#1f3a31", "#f4f7f5"),
        ]:
            style.configure(name, background=bg)
        style.configure("App.TLabel", background="#0f1418", foreground="#f4f7f5")
        style.configure("Muted.TLabel", background="#0f1418", foreground="#aeb8b4")
        style.configure("Panel.TLabel", background="#1a2228", foreground="#f4f7f5")
        style.configure("PanelMuted.TLabel", background="#1a2228", foreground="#aeb8b4")
        style.configure("Status.TLabel", background="#202b32", foreground="#f4f7f5")
        style.configure("StatusMuted.TLabel", background="#202b32", foreground="#b9c4bf")
        style.configure("Slot.TLabel", background="#151c21", foreground="#f4f7f5")
        style.configure("Card.TLabel", background="#20282f", foreground="#f4f7f5")
        style.configure("ActiveCard.TLabel", background="#1f3a31", foreground="#f4f7f5")
        style.configure("Modern.TCombobox", fieldbackground="#20282f", background="#20282f", foreground="#f4f7f5", arrowcolor="#dce5e0", bordercolor="#34434c", lightcolor="#34434c", darkcolor="#34434c", padding=6)
        style.map("Modern.TCombobox", fieldbackground=[("readonly", "#20282f")], foreground=[("readonly", "#f4f7f5")], selectbackground=[("readonly", "#26323a")], selectforeground=[("readonly", "#f4f7f5")])

    def _build(self) -> None:
        self.root.configure(bg="#0f1418")
        self.shell = ttk.Frame(self.root, style="App.TFrame", padding=20)
        self.shell.pack(fill="both", expand=True)
        self.shell.columnconfigure(0, weight=1)
        self.shell.columnconfigure(1, weight=0)
        self.shell.rowconfigure(1, weight=1)
        header = ttk.Frame(self.shell, style="App.TFrame")
        header.grid(row=0, column=0, columnspan=2, sticky="we", pady=(0, 16))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Biblioteca de cartuchos", style="App.TLabel", font=("Segoe UI", 24, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="Conecta un SSD y juega desde Steam como si fuera un cartucho.", style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 0))
        ModernButton(header, text="Ayuda", command=self._showHelp, background="#0f1418", width=94).grid(row=0, column=1, rowspan=2, sticky="e", padx=(0, 8))
        ModernButton(header, text="☰", command=self._toggleSidebar, background="#0f1418", width=48, height=42).grid(row=0, column=2, rowspan=2, sticky="e")

        self.libraryFrame = ttk.Frame(self.shell, style="App.TFrame")
        self.libraryFrame.grid(row=1, column=0, sticky="nsew", padx=(0, 18))
        self.libraryFrame.columnconfigure(0, weight=1)
        self.libraryFrame.rowconfigure(1, weight=1)
        self._buildStatusBand()
        self.cardsCanvas = tk.Canvas(self.libraryFrame, bg="#0f1418", highlightthickness=0)
        self.cardsCanvas.grid(row=1, column=0, sticky="nsew")
        self.cardsScrollbar = ttk.Scrollbar(self.libraryFrame, orient="vertical", command=self.cardsCanvas.yview)
        self.cardsCanvas.configure(yscrollcommand=lambda first, last: self._setScrollbar(self.cardsScrollbar, first, last, row=1, column=1))
        self.cardsFrame = ttk.Frame(self.cardsCanvas, style="App.TFrame")
        self.cardsCanvasWindow = self.cardsCanvas.create_window((0, 0), window=self.cardsFrame, anchor="nw")
        self.cardsFrame.bind("<Configure>", lambda event: self._updateCardsScrollregion())
        self.cardsCanvas.bind("<Configure>", self._onCardsCanvasConfigure)

        self.sidebarContainer = ttk.Frame(self.shell, style="Panel.TFrame")
        self.sidebarContainer.grid(row=1, column=1, sticky="nsew")
        self.sidebarCanvas = tk.Canvas(self.sidebarContainer, width=312, bg="#1a2228", highlightthickness=0)
        self.sidebarCanvas.grid(row=0, column=0, sticky="nsew")
        self.sidebarScrollbar = ttk.Scrollbar(self.sidebarContainer, orient="vertical", command=self.sidebarCanvas.yview)
        self.sidebarCanvas.configure(yscrollcommand=lambda first, last: self._setScrollbar(self.sidebarScrollbar, first, last, row=0, column=1))
        self.sidebarContainer.rowconfigure(0, weight=1)
        self.sidebarContainer.columnconfigure(0, weight=1)
        self.sidebar = ttk.Frame(self.sidebarCanvas, style="Panel.TFrame", padding=16)
        self.sidebarCanvasWindow = self.sidebarCanvas.create_window((0, 0), window=self.sidebar, anchor="nw")
        self.sidebar.bind("<Configure>", lambda event: self._updateSidebarScrollregion())
        self.sidebarCanvas.bind("<Configure>", lambda event: self._onSidebarCanvasConfigure(event))
        self._buildSidebar()
        self.sidebarContainer.grid_remove()
        self._bindGlobalWheelScrolling()

    def _buildStatusBand(self) -> None:
        self.statusBand = ttk.Frame(self.libraryFrame, style="Status.TFrame", padding=18)
        self.statusBand.grid(row=0, column=0, sticky="we", pady=(0, 16))
        self.statusBand.columnconfigure(1, weight=1)
        ttk.Label(self.statusBand, text="SSD SLOT", style="StatusMuted.TLabel", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        self.slotFrame = ttk.Frame(self.statusBand, style="Slot.TFrame", padding=14)
        self.slotFrame.grid(row=1, column=0, sticky="nw", padx=(0, 18))
        self.slotCoverLabel = ttk.Label(self.slotFrame, style="Slot.TLabel")
        self.slotEmptyCanvas = tk.Canvas(self.slotFrame, width=132, height=188, bg="#151c21", highlightthickness=0)
        self.slotEmptyCanvas.create_rectangle(16, 22, 116, 166, outline="#51606a", width=2)
        self.slotEmptyCanvas.create_line(30, 50, 102, 50, fill="#51606a", width=2)
        self.slotEmptyCanvas.create_text(66, 96, text="ranura\nvacia", fill="#aeb8b4", width=96, font=("Segoe UI", 11, "bold"))
        self.slotEmptyCanvas.grid(row=0, column=0, sticky="n")
        self.slotTextFrame = ttk.Frame(self.statusBand, style="Status.TFrame")
        self.slotTextFrame.grid(row=1, column=1, sticky="new")
        self.slotStatusLabel = tk.Label(self.slotTextFrame, textvariable=self.statusText, bg="#202b32", fg="#8a9690", font=("Segoe UI", 10, "bold"))
        self.slotStatusLabel.grid(row=0, column=0, sticky="w")
        ttk.Label(self.slotTextFrame, textvariable=self.titleText, style="Status.TLabel", font=("Segoe UI", 18, "bold")).grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(self.slotTextFrame, textvariable=self.subtitleText, style="StatusMuted.TLabel").grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Label(self.slotTextFrame, textvariable=self.detailText, style="StatusMuted.TLabel", wraplength=520).grid(row=3, column=0, sticky="we", pady=(10, 0))
        slotActions = ttk.Frame(self.slotTextFrame, style="Status.TFrame")
        slotActions.grid(row=4, column=0, sticky="w", pady=(12, 0))
        self.slotPlayButton = ModernButton(slotActions, text="Jugar", command=lambda: self._runSteamAction("open"), variant="accent", background="#202b32", width=100)
        self.slotPlayButton.grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.slotInstallButton = ModernButton(slotActions, text="Instalar", command=lambda: self._runSteamAction("install"), background="#202b32", width=110)
        self.slotInstallButton.grid(row=0, column=1, sticky="w")
        self.stateTechnicalLabel = ttk.Label(self.slotTextFrame, textvariable=self.stateTechnicalDetailText, style="StatusMuted.TLabel", wraplength=640)
        ModernButton(self.statusBand, text="Detalles", command=self._toggleStateTechnicalDetails, background="#202b32", width=112).grid(row=1, column=2, sticky="ne")

    def _applyWindowIcon(self) -> None:
        iconPath = appIconPath()
        if iconPath is None:
            return
        try:
            self.root.iconbitmap(str(iconPath))
        except tk.TclError:
            self.logger.warning("Could not apply window icon: %s", iconPath)

    def _buildSidebar(self) -> None:
        self.sidebar.columnconfigure(0, weight=1)
        self.sidebar.columnconfigure(1, weight=1)
        ttk.Label(self.sidebar, text="Centro de control", style="Panel.TLabel", font=("Segoe UI", 16, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        cartridges = self._addSidebarSection(1, "cartridges", "Opciones de cartucho", "")
        ModernButton(cartridges, text="Crear cartucho", command=self._createCartridge, variant="accent", background="#1a2228", width=244).grid(row=1, column=0, columnspan=2, sticky="we", pady=(0, 8))
        ModernButton(cartridges, text="Actualizar cartucho", command=self._updateCartridge, background="#1a2228", width=244).grid(row=2, column=0, columnspan=2, sticky="we")
        repair = self._addSidebarSection(3, "repair", "Reparar cartucho", "", parent=cartridges)
        ModernButton(repair, text="Reparar", command=self._repairCartridge, background="#1a2228", width=244).grid(row=1, column=0, columnspan=2, sticky="we", pady=(0, 8))
        ModernButton(repair, text="Preparar para usar en cualquier PC", command=self._convertCartridge, background="#1a2228", width=244).grid(row=2, column=0, columnspan=2, sticky="we")
        windowsSection = self._addSidebarSection(4, "windows", "Windows", "Configura cómo se comporta la app al iniciar.")
        activitySection = self._addSidebarSection(7, "activity", "Actividad", "Eventos recientes del launcher.")
        self.startupToggle = ttk.Checkbutton(windowsSection, text="Iniciar con Windows", variable=self.startupEnabledValue, command=self._toggleStartup)
        self.startupToggle.grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))
        ttk.Label(windowsSection, textvariable=self.startupStatusText, style="PanelMuted.TLabel", wraplength=260).grid(row=2, column=0, columnspan=2, sticky="we", pady=(6, 0))
        self.activityLabel = ttk.Label(activitySection, text="Sin actividad reciente.", style="PanelMuted.TLabel", wraplength=260)
        self.activityLabel.grid(row=1, column=0, columnspan=2, sticky="we", pady=(10, 0))
        ModernButton(self.sidebar, text="Actualizar biblioteca", command=self._refreshLibrary, background="#1a2228", width=244).grid(row=10, column=0, columnspan=2, sticky="we", pady=(22, 8))
        ttk.Label(self.sidebar, textvariable=self.actionText, style="PanelMuted.TLabel", wraplength=260).grid(row=11, column=0, columnspan=2, sticky="we", pady=(10, 0))

    def _addSidebarSection(self, row: int, key: str, title: str, description: str, parent=None) -> ttk.Frame:
        parent = self.sidebar if parent is None else parent
        labelText = tk.StringVar(value=f"▸ {title}")
        self.sidebarSectionLabels[key] = labelText
        self.sidebarSectionVisible[key] = False
        ttk.Separator(parent).grid(row=row, column=0, columnspan=2, sticky="we", pady=(14, 10))
        ModernButton(parent, textvariable=labelText, command=lambda: self._toggleSidebarSection(key, title), background="#1a2228", width=244).grid(row=row + 1, column=0, columnspan=2, sticky="we")
        body = ttk.Frame(parent, style="Panel.TFrame")
        body.grid(row=row + 2, column=0, columnspan=2, sticky="we", pady=(8, 0))
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        if description:
            ttk.Label(body, text=description, style="PanelMuted.TLabel", wraplength=260).grid(row=0, column=0, columnspan=2, sticky="we")
        body.grid_remove()
        self.sidebarSections[key] = body
        return body

    def _toggleSidebarSection(self, key: str, title: str) -> None:
        section = self.sidebarSections[key]
        isVisible = self.sidebarSectionVisible[key]
        if isVisible:
            section.grid_remove()
            self.sidebarSectionLabels[key].set(f"▸ {title}")
        else:
            section.grid()
            self.sidebarSectionLabels[key].set(f"▾ {title}")
        self.sidebarSectionVisible[key] = not isVisible
        self._updateSidebarScrollregion()

    def _toggleSidebar(self) -> None:
        if self.sidebarVisible:
            self.sidebarContainer.grid_remove()
        else:
            self.sidebarContainer.grid(row=1, column=1, sticky="nsew")
        self.sidebarVisible = not self.sidebarVisible

    def _showHelp(self) -> None:
        if self.dialogController.active:
            if self.dialogController.dialog is not None:
                self.dialogController.dialog.focus()
            return
        messagebox.showinfo(helpTitle, helpText, parent=self.root)

    def _toggleStateTechnicalDetails(self) -> None:
        self.stateTechnicalVisible = not self.stateTechnicalVisible
        if self.stateTechnicalVisible and self.stateTechnicalDetailText.get():
            self.stateTechnicalLabel.grid(row=5, column=0, sticky="we", pady=(8, 0))
        else:
            self.stateTechnicalLabel.grid_remove()

    def _updateCardsScrollregion(self) -> None:
        self.cardsCanvas.configure(scrollregion=self.cardsCanvas.bbox("all"))

    def _updateSidebarScrollregion(self) -> None:
        self.sidebarCanvas.configure(scrollregion=self.sidebarCanvas.bbox("all"))

    def _onSidebarCanvasConfigure(self, event) -> None:
        self.sidebarCanvas.itemconfigure(self.sidebarCanvasWindow, width=event.width)
        self._updateSidebarScrollregion()

    def _setScrollbar(self, scrollbar: ttk.Scrollbar, first: str, last: str, row: int, column: int) -> None:
        if float(first) <= 0.0 and float(last) >= 1.0:
            scrollbar.grid_remove()
        else:
            scrollbar.grid(row=row, column=column, sticky="ns")
        scrollbar.set(first, last)

    def _bindGlobalWheelScrolling(self) -> None:
        self.root.bind_all("<MouseWheel>", self._scrollActiveCanvasWithWheel)
        self.root.bind_all("<Button-4>", lambda event: self._scrollActiveCanvasByUnits(-1))
        self.root.bind_all("<Button-5>", lambda event: self._scrollActiveCanvasByUnits(1))

    def _scrollActiveCanvasWithWheel(self, event) -> None:
        if event.delta == 0:
            return
        canvas = self._activeScrollCanvas()
        if canvas is not None:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _scrollActiveCanvasByUnits(self, units: int) -> None:
        canvas = self._activeScrollCanvas()
        if canvas is not None:
            canvas.yview_scroll(units, "units")

    def _activeScrollCanvas(self) -> tk.Canvas | None:
        if self.dialogController.active:
            return None
        widget = self.root.winfo_containing(self.root.winfo_pointerx(), self.root.winfo_pointery())
        if self._isDescendantOf(widget, self.sidebarCanvas) or self._isDescendantOf(widget, self.sidebar):
            return self.sidebarCanvas
        if self._isDescendantOf(widget, self.cardsCanvas) or self._isDescendantOf(widget, self.cardsFrame):
            return self.cardsCanvas
        return None

    def _isDescendantOf(self, widget, ancestor) -> bool:
        current = widget
        while current is not None:
            if current == ancestor:
                return True
            current = getattr(current, "master", None)
        return False

    def _refreshStartupState(self) -> None:
        enabled = isStartupEnabled()
        self.startupEnabledValue.set(enabled)
        self.startupStatusText.set("Activado" if enabled else "Desactivado")

    def _toggleStartup(self) -> None:
        try:
            if self.startupEnabledValue.get():
                path = enableStartup()
                self.startupStatusText.set(f"Activado: {path.name}")
            else:
                disableStartup()
                self.startupStatusText.set("Desactivado")
        except RuntimeError:
            self._refreshStartupState()
            self.actionText.set("No se pudo actualizar el inicio con Windows.")

    def _scanExisting(self) -> None:
        def complete(states):
            for state in states:
                self._render(state, showPopup=False)
                self._autoLaunch(state)
        self.tasks.submit("poll", lambda: self.sessionService.handleExisting(self.deviceScanner.scan()),
                          complete, lambda exc: self.actionText.set(str(exc)))

    def _poll(self) -> None:
        def scan():
            snapshot = self.monitor.pollOnce()
            states = []
            for change in snapshot.removed:
                states.extend(self.sessionService.handleRemoved(change))
            for change in snapshot.inserted + snapshot.updated:
                states.extend(self.sessionService.handleInserted(change))
            return states
        def complete(states):
            for state in states:
                if state.state == LauncherState.NOT_INSERTED:
                    self.generation += 1
                    self.runtimeStatusStore.clear()
                self._render(state)
                self._autoLaunch(state)
            self._renderRuntimeStatus()
            if self.sessionService.waiting:
                self.actionText.set("Hay cartuchos en espera. Se activaran al retirar el actual.")
        self.tasks.submit("poll", scan, complete,
                          lambda exc: self.actionText.set("No se pudo leer el disco; vuelve a conectarlo."))
        self.root.after(self.intervalMilliseconds, self._poll)

    def _autoLaunch(self, state) -> None:
        if not self.suppressStatePopups and self.sessionService.shouldRunSteamAction(state):
            self._runSteamAction("auto")

    def _render(self, state: AppState, showPopup: bool = True) -> None:
        if (state.rootPath, state.manifest, state.state) != (self.currentState.rootPath, self.currentState.manifest, self.currentState.state):
            self.generation += 1
        self.currentState = state
        state = self._stateWithRuntimeStatus(state)
        viewModel = viewModelFromState(state)
        self.titleText.set(viewModel.title)
        self.subtitleText.set(viewModel.subtitle)
        self.detailText.set(viewModel.detail)
        self.statusText.set(viewModel.status)
        self.stateTechnicalDetailText.set(viewModel.technicalDetail)
        if not viewModel.technicalDetail or not self.stateTechnicalVisible:
            self.stateTechnicalLabel.grid_remove()
        buttonState = "normal" if viewModel.canRunSteamAction else "disabled"
        self.slotPlayButton.configure(state=buttonState)
        self.slotInstallButton.configure(state=buttonState)
        self._renderSlot(state)
        self._addActivity(activityTextFromState(state), activityKeyFromState(state))
        self._refreshLibrary()
        if showPopup:
            self._showStatusPopupForState(state)

    def _renderSlot(self, state: AppState) -> None:
        statusColor = {LauncherState.READY: "#75ff8a", LauncherState.VALIDATING: "#ffd166", LauncherState.NOT_INSERTED: "#8a9690", LauncherState.STEAM_REQUIRED: "#ffd166", LauncherState.INVALID_CARTRIDGE: "#ff5c5c", LauncherState.DEVICE_MISMATCH: "#ff9d5c", LauncherState.ERROR: "#ff5c5c"}.get(state.state, "#b9c4bf")
        self.slotStatusLabel.configure(fg=statusColor)
        cover = None
        if state.manifest is not None:
            cover = self.coverCache.get(state.manifest.appId, steamLibraryCoverUrl(state.manifest.appId), (132, 198))
        if cover is None:
            self.slotCoverLabel.grid_remove()
            self.slotEmptyCanvas.grid(row=0, column=0, sticky="n")
            return
        self.slotEmptyCanvas.grid_remove()
        self.slotCoverLabel.configure(image=cover)
        self.slotCoverLabel.image = cover
        self.slotCoverLabel.grid(row=0, column=0, sticky="n")

    def _renderRuntimeStatus(self) -> None:
        if self.currentState.state == LauncherState.READY:
            self._render(self.currentState)

    def _stateWithRuntimeStatus(self, state: AppState) -> AppState:
        runtimeStatus = self.runtimeStatusStore.read()
        if runtimeStatus is None or state.cartridgeId != runtimeStatus.cartridgeId:
            return state
        runtimeState = LauncherState.READY if runtimeStatus.phase == "unconfirmed" else LauncherState.GAME_RUNNING if runtimeStatus.phase == "running" else LauncherState.OPENING if runtimeStatus.action == "open" else LauncherState.NOT_INSTALLED
        message = runtimeStatusMessage(runtimeStatus)
        return AppState(
            state=runtimeState,
            rootPath=state.rootPath,
            cartridgeId=state.cartridgeId,
            manifest=state.manifest,
            message=message,
        )

    def _showStatusPopupForState(self, state: AppState) -> None:
        if self.suppressStatePopups:
            return
        message = statusPopupMessageFromState(state)
        popupKey = statusPopupKeyFromState(state)
        if message is None or popupKey is None:
            return
        self._showStatusPopup(message)

    def _onCardsCanvasConfigure(self, event) -> None:
        self.cardsCanvas.itemconfigure(self.cardsCanvasWindow, width=event.width)
        self._renderLibraryCards(event.width)

    def _refreshLibrary(self) -> None:
        activeCartridgeId = self.currentState.cartridgeId if self.currentState.state == LauncherState.READY else None
        try:
            self.libraryCards = libraryCardsWithState(self.registry.all(), activeCartridgeId)
            if self.registry.warning:
                self.actionText.set(self.registry.warning)
        except CartridgeError as exc:
            self.actionText.set(exc.message)
            self.libraryCards = ()
        self._renderLibraryCards(max(self.cardsCanvas.winfo_width(), 1))

    def _renderLibraryCards(self, availableWidth: int) -> None:
        for child in self.cardsFrame.winfo_children():
            child.destroy()
        columnCount = max(1, availableWidth // 190)
        if not self.libraryCards:
            ttk.Label(self.cardsFrame, text="Conecta un cartucho para comenzar.\nPuedes preparar un SSD desde Opciones.",
                      style="PanelMuted.TLabel").grid(row=0, column=0, padx=16, pady=24)
        for index, card in enumerate(self.libraryCards):
            frame = ttk.Frame(self.cardsFrame, style="ActiveCard.TFrame" if card.isActive else "Card.TFrame", padding=12)
            frame.grid(row=index // columnCount, column=index % columnCount, sticky="nw", padx=(0, 12), pady=(0, 12))
            labelStyle = "ActiveCard.TLabel" if card.isActive else "Card.TLabel"
            cover = self.coverCache.get(card.appId, card.coverUrl, (132, 198))
            if cover is not None:
                coverLabel = ttk.Label(frame, image=cover, style=labelStyle)
                coverLabel.image = cover
                coverLabel.grid(row=0, column=0, sticky="w")
                coverLabel.bind("<Button-1>", lambda event, cartridgeId=card.cartridgeId: self._selectLibraryCard(cartridgeId))
            else:
                placeholder = tk.Canvas(frame, width=132, height=198, bg="#20282f" if not card.isActive else "#1f3a31", highlightthickness=0)
                placeholder.create_rectangle(12, 14, 120, 184, outline="#50606a", width=2)
                placeholder.create_text(66, 99, text=card.displayName, fill="#f4f7f5", width=104, font=("Segoe UI", 11, "bold"))
                placeholder.grid(row=0, column=0, sticky="w")
                placeholder.bind("<Button-1>", lambda event, cartridgeId=card.cartridgeId: self._selectLibraryCard(cartridgeId))

            titleLabel = ttk.Label(frame, text=card.displayName, style=labelStyle, wraplength=150, font=("Segoe UI", 11, "bold"))
            titleLabel.grid(row=1, column=0, sticky="w", pady=(8, 0))
            titleLabel.bind("<Button-1>", lambda event, cartridgeId=card.cartridgeId: self._selectLibraryCard(cartridgeId))
            statusLabel = ttk.Label(frame, text=card.statusText, style=labelStyle, font=("Segoe UI", 9))
            statusLabel.grid(row=2, column=0, sticky="w", pady=(4, 0))
            statusLabel.bind("<Button-1>", lambda event, cartridgeId=card.cartridgeId: self._selectLibraryCard(cartridgeId))
            frame.bind("<Button-1>", lambda event, cartridgeId=card.cartridgeId: self._selectLibraryCard(cartridgeId))

    def _selectLibraryCard(self, cartridgeId: str) -> None:
        cartridge = self.registry.get(cartridgeId)
        if cartridge is not None:
            self.actionText.set(librarySelectionSummary(libraryDetailFromRegistry(cartridge)))

    def _makeCartridgeDialog(self, operation, onClosed):
        return CartridgeDialog(self.root, operation, self.security, self.registry,
            self.deviceScanner, self.steamSearchClient, self.tasks, self._cartridgeSaved, onClosed)

    def _cartridgeSaved(self, manifest):
        self.actionText.set(f"Cartucho listo: {manifest.displayName}")
        self._scanExisting()
        self._refreshLibrary()

    def _close(self):
        if self.dialogController.close():
            self.root.destroy()

    def _openCartridgeDialog(self, operation):
        dialog = self.dialogController.open(operation)
        if dialog is None:
            self.actionText.set("Ya hay una operación abierta en otra ventana de 3SD.")
        return dialog

    def _createCartridge(self):
        return self._openCartridgeDialog("create")

    def _updateCartridge(self):
        return self._openCartridgeDialog("update")

    def _repairCartridge(self):
        return self._openCartridgeDialog("repair")

    def _convertCartridge(self):
        return self._openCartridgeDialog("convert")

    def _runSteamAction(self, steamAction: str) -> None:
        state = self.currentState
        if state.state != LauncherState.READY or state.manifest is None:
            self.actionText.set("Conecta un cartucho valido para continuar.")
            return
        generation = self.generation
        self.actionText.set("Comprobando cartucho y Steam...")
        def cancelled():
            return self.tasks.closed or self.generation != generation
        def complete(result):
            if not cancelled():
                self.actionText.set(result.message)
                self.sessionService.markSteamActionRun(state)
        def failed(exc):
            if not cancelled():
                self.actionText.set(exc.message if isinstance(exc, CartridgeError) else "Steam no pudo completar la solicitud.")
                self.logger.warning("Accion Steam: %s", exc)
        self.tasks.submit(("steam", generation), lambda: self.actions.execute(state, steamAction, cancelled), complete, failed)

    def _showStatusPopup(self, message: StatusPopupMessage) -> None:
        if self.dialogController.active:
            return
        popupKey = message.key or f"{message.title}:{message.message}"
        if popupKey == self.lastStatusPopupKey:
            return
        self.lastStatusPopupKey = popupKey
        self.statusPopup.show(message)

    def _addActivity(self, text: str, key: str | None = None) -> None:
        if key is not None and key == self.lastActivityKey:
            return
        self.lastActivityKey = key
        self.activityItems = ([text] + self.activityItems)[:8]
        if hasattr(self, "activityLabel"):
            self.activityLabel.configure(text="\n".join(self.activityItems))


def steamSearchResultLabel(result: SteamSearchResult) -> str:
    return f"{result.displayName} ({result.appId})"


def activityTextFromState(state: AppState) -> str:
    if state.state == LauncherState.VALIDATING:
        return f"Validando cartucho: {state.rootPath or 'disco'}"
    if state.state == LauncherState.READY and state.manifest is not None:
        return f"Cartucho listo: {state.manifest.displayName}"
    if state.state == LauncherState.NOT_INSERTED and state.rootPath is not None:
        return f"Cartucho removido: {state.rootPath}"
    if state.errorCode is not None:
        return f"Error de cartucho: {state.errorCode.value}"
    if state.state == LauncherState.NOT_INSERTED:
        return "Esperando cartucho."
    return state.message


def activityKeyFromState(state: AppState) -> str:
    return f"{state.state.value}:{state.cartridgeId or ''}:{state.rootPath or ''}:{state.errorCode or ''}"


def runtimeStatusMessage(runtimeStatus: RuntimeStatus) -> str:
    if runtimeStatus.phase == "unconfirmed":
        return "Solicitud enviada; inicio no confirmado. Revisa Steam."
    if runtimeStatus.phase == "running":
        return f"Steam inicio {runtimeStatus.displayName}."
    if runtimeStatus.phase == "sending":
        return f"Enviando solicitud a Steam: {runtimeStatus.displayName}"
    if runtimeStatus.action == "open":
        return f"Steam esta abriendo {runtimeStatus.displayName}."
    if runtimeStatus.action == "install":
        return f"Steam esta preparando la instalacion de {runtimeStatus.displayName}."
    return f"Steam esta preparando {runtimeStatus.displayName}."


def runLauncherUi(security: SecurityService, registry: LocalRegistry, deviceScanner: WindowsDeviceScanner, logger: logging.Logger, suppressStatePopups: bool = False) -> None:
    validator = CartridgeValidator(security, registry)
    watchService = CartridgeWatchService(validator, logger)
    sessionService = CartridgeSessionService(watchService, logger)
    root = tk.Tk()
    LauncherWindow(root, security, registry, deviceScanner, sessionService, SteamIntegration(SteamClient()), logger, suppressStatePopups=suppressStatePopups)
    root.mainloop()

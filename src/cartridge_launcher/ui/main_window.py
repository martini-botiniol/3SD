from __future__ import annotations

import logging
from pathlib import Path
import time
import tkinter as tk
from tkinter import messagebox, ttk

from cartridge_launcher.app.state import AppState
from cartridge_launcher.domain.errors import CartridgeError
from cartridge_launcher.domain.models import RegisteredCartridge
from cartridge_launcher.domain.states import LauncherState
from cartridge_launcher.infrastructure.steam_client import SteamClient
from cartridge_launcher.infrastructure.steam_store_search import SteamSearchResult, SteamStoreSearchClient
from cartridge_launcher.infrastructure.startup_shortcut import disableStartup, enableStartup, isStartupEnabled
from cartridge_launcher.infrastructure.windows_devices import WindowsDeviceScanner
from cartridge_launcher.services.cartridge_creation_service import CartridgeCreationService
from cartridge_launcher.services.cartridge_session_service import CartridgeSessionService
from cartridge_launcher.services.cartridge_update_service import CartridgeUpdateService
from cartridge_launcher.services.cartridge_validator import CartridgeValidator
from cartridge_launcher.services.cartridge_watch_service import CartridgeWatchService
from cartridge_launcher.services.device_monitor import DeviceChange, DeviceMonitor
from cartridge_launcher.services.local_registry import LocalRegistry
from cartridge_launcher.services.runtime_status import RuntimeStatus, defaultRuntimeStatusStore
from cartridge_launcher.services.security_service import SecurityService
from cartridge_launcher.services.steam_integration import SteamIntegration
from cartridge_launcher.ui.app_icon import appIconPath
from cartridge_launcher.ui.cover_cache import CoverCache
from cartridge_launcher.ui.error_messages import friendlyErrorFromCode
from cartridge_launcher.ui.help_content import helpText, helpTitle
from cartridge_launcher.ui.modern_button import ModernButton
from cartridge_launcher.ui.status_messages import StatusPopupMessage, statusPopupKeyFromState, statusPopupMessageFromBlockedCartridge, statusPopupMessageFromState
from cartridge_launcher.ui.status_popup import StatusPopup
from cartridge_launcher.ui.view_models import LibraryCardViewModel, formatCapacity, libraryAdvancedDetails, libraryCardsWithState, libraryDetailFromRegistry, librarySelectionSummary, steamLibraryCoverUrl, viewModelFromState


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
        self.coverCache = CoverCache(Path.cwd() / ".cartridge-launcher" / "covers")
        self.currentState = self.sessionService.initialState()
        self.sidebarVisible = False
        self.libraryCards: tuple[LibraryCardViewModel, ...] = ()
        self.libraryColumnCount = 0
        self.statusPopup = StatusPopup(root)
        self.titleText = tk.StringVar()
        self.subtitleText = tk.StringVar()
        self.detailText = tk.StringVar()
        self.statusText = tk.StringVar()
        self.actionText = tk.StringVar(value="")
        self.selectedDeviceText = tk.StringVar()
        self.createDisplayNameText = tk.StringVar()
        self.createAppIdText = tk.StringVar()
        self.deviceDetailsText = tk.StringVar(value="")
        self.deviceDetailsVisible = False
        self.selectedGameTitleText = tk.StringVar(value="Selecciona un juego")
        self.selectedGameDetailText = tk.StringVar(value="Elige una portada para ver acciones y detalles.")
        self.selectedGameAdvancedText = tk.StringVar(value="")
        self.selectedGameAdvancedVisible = False
        self.selectedAppId: str | None = None
        self.selectedCartridgeId: str | None = None
        self.searchResultText = tk.StringVar(value="")
        self.stateTechnicalDetailText = tk.StringVar(value="")
        self.stateTechnicalVisible = False
        self.optionsButtonText = tk.StringVar(value="Opciones")
        self.startupStatusText = tk.StringVar(value="")
        self.startupEnabledValue = tk.BooleanVar(value=False)
        self.deviceOptions: dict[str, str] = {}
        self.searchResults: dict[str, SteamSearchResult] = {}
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
        self._refreshDevices(showResult=False)
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
        ModernButton(header, textvariable=self.optionsButtonText, command=self._toggleSidebar, background="#0f1418", width=142).grid(row=0, column=2, rowspan=2, sticky="e")

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
        setupSection = self._addSidebarSection(1, "setup", "Seleccionar SSD y juego", "Elige el disco y el juego que usaras en las acciones de cartucho.")
        createSection = self._addSidebarSection(4, "create", "Crear cartucho", "Prepara un SSD nuevo con el juego seleccionado.")
        updateSection = self._addSidebarSection(7, "update", "Actualizar cartucho", "Reemplaza el juego asociado al SSD seleccionado.")
        activeSection = self._addSidebarSection(10, "active", "Cartucho activo", "Acciones para el SSD conectado ahora.")
        selectedSection = self._addSidebarSection(13, "selected", "Juego seleccionado", "Acciones para una portada elegida de la biblioteca.")
        windowsSection = self._addSidebarSection(16, "windows", "Windows", "Configura como se comporta la app al iniciar.")
        activitySection = self._addSidebarSection(19, "activity", "Actividad", "Eventos recientes del launcher.")
        self._buildSetupSection(setupSection)
        ModernButton(createSection, text="Crear cartucho", command=self._createCartridge, variant="accent", background="#1a2228", width=244).grid(row=1, column=0, columnspan=2, sticky="we", pady=(10, 0))
        ModernButton(updateSection, text="Cambiar juego del cartucho", command=self._updateCartridge, variant="accent", background="#1a2228", width=244).grid(row=1, column=0, columnspan=2, sticky="we", pady=(10, 8))
        ttk.Label(updateSection, text="Para quitar el juego actual y poner otro, selecciona el SSD, elige el nuevo juego y usa Cambiar juego.", style="PanelMuted.TLabel", wraplength=260).grid(row=2, column=0, columnspan=2, sticky="we")
        self.openButton = ModernButton(activeSection, text="Abrir", command=lambda: self._runSteamAction("open"), background="#1a2228")
        self.openButton.grid(row=1, column=0, sticky="we", padx=(0, 6), pady=(10, 8))
        self.installButton = ModernButton(activeSection, text="Instalar", command=lambda: self._runSteamAction("install"), background="#1a2228")
        self.installButton.grid(row=1, column=1, sticky="we", pady=(10, 8))
        self.autoButton = ModernButton(activeSection, text="Abrir o instalar automaticamente", command=lambda: self._runSteamAction("auto"), background="#1a2228", width=244)
        self.autoButton.grid(row=2, column=0, columnspan=2, sticky="we")
        ttk.Label(selectedSection, textvariable=self.selectedGameTitleText, style="Panel.TLabel", font=("Segoe UI", 11, "bold"), wraplength=260).grid(row=1, column=0, columnspan=2, sticky="we", pady=(10, 0))
        ttk.Label(selectedSection, textvariable=self.selectedGameDetailText, style="PanelMuted.TLabel", wraplength=260).grid(row=2, column=0, columnspan=2, sticky="we", pady=(6, 8))
        ModernButton(selectedSection, text="Detalles", command=self._toggleSelectedGameAdvancedDetails, background="#1a2228", width=244).grid(row=3, column=0, columnspan=2, sticky="we", pady=(0, 8))
        self.selectedGameAdvancedLabel = ttk.Label(selectedSection, textvariable=self.selectedGameAdvancedText, style="PanelMuted.TLabel", wraplength=260)
        self.selectedOpenButton = ModernButton(selectedSection, text="Abrir", command=lambda: self._runSelectedSteamAction("open"), background="#1a2228")
        self.selectedOpenButton.grid(row=5, column=0, sticky="we", padx=(0, 6))
        self.selectedInstallButton = ModernButton(selectedSection, text="Instalar", command=lambda: self._runSelectedSteamAction("install"), background="#1a2228")
        self.selectedInstallButton.grid(row=5, column=1, sticky="we")
        ModernButton(selectedSection, text="Eliminar registro", command=self._deleteSelectedLibraryCard, background="#1a2228", width=244).grid(row=6, column=0, columnspan=2, sticky="we", pady=(8, 0))
        self.startupToggle = ttk.Checkbutton(windowsSection, text="Iniciar con Windows", variable=self.startupEnabledValue, command=self._toggleStartup)
        self.startupToggle.grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))
        ttk.Label(windowsSection, textvariable=self.startupStatusText, style="PanelMuted.TLabel", wraplength=260).grid(row=2, column=0, columnspan=2, sticky="we", pady=(6, 0))
        self.activityLabel = ttk.Label(activitySection, text="Sin actividad reciente.", style="PanelMuted.TLabel", wraplength=260)
        self.activityLabel.grid(row=1, column=0, columnspan=2, sticky="we", pady=(10, 0))
        ModernButton(self.sidebar, text="Actualizar biblioteca", command=self._refreshLibrary, background="#1a2228", width=244).grid(row=22, column=0, columnspan=2, sticky="we", pady=(22, 8))
        ttk.Label(self.sidebar, textvariable=self.actionText, style="PanelMuted.TLabel", wraplength=260).grid(row=23, column=0, columnspan=2, sticky="we", pady=(10, 0))

    def _buildSetupSection(self, setupSection) -> None:
        ttk.Label(setupSection, text="Disco", style="Panel.TLabel").grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.deviceCombo = ttk.Combobox(setupSection, textvariable=self.selectedDeviceText, width=26, state="readonly")
        self.deviceCombo.grid(row=2, column=0, columnspan=2, sticky="we", pady=(4, 8))
        self.deviceCombo.bind("<<ComboboxSelected>>", lambda event: self._renderDeviceDetails())
        ModernButton(setupSection, text="Actualizar", command=self._refreshDevices, background="#1a2228").grid(row=3, column=0, sticky="we", padx=(0, 6), pady=(0, 10))
        ModernButton(setupSection, text="Detalles", command=self._toggleDeviceDetails, background="#1a2228").grid(row=3, column=1, sticky="we", pady=(0, 10))
        self.deviceDetailsLabel = ttk.Label(setupSection, textvariable=self.deviceDetailsText, style="PanelMuted.TLabel", wraplength=260)
        ttk.Label(setupSection, text="Nombre del juego", style="Panel.TLabel").grid(row=5, column=0, sticky="w")
        ttk.Entry(setupSection, textvariable=self.createDisplayNameText, width=28).grid(row=6, column=0, columnspan=2, sticky="we", pady=(4, 10))
        ttk.Label(setupSection, text="Steam AppID", style="Panel.TLabel").grid(row=7, column=0, sticky="w")
        ttk.Entry(setupSection, textvariable=self.createAppIdText, width=28).grid(row=8, column=0, columnspan=2, sticky="we", pady=(4, 12))
        ModernButton(setupSection, text="Buscar por nombre", command=self._searchSteamGame, background="#1a2228", width=244).grid(row=9, column=0, columnspan=2, sticky="we", pady=(0, 8))
        self.searchCombo = ttk.Combobox(setupSection, textvariable=self.searchResultText, width=26, state="readonly")
        self.searchCombo.grid(row=10, column=0, columnspan=2, sticky="we", pady=(0, 8))
        self.searchCombo.bind("<<ComboboxSelected>>", lambda event: self._selectSteamSearchResult())

    def _addSidebarSection(self, row: int, key: str, title: str, description: str) -> ttk.Frame:
        labelText = tk.StringVar(value=f"[+] {title}")
        self.sidebarSectionLabels[key] = labelText
        self.sidebarSectionVisible[key] = False
        ttk.Separator(self.sidebar).grid(row=row, column=0, columnspan=2, sticky="we", pady=(14, 10))
        ModernButton(self.sidebar, textvariable=labelText, command=lambda: self._toggleSidebarSection(key, title), background="#1a2228", width=244).grid(row=row + 1, column=0, columnspan=2, sticky="we")
        body = ttk.Frame(self.sidebar, style="Panel.TFrame")
        body.grid(row=row + 2, column=0, columnspan=2, sticky="we", pady=(8, 0))
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        ttk.Label(body, text=description, style="PanelMuted.TLabel", wraplength=260).grid(row=0, column=0, columnspan=2, sticky="we")
        body.grid_remove()
        self.sidebarSections[key] = body
        return body

    def _toggleSidebarSection(self, key: str, title: str) -> None:
        section = self.sidebarSections[key]
        isVisible = self.sidebarSectionVisible[key]
        if isVisible:
            section.grid_remove()
            self.sidebarSectionLabels[key].set(f"[+] {title}")
        else:
            section.grid()
            self.sidebarSectionLabels[key].set(f"[-] {title}")
        self.sidebarSectionVisible[key] = not isVisible
        self._updateSidebarScrollregion()

    def _toggleSidebar(self) -> None:
        if self.sidebarVisible:
            self.sidebarContainer.grid_remove()
            self.optionsButtonText.set("Opciones")
        else:
            self.sidebarContainer.grid(row=1, column=1, sticky="nsew")
            self.optionsButtonText.set("Ocultar opciones")
        self.sidebarVisible = not self.sidebarVisible

    def _showHelp(self) -> None:
        messagebox.showinfo(helpTitle, helpText)

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

    def _toggleDeviceDetails(self) -> None:
        self.deviceDetailsVisible = not self.deviceDetailsVisible
        self._renderDeviceDetails()

    def _renderDeviceDetails(self) -> None:
        label = self.selectedDeviceText.get()
        rootPath = self.deviceOptions.get(label)
        if rootPath is None:
            self.deviceDetailsText.set("")
            self.deviceDetailsLabel.grid_remove()
            return
        device = self.deviceScanner.scan().get(rootPath)
        if device is None:
            self.deviceDetailsText.set("El disco seleccionado ya no esta disponible.")
        else:
            self.deviceDetailsText.set(f"Ruta: {device.rootPath}\nSerial: {device.volumeSerialNumber}\nCapacidad: {formatCapacity(device.capacityBytes)}")
        if self.deviceDetailsVisible:
            self.deviceDetailsLabel.grid(row=4, column=0, columnspan=2, sticky="we", pady=(0, 10))
        else:
            self.deviceDetailsLabel.grid_remove()

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
        for state in self.sessionService.handleExisting(self.deviceScanner.scan()):
            self._render(state, showPopup=False)

    def _poll(self) -> None:
        snapshot = self.monitor.pollOnce()
        for change in snapshot.removed:
            for state in self.sessionService.handleRemoved(change):
                self._render(state)
        for change in snapshot.inserted:
            if self.sessionService.isBlockedByActiveCartridge(change):
                message = statusPopupMessageFromBlockedCartridge(str(change.root))
                self._showStatusPopup(message)
                self._addActivity("Cartucho ignorado: ya hay un cartucho activo.", message.key)
                continue
            for state in self.sessionService.handleInserted(change):
                self._render(state)
        self._renderRuntimeStatus()
        self.root.after(self.intervalMilliseconds, self._poll)

    def _render(self, state: AppState, showPopup: bool = True) -> None:
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
        self.openButton.configure(state=buttonState)
        self.installButton.configure(state=buttonState)
        self.autoButton.configure(state=buttonState)
        self.slotPlayButton.configure(state=buttonState)
        self.slotInstallButton.configure(state=buttonState)
        self._syncSelectedActionButtons()
        self._renderSlot(state)
        self._syncRegistryFromReadyState(state)
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
        runtimeState = LauncherState.GAME_RUNNING if runtimeStatus.phase == "running" else LauncherState.OPENING if runtimeStatus.action == "open" else LauncherState.NOT_INSTALLED
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

    def _syncRegistryFromReadyState(self, state: AppState) -> None:
        if state.state != LauncherState.READY or state.manifest is None or state.rootPath is None:
            return
        device = self.deviceScanner.scan().get(state.rootPath)
        if device is None:
            return
        self.registry.upsert(RegisteredCartridge(state.manifest.cartridgeId, state.manifest.appId, device.volumeSerialNumber, device.capacityBytes, state.manifest.displayName))

    def _onCardsCanvasConfigure(self, event) -> None:
        self.cardsCanvas.itemconfigure(self.cardsCanvasWindow, width=event.width)
        self._renderLibraryCards(event.width)

    def _refreshLibrary(self) -> None:
        activeCartridgeId = self.currentState.cartridgeId if self.currentState.state == LauncherState.READY else None
        self.libraryCards = libraryCardsWithState(self.registry.all(), activeCartridgeId)
        self._renderLibraryCards(max(self.cardsCanvas.winfo_width(), 1))

    def _renderLibraryCards(self, availableWidth: int) -> None:
        for child in self.cardsFrame.winfo_children():
            child.destroy()
        columnCount = max(1, availableWidth // 190)
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
        if cartridge is None:
            return
        detail = libraryDetailFromRegistry(cartridge)
        self.selectedAppId = detail.appId
        self.selectedCartridgeId = detail.cartridgeId
        self.selectedGameTitleText.set(detail.title)
        self.selectedGameDetailText.set(librarySelectionSummary(detail))
        self.selectedGameAdvancedText.set(libraryAdvancedDetails(detail))
        if self.selectedGameAdvancedVisible:
            self.selectedGameAdvancedLabel.grid(row=4, column=0, columnspan=2, sticky="we", pady=(0, 8))
        self._syncSelectedActionButtons()

    def _toggleSelectedGameAdvancedDetails(self) -> None:
        self.selectedGameAdvancedVisible = not self.selectedGameAdvancedVisible
        if self.selectedGameAdvancedVisible and self.selectedGameAdvancedText.get():
            self.selectedGameAdvancedLabel.grid(row=4, column=0, columnspan=2, sticky="we", pady=(0, 8))
        else:
            self.selectedGameAdvancedLabel.grid_remove()

    def _deleteSelectedLibraryCard(self) -> None:
        if self.selectedCartridgeId is None:
            self.actionText.set("Selecciona un juego de la biblioteca.")
            return
        cartridge = self.registry.get(self.selectedCartridgeId)
        if cartridge is None:
            self.actionText.set("Ese registro ya no existe.")
            self.selectedCartridgeId = None
            self.selectedAppId = None
            self._syncSelectedActionButtons()
            self._refreshLibrary()
            return
        if not messagebox.askyesno("Eliminar registro", f"Eliminar {cartridge.displayName or cartridge.appId} de la biblioteca local?\n\nEsto no borra archivos del SSD."):
            return
        if self.registry.delete(cartridge.cartridgeId):
            self.actionText.set("Registro eliminado de la biblioteca.")
            self.selectedCartridgeId = None
            self.selectedAppId = None
            self.selectedGameTitleText.set("Selecciona un juego")
            self.selectedGameDetailText.set("Elige una portada para ver acciones y detalles.")
            self.selectedGameAdvancedText.set("")
            self.selectedGameAdvancedLabel.grid_remove()
            self._syncSelectedActionButtons()
            self._refreshLibrary()

    def _refreshDevices(self, showResult: bool = True) -> None:
        devices = self.deviceScanner.scan()
        self.deviceOptions = {f"{device.rootPath} ({device.volumeSerialNumber})": root for root, device in devices.items()}
        self.deviceCombo["values"] = tuple(self.deviceOptions.keys())
        if self.deviceOptions and self.selectedDeviceText.get() not in self.deviceOptions:
            self.selectedDeviceText.set(next(iter(self.deviceOptions)))
        if showResult:
            self.actionText.set(f"Discos detectados: {len(self.deviceOptions)}")
        self._renderDeviceDetails()

    def _searchSteamGame(self) -> None:
        term = self.createDisplayNameText.get().strip()
        if not term:
            self.actionText.set("Escribe un nombre para buscar.")
            return
        try:
            results = self.steamSearchClient.search(term)
        except Exception:
            self.actionText.set("Busqueda de Steam no disponible.")
            return
        self.searchResults = {steamSearchResultLabel(result): result for result in results}
        self.searchCombo["values"] = tuple(self.searchResults.keys())
        if self.searchResults:
            self.searchResultText.set(next(iter(self.searchResults)))
            self._selectSteamSearchResult()

    def _selectSteamSearchResult(self) -> None:
        result = self.searchResults.get(self.searchResultText.get())
        if result is not None:
            self.createDisplayNameText.set(result.displayName)
            self.createAppIdText.set(result.appId)

    def _createCartridge(self) -> None:
        rootPath = self.deviceOptions.get(self.selectedDeviceText.get())
        if rootPath is None:
            self.actionText.set("Selecciona un SSD.")
            return
        try:
            manifest = CartridgeCreationService(self.security, self.registry, self.deviceScanner).create(Path(rootPath), self.createDisplayNameText.get(), self.createAppIdText.get())
            self.actionText.set(f"Cartucho creado: {manifest.displayName}")
            self._refreshLibrary()
        except CartridgeError as exc:
            friendly = friendlyErrorFromCode(exc.code)
            self.actionText.set(f"{friendly.title}: {friendly.message}")

    def _updateCartridge(self) -> None:
        rootPath = self.deviceOptions.get(self.selectedDeviceText.get())
        if rootPath is None:
            self.actionText.set("Selecciona un SSD.")
            return
        try:
            manifest = CartridgeUpdateService(self.security, self.registry, self.deviceScanner).update(Path(rootPath), self.createDisplayNameText.get(), self.createAppIdText.get())
            self.actionText.set(f"Juego cambiado: {manifest.displayName}")
            self._refreshLibrary()
        except CartridgeError as exc:
            friendly = friendlyErrorFromCode(exc.code)
            self.actionText.set(f"{friendly.title}: {friendly.message}")

    def _runSteamAction(self, steamAction: str) -> None:
        state = self.currentState
        if state.state != LauncherState.READY or state.manifest is None:
            self.actionText.set("No hay cartucho listo.")
            return
        action = "open" if steamAction == "auto" else steamAction
        self._showSteamAction(state.manifest.displayName, action)
        try:
            if steamAction == "open":
                self.steamIntegration.openGame(state.manifest.appId)
                if self.steamIntegration.waitForGameLaunch(state.manifest.appId, time.time()):
                    self.actionText.set(f"Juego iniciado: {state.manifest.displayName}")
                    return
            elif steamAction == "install":
                self.steamIntegration.installGame(state.manifest.appId)
            else:
                libraryRoot = Path(state.rootPath) / state.manifest.libraryPath if state.rootPath is not None else None
                action = self.steamIntegration.runAutoAction(state.manifest.appId, libraryRoot)
                if action == "open" and self.steamIntegration.waitForGameLaunch(state.manifest.appId, time.time()):
                    self.actionText.set(f"Juego iniciado: {state.manifest.displayName}")
                    return
            self._finishSteamAction(state.manifest.displayName, action)
        except Exception as exc:
            self.logger.warning("UI Steam action failed: %s", exc)
            self.actionText.set("Steam no pudo completar la accion. Intenta de nuevo.")

    def _runSelectedSteamAction(self, steamAction: str) -> None:
        if self.selectedAppId is None or self.selectedCartridgeId is None:
            self.actionText.set("Selecciona un juego de la biblioteca.")
            return
        if not self._selectedCartridgeIsActive():
            self.actionText.set("Conecta este SSD para abrir o instalar el juego.")
            return
        displayName = self.selectedGameTitleText.get()
        self._showSteamAction(displayName, steamAction)
        try:
            if steamAction == "open":
                self.steamIntegration.openGame(self.selectedAppId)
                if self.steamIntegration.waitForGameLaunch(self.selectedAppId, time.time()):
                    self.actionText.set(f"Juego iniciado: {displayName}")
                    return
            else:
                self.steamIntegration.installGame(self.selectedAppId)
            self._finishSteamAction(displayName, steamAction)
        except Exception as exc:
            self.logger.warning("UI Steam action failed: %s", exc)
            self.actionText.set("Steam no pudo completar la accion. Intenta de nuevo.")

    def _showSteamAction(self, displayName: str, steamAction: str) -> None:
        self.actionText.set(f"Abriendo juego: {displayName}" if steamAction == "open" else f"Instalando juego: {displayName}")

    def _finishSteamAction(self, displayName: str, steamAction: str) -> None:
        self.actionText.set(f"Juego abierto: {displayName}" if steamAction == "open" else f"Instalacion enviada: {displayName}")

    def _showStatusPopup(self, message: StatusPopupMessage) -> None:
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

    def _selectedCartridgeIsActive(self) -> bool:
        return self.selectedCartridgeId is not None and self.currentState.state == LauncherState.READY and self.currentState.cartridgeId == self.selectedCartridgeId

    def _syncSelectedActionButtons(self) -> None:
        if not hasattr(self, "selectedOpenButton"):
            return
        state = "normal" if self._selectedCartridgeIsActive() else "disabled"
        self.selectedOpenButton.configure(state=state)
        self.selectedInstallButton.configure(state=state)


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
    if runtimeStatus.phase == "running":
        return f"Steam inicio {runtimeStatus.displayName}."
    if runtimeStatus.phase == "sending":
        return f"Abriendo juego: {runtimeStatus.displayName}"
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

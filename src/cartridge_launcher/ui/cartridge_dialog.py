from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import ttk

from cartridge_launcher.domain.errors import CartridgeError, ErrorCode
from cartridge_launcher.domain.manifest import manifestFromBytes, MAX_MANIFEST_BYTES, MAX_STEAM_APP_ID
from cartridge_launcher.services.cartridge_creation_service import CartridgeCreationService
from cartridge_launcher.services.cartridge_update_service import CartridgeUpdateService
from cartridge_launcher.services.cartridge_repair_service import CartridgeRepairService
from cartridge_launcher.services.cartridge_conversion_service import CartridgeConversionService
from cartridge_launcher.ui.modern_button import ModernButton


TITLES = {"create": "Crear cartucho", "update": "Actualizar cartucho", "repair": "Reparar cartucho",
          "convert": "Preparar para usar en cualquier PC"}


class CartridgeDialog:
    def __init__(self, parent, operation, security, registry, scanner, searchClient, tasks, onSuccess, onClosed):
        self.operation = operation
        self.security, self.registry, self.scanner = security, registry, scanner
        self.searchClient, self.tasks = searchClient, tasks
        self.onSuccess, self.onClosed = onSuccess, onClosed
        self.closed = False
        self.busy = False
        self.reading = False
        self.revision = 0
        self.searchRevision = 0
        self.devices = {}
        self.selectedDevice = None
        self.results = {}
        self.pollId = None
        self.window = tk.Toplevel(parent)
        self.window.withdraw()
        self.window.title(TITLES[operation])
        self.window.configure(bg="#1a2228")
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.bind("<Escape>", lambda event: self.close())
        self.window.bind("<Destroy>", self._destroyed, add="+")
        self.deviceText = tk.StringVar(self.window)
        self.nameText = tk.StringVar(self.window)
        self.appIdText = tk.StringVar(self.window)
        self.queryText = tk.StringVar(self.window)
        self.resultText = tk.StringVar(self.window)
        self.currentText = tk.StringVar(self.window, value="Selecciona un SSD para continuar.")
        self.messageText = tk.StringVar(self.window)
        self.repairConfirmed = tk.BooleanVar(self.window, value=False)
        self.gameInputs = []
        try:
            self._build()
            self.queryText.trace_add("write", self._queryChanged)
        except Exception:
            self.window.destroy()
            raise

    def _label(self, text, row):
        ttk.Label(self.body, text=text, style="Panel.TLabel").grid(row=row, column=0, columnspan=2, sticky="w", pady=(10, 4))

    def _entry(self, variable, row, columnspan=2):
        entry = tk.Entry(self.body, textvariable=variable, bg="#20282f", fg="#f4f7f5",
                         insertbackground="#f4f7f5", relief="flat", font=("Segoe UI", 11),
                         disabledbackground="#20282f", disabledforeground="#8d9994")
        entry.grid(row=row, column=0, columnspan=columnspan, sticky="we", ipady=7, padx=(0, 6))
        self.gameInputs.append(entry)
        return entry

    def _build(self):
        outer = ttk.Frame(self.window, style="Panel.TFrame", padding=18)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)
        ttk.Label(outer, text=TITLES[self.operation], style="Panel.TLabel", font=("Segoe UI", 17, "bold"),
                  wraplength=480).grid(row=0, column=0, sticky="we", pady=(0, 12))
        area = ttk.Frame(outer, style="Panel.TFrame")
        area.grid(row=1, column=0, sticky="nsew")
        area.columnconfigure(0, weight=1)
        area.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(area, bg="#1a2228", highlightthickness=0, width=480, height=350)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(area, orient="vertical", command=self.canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.body = ttk.Frame(self.canvas, style="Panel.TFrame")
        self.body.columnconfigure(0, weight=1)
        self.body.columnconfigure(1, weight=0)
        bodyId = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind("<Configure>", lambda event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        def resizeBody(event):
            self.canvas.itemconfigure(bodyId, width=event.width)
            for child in self.body.winfo_children():
                if isinstance(child, ttk.Label):
                    child.configure(wraplength=max(120, event.width - 12))
        self.canvas.bind("<Configure>", resizeBody)
        self.window.bind("<MouseWheel>", self._wheel)
        self._label("1. Selecciona el SSD", 0)
        self.deviceCombo = ttk.Combobox(self.body, textvariable=self.deviceText, state="readonly", style="Modern.TCombobox", width=32)
        self.deviceCombo.grid(row=1, column=0, sticky="we", padx=(0, 8))
        self.deviceCombo.bind("<<ComboboxSelected>>", self._selectDevice)
        self.refreshButton = ModernButton(self.body, text="Actualizar", command=self._scanDevices, background="#1a2228", width=100)
        self.refreshButton.grid(row=1, column=1)
        ttk.Label(self.body, textvariable=self.currentText, style="PanelMuted.TLabel", wraplength=440).grid(row=2, column=0, columnspan=2, sticky="we", pady=(8, 8))
        if self.operation == "convert":
            ttk.Label(self.body, text="Prepara un cartucho antiguo para compartirlo entre PCs. Su origen anterior puede no verificarse aquí. Conserva el juego y crea un respaldo; no necesitas elegir otro juego.",
                      style="PanelMuted.TLabel", wraplength=440).grid(row=3, column=0, columnspan=2, sticky="we", pady=12)
        else:
            self._label("2. Elige el juego" if self.operation != "repair" else "2. Revisa el juego del cartucho", 3)
            query = self._entry(self.queryText, 4, columnspan=1)
            query.bind("<Return>", lambda event: self._search())
            self.searchButton = ModernButton(self.body, text="Buscar", command=self._search, background="#1a2228", width=100)
            self.searchButton.grid(row=4, column=1)
            self.gameInputs.append(self.searchButton)
            self.searchCombo = ttk.Combobox(self.body, textvariable=self.resultText, state="readonly", style="Modern.TCombobox")
            self.searchCombo.grid(row=5, column=0, columnspan=2, sticky="we", pady=(8, 0))
            self.searchCombo.bind("<<ComboboxSelected>>", self._selectResult)
            self.gameInputs.append(self.searchCombo)
            self._label("Nombre del juego (también puedes escribirlo)", 6)
            self._entry(self.nameText, 7)
            self._label("Steam AppID", 8)
            self._entry(self.appIdText, 9)
        if self.operation == "repair":
            ttk.Label(self.body, text="La reparación reconstruye la autorización y desactiva metadata ejecutable. Conserva un respaldo y no borra el juego.",
                      style="PanelMuted.TLabel", wraplength=440).grid(row=10, column=0, columnspan=2, sticky="we", pady=(12, 6))
            self.repairCheck = ttk.Checkbutton(self.body, text="Confirmo que quiero reparar este cartucho", variable=self.repairConfirmed)
            self.repairCheck.grid(row=11, column=0, columnspan=2, sticky="w", pady=(0, 10))
            self.gameInputs.append(self.repairCheck)
        footer = ttk.Frame(outer, style="Panel.TFrame")
        footer.grid(row=2, column=0, sticky="we", pady=(12, 0))
        footer.columnconfigure(0, weight=1)
        ttk.Label(footer, textvariable=self.messageText, style="PanelMuted.TLabel", wraplength=460).grid(row=0, column=0, columnspan=2, sticky="we", pady=(0, 10))
        self.cancelButton = ModernButton(footer, text="Cancelar", command=self.close, background="#1a2228", width=105)
        self.cancelButton.grid(row=1, column=0, sticky="e", padx=(0, 8))
        self.confirmButton = ModernButton(footer, text="Preparar cartucho" if self.operation == "convert" else TITLES[self.operation],
            command=self.submit, variant="accent", background="#1a2228", width=190)
        self.confirmButton.grid(row=1, column=1)
        def resizeOuter(event):
            if event.widget == outer:
                for frame in (outer, footer):
                    for child in frame.winfo_children():
                        if isinstance(child, ttk.Label):
                            child.configure(wraplength=max(120, event.width - 36))
        outer.bind("<Configure>", resizeOuter)
        self._controls()

    def show(self):
        self.window.update_idletasks()
        parent = self.window.master
        width = min(560, self.window.winfo_screenwidth() - 40)
        height = min(640 if self.operation != "convert" else 420, self.window.winfo_screenheight() - 80)
        x = max(0, min(parent.winfo_rootx() + (parent.winfo_width() - width) // 2, self.window.winfo_screenwidth() - width))
        y = max(0, min(parent.winfo_rooty() + (parent.winfo_height() - height) // 2, self.window.winfo_screenheight() - height))
        self.window.geometry(f"{width}x{height}+{x}+{y}")
        self.window.minsize(min(420, width), min(360, height))
        self.window.deiconify()
        self.window.grab_set()
        self.deviceCombo.focus_set()
        self._scanDevices()
        self.pollId = self.window.after(1000, self._poll)

    def focus(self):
        if not self.closed:
            self.window.lift()
            self.window.focus_set()

    def _wheel(self, event):
        self.canvas.yview_scroll(-int(event.delta / 120), "units")
        return "break"

    def _controls(self):
        enabled = self.selectedDevice is not None and not self.busy and not self.reading
        self.deviceCombo.configure(state="disabled" if self.busy else "readonly")
        self.refreshButton.configure(state="disabled" if self.busy else "normal")
        self.cancelButton.configure(state="disabled" if self.busy else "normal")
        self.confirmButton.configure(state="normal" if enabled else "disabled")
        for widget in self.gameInputs:
            widget.configure(state=("readonly" if isinstance(widget, ttk.Combobox) else "normal") if enabled else "disabled")

    def _poll(self):
        if not self.closed:
            if not self.busy:
                self._scanDevices()
            self.pollId = self.window.after(1000, self._poll)

    def _scanDevices(self):
        if self.closed or self.busy:
            return
        def done(devices):
            if self.closed or self.busy:
                return
            self.devices = {f"{device.rootPath} · {device.capacityBytes // (1024**3)} GB": device for device in devices.values()}
            self.deviceCombo["values"] = tuple(self.devices)
            if self.selectedDevice is not None and self.devices.get(self.deviceText.get()) != self.selectedDevice:
                self.deviceText.set("")
                self._selectDevice()
                self.messageText.set("El SSD se desconectó o cambió. Selecciónalo de nuevo.")
        def failed(exc):
            if not self.closed and not self.busy:
                self.messageText.set("No se pudieron explorar los discos. Pulsa Actualizar para reintentar.")
        self.tasks.submit(("dialog-devices", id(self)), self.scanner.scan, done, failed)

    def _selectDevice(self, event=None):
        if self.closed or self.busy:
            return
        self.revision += 1
        revision = self.revision
        self.selectedDevice = self.devices.get(self.deviceText.get())
        self.nameText.set("")
        self.appIdText.set("")
        self.queryText.set("")
        self.repairConfirmed.set(False)
        self.messageText.set("")
        self.reading = self.selectedDevice is not None and self.operation != "create"
        self.currentText.set("Leyendo cartucho…" if self.reading else "Selecciona un SSD para continuar." if self.selectedDevice is None else "SSD seleccionado. Ahora elige el juego.")
        self._controls()
        if not self.reading:
            return
        root = Path(self.selectedDevice.rootPath)
        def read():
            path = root / ".cartridge" / "manifest.json"
            if path.stat().st_size > MAX_MANIFEST_BYTES:
                raise ValueError("Manifiesto demasiado grande")
            return manifestFromBytes(path.read_bytes())
        def done(manifest):
            if self.closed or self.busy or revision != self.revision:
                return
            self.reading = False
            self.currentText.set(f"Juego actual: {manifest.displayName} (AppID {manifest.appId})")
            if self.operation == "repair":
                self.nameText.set(manifest.displayName)
                self.appIdText.set(manifest.appId)
            self._controls()
        def failed(exc):
            if self.closed or self.busy or revision != self.revision:
                return
            self.reading = False
            self.currentText.set("No se pudo leer el juego actual." + (" Completa los datos para reparar." if self.operation == "repair" else ""))
            self._controls()
        self.tasks.submit(("dialog-read", id(self), revision), read, done, failed)

    def _queryChanged(self, *args):
        self.searchRevision += 1
        self.results = {}
        self.resultText.set("")
        if hasattr(self, "searchCombo"):
            self.searchCombo["values"] = ()

    def _search(self):
        if self.closed or self.busy or self.selectedDevice is None or self.reading:
            return
        query = self.queryText.get().strip()
        if not query:
            self.messageText.set("Escribe un nombre para buscar o completa nombre y AppID manualmente.")
            return
        revision = self.searchRevision
        self.messageText.set("Buscando juegos…")
        def done(results):
            if self.closed or self.busy or revision != self.searchRevision:
                return
            self.results = {f"{result.displayName} ({result.appId})": result for result in results}
            self.searchCombo["values"] = tuple(self.results)
            self.messageText.set("Selecciona un resultado." if results else "No se encontraron juegos. Puedes escribir nombre y AppID.")
        def failed(exc):
            if not self.closed and not self.busy and revision == self.searchRevision:
                self.messageText.set("Búsqueda no disponible. Puedes escribir nombre y AppID.")
        self.tasks.submit(("search", id(self), revision), lambda: self.searchClient.search(query), done, failed)

    def _selectResult(self, event=None):
        if self.busy or self.closed:
            return
        result = self.results.get(self.resultText.get())
        if result:
            self.nameText.set(result.displayName)
            self.appIdText.set(result.appId)

    def submit(self):
        if self.closed or self.busy or self.reading:
            return
        device = self.selectedDevice
        if device is None:
            self.messageText.set("Selecciona el SSD que quieres usar.")
            return
        name, appId = self.nameText.get().strip(), self.appIdText.get().strip()
        if self.operation != "convert" and (not name or not appId.isascii() or not appId.isdigit() or len(appId) > 10 or not 0 < int(appId) <= MAX_STEAM_APP_ID):
            self.messageText.set("Completa el nombre y un Steam AppID válido.")
            return
        if self.operation == "repair" and not self.repairConfirmed.get():
            self.messageText.set("Marca la confirmación de reparación para continuar.")
            return
        self.busy = True
        self.searchRevision += 1
        self.messageText.set("Guardando cartucho… Espera antes de desconectar el SSD.")
        self._controls()
        def work():
            root = Path(device.rootPath)
            if self.scanner.findDeviceByRoot(root) != device:
                raise CartridgeError(ErrorCode.DEVICE_REMOVED, "El SSD se desconectó o fue reemplazado. Selecciónalo de nuevo.")
            service = {"create": CartridgeCreationService, "update": CartridgeUpdateService,
                       "repair": CartridgeRepairService, "convert": CartridgeConversionService}[self.operation](self.security, self.registry, self.scanner)
            return service.convert(root) if self.operation == "convert" else getattr(service, self.operation)(root, name, appId)
        def done(manifest):
            if self.closed:
                return
            self.busy = False
            self.close()
            self.onSuccess(manifest)
        if not self.tasks.submit(("dialog-write", id(self)), work, done, self._failed):
            self._failed(RuntimeError("Hay una operación pendiente. Intenta de nuevo."))

    def _failed(self, exc):
        if self.closed:
            return
        self.busy = False
        self.messageText.set(str(exc))
        self._controls()

    def close(self):
        if self.closed:
            return True
        if self.busy:
            self.messageText.set("La escritura está en curso. Espera a que termine para cerrar.")
            return False
        self.window.destroy()
        return True

    def _destroyed(self, event):
        if event.widget != self.window or self.closed:
            return
        self.closed = True
        self.revision += 1
        self.searchRevision += 1
        if self.pollId is not None:
            self.window.after_cancel(self.pollId)
            self.pollId = None
        try:
            self.window.grab_release()
            self.window.master.focus_set()
        except tk.TclError:
            pass
        self.onClosed()

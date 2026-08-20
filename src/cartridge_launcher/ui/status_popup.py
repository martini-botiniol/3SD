from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from cartridge_launcher.ui.app_icon import appIconPath
from cartridge_launcher.ui.modern_button import ModernButton
from cartridge_launcher.ui.popup_dedupe import shouldShowPopupKey
from cartridge_launcher.ui.status_messages import StatusPopupMessage


class StatusPopup:
    def __init__(self, root: tk.Tk, openLibrary: Callable[[], None] | None = None):
        self.root = root
        self.openLibrary = openLibrary
        self.window: tk.Toplevel | None = None
        self.titleText = tk.StringVar()
        self.messageText = tk.StringVar()
        self.dismissAfterId: str | None = None
        self.activeKey: str | None = None

    def show(self, message: StatusPopupMessage) -> None:
        messageKey = message.key or f"{message.title}:{message.message}"
        if self.window is not None and self.window.winfo_exists() and self.activeKey == messageKey:
            return
        if message.key and not message.key.startswith(("steam:action:", "NOT_INSERTED:")) and not shouldShowPopupKey(message.key):
            return

        if self.window is None or not self.window.winfo_exists():
            self._build()
        self.activeKey = messageKey
        self.titleText.set(message.title)
        self.messageText.set(message.message)
        self._position()
        self.window.deiconify()
        self.window.lift()
        self.window.attributes("-topmost", True)
        if self.dismissAfterId is not None:
            self.window.after_cancel(self.dismissAfterId)
            self.dismissAfterId = None
        if message.dismissAfterMilliseconds is not None:
            self.dismissAfterId = self.window.after(message.dismissAfterMilliseconds, self.dismiss)

    def dismiss(self) -> None:
        if self.window is not None and self.dismissAfterId is not None:
            self.window.after_cancel(self.dismissAfterId)
            self.dismissAfterId = None
        if self.window is not None and self.window.winfo_exists():
            self.window.destroy()
        self.window = None
        self.activeKey = None

    def restoreRoot(self) -> None:
        self.dismiss()
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def openLibraryFromPopup(self) -> None:
        self.dismiss()
        if self.openLibrary is not None:
            self.openLibrary()
            return
        self.restoreRoot()

    def _build(self) -> None:
        window = tk.Toplevel(self.root)
        self.window = window
        window.title("3SD")
        window.configure(bg="#1c2024")
        window.attributes("-topmost", True)
        window.resizable(False, False)
        window.protocol("WM_DELETE_WINDOW", self.dismiss)
        self._applyWindowIcon(window)
        frame = ttk.Frame(window, style="Panel.TFrame", padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, textvariable=self.titleText, style="Panel.TLabel", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(frame, textvariable=self.messageText, style="PanelMuted.TLabel", wraplength=280).pack(anchor="w", pady=(6, 12))
        actions = ttk.Frame(frame, style="Panel.TFrame")
        actions.pack(fill="x")
        ModernButton(actions, text="Ocultar", command=self.dismiss, background="#1c2024", width=100).pack(side="right")
        ModernButton(actions, text="Abrir biblioteca", command=self.openLibraryFromPopup, variant="accent", background="#1c2024", width=142).pack(side="right", padx=(0, 8))

    def _position(self) -> None:
        if self.window is None:
            return
        self.window.update_idletasks()
        self.window.geometry(centeredGeometry(self.window.winfo_screenwidth(), self.window.winfo_screenheight(), 380, self.window.winfo_reqheight()))

    def _applyWindowIcon(self, window: tk.Toplevel) -> None:
        iconPath = appIconPath()
        if iconPath is None:
            return
        try:
            window.iconbitmap(str(iconPath))
        except tk.TclError:
            pass


def centeredGeometry(screenWidth: int, screenHeight: int, width: int, height: int) -> str:
    x = max(0, (screenWidth - width) // 2)
    y = max(0, (screenHeight - height) // 2)
    return f"{width}x{height}+{x}+{y}"

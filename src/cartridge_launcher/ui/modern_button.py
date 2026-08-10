from __future__ import annotations

import tkinter as tk
from collections.abc import Callable


class ModernButton(tk.Canvas):
    PALETTE = {
        "accent": {"normal": "#49b86f", "hover": "#5fd183", "pressed": "#3a965a", "disabled": "#26332b", "text": "#07120b", "disabledText": "#8d9994"},
        "quiet": {"normal": "#26323a", "hover": "#34434c", "pressed": "#1d272e", "disabled": "#20282e", "text": "#dce5e0", "disabledText": "#8d9994"},
    }

    def __init__(self, master, text: str = "", command: Callable[[], None] | None = None, variant: str = "quiet", background: str = "#0f1418", textvariable: tk.StringVar | None = None, width: int = 116, height: int = 38, radius: int = 10):
        super().__init__(master, width=width, height=height, bg=background, bd=0, highlightthickness=0, relief="flat", cursor="hand2", takefocus=True)
        self.command = command
        self.variant = variant if variant in self.PALETTE else "quiet"
        self._text = text
        self.textvariable = textvariable
        self.state = "normal"
        self.radius = radius
        self.isHovering = False
        self.isPressed = False
        self._variableTraceId: str | None = None
        if self.textvariable is not None:
            self._text = self.textvariable.get()
            self._variableTraceId = self.textvariable.trace_add("write", self._onTextVariableChanged)
        self.bind("<Configure>", lambda event: self._draw())
        self.bind("<Enter>", self._onEnter)
        self.bind("<Leave>", self._onLeave)
        self.bind("<ButtonPress-1>", self._onPress)
        self.bind("<ButtonRelease-1>", self._onRelease)
        self.bind("<Return>", self._onKeyboardActivate)
        self.bind("<space>", self._onKeyboardActivate)
        self.bind("<Destroy>", self._onDestroy)
        self._draw()

    def configure(self, cnf=None, **kw):  # noqa: ANN001
        if cnf:
            kw.update(cnf)
        if "state" in kw:
            self.state = kw.pop("state")
            super().configure(cursor="" if self.state == "disabled" else "hand2")
        if "text" in kw:
            self._text = kw.pop("text")
        if "command" in kw:
            self.command = kw.pop("command")
        if "background" in kw:
            super().configure(bg=kw.pop("background"))
        if "variant" in kw:
            variant = kw.pop("variant")
            self.variant = variant if variant in self.PALETTE else self.variant
        result = super().configure(**kw) if kw else None
        self._draw()
        return result

    config = configure

    def _onTextVariableChanged(self, *_args) -> None:
        if self.textvariable is not None:
            self._text = self.textvariable.get()
            self._draw()

    def _onEnter(self, _event) -> None:
        if self.state != "disabled":
            self.isHovering = True
            self._draw()

    def _onLeave(self, _event) -> None:
        self.isHovering = False
        self.isPressed = False
        self._draw()

    def _onPress(self, _event) -> None:
        if self.state != "disabled":
            self.focus_set()
            self.isPressed = True
            self._draw()

    def _onRelease(self, event) -> None:
        if self.state == "disabled":
            return
        wasPressed = self.isPressed
        self.isPressed = False
        self._draw()
        if wasPressed and 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height() and self.command is not None:
            self.command()

    def _onKeyboardActivate(self, _event) -> str:
        if self.state != "disabled" and self.command is not None:
            self.command()
        return "break"

    def _onDestroy(self, _event) -> None:
        if self.textvariable is not None and self._variableTraceId is not None:
            try:
                self.textvariable.trace_remove("write", self._variableTraceId)
            except tk.TclError:
                pass

    def _draw(self) -> None:
        self.delete("all")
        width = max(self.winfo_width(), int(self["width"]))
        height = max(self.winfo_height(), int(self["height"]))
        palette = self.PALETTE[self.variant]
        if self.state == "disabled":
            fill, textFill = palette["disabled"], palette["disabledText"]
        elif self.isPressed:
            fill, textFill = palette["pressed"], palette["text"]
        elif self.isHovering:
            fill, textFill = palette["hover"], palette["text"]
        else:
            fill, textFill = palette["normal"], palette["text"]
        self._roundedRectangle(1, 1, width - 1, height - 1, self.radius, fill)
        self.create_text(width // 2, height // 2, text=self._text, fill=textFill, font=("Segoe UI", 10, "bold"), width=max(20, width - 18))

    def _roundedRectangle(self, x1: int, y1: int, x2: int, y2: int, radius: int, fill: str) -> None:
        radius = min(radius, max(0, (x2 - x1) // 2), max(0, (y2 - y1) // 2))
        points = [x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius, x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2, x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1]
        self.create_polygon(points, smooth=True, fill=fill, outline="")

from __future__ import annotations

from dataclasses import dataclass

from cartridge_launcher.app.state import AppState
from cartridge_launcher.domain.states import LauncherState


@dataclass(frozen=True)
class StatusPopupMessage:
    title: str
    message: str
    dismissAfterMilliseconds: int | None = None
    key: str = ""


def statusPopupMessageFromState(state: AppState) -> StatusPopupMessage | None:
    if state.state == LauncherState.VALIDATING:
        return StatusPopupMessage("Validando cartucho", state.rootPath or "Revisando SSD.", 1800, key=statusPopupKeyFromState(state) or "")
    if state.state == LauncherState.READY and state.manifest is not None:
        return StatusPopupMessage("Cartucho listo", f"{state.manifest.displayName} esta listo.", 1200, key=statusPopupKeyFromState(state) or "")
    if state.state == LauncherState.NOT_INSERTED and state.rootPath is not None:
        return StatusPopupMessage("Cartucho expulsado", f"El SSD cartucho fue expulsado.\n{state.rootPath}", key=statusPopupKeyFromState(state) or "")
    if state.errorCode is not None:
        return StatusPopupMessage("No se pudo usar el cartucho", state.message or state.errorCode.value, key=statusPopupKeyFromState(state) or "")
    return None


def statusPopupKeyFromState(state: AppState) -> str | None:
    if (
        state.state != LauncherState.VALIDATING
        and not (state.state == LauncherState.READY and state.manifest is not None)
        and not (state.state == LauncherState.NOT_INSERTED and state.rootPath is not None)
        and state.errorCode is None
    ):
        return None
    return f"{state.state.value}:{state.rootPath or ''}:{state.cartridgeId or ''}:{state.errorCode or ''}:{state.message}"


def statusPopupMessageFromSteamAction(displayName: str, steamAction: str, runId: str) -> StatusPopupMessage:
    title = "Abriendo juego" if steamAction == "open" else "Instalando juego"
    action = "abriendo" if steamAction == "open" else "preparando"
    return StatusPopupMessage(
        title,
        f"Steam esta {action} {displayName}.",
        key=f"steam:action:{displayName}:{steamAction}:{runId}",
    )


def statusPopupMessageFromBlockedCartridge(rootPath: str) -> StatusPopupMessage:
    return StatusPopupMessage(
        "Cartucho en espera",
        f"Ya hay un cartucho activo. Retira el actual para usar este SSD.\n{rootPath}",
        2400,
        key=f"cartridge:blocked:{rootPath}",
    )


def statusPopupDismissMessage() -> StatusPopupMessage:
    return StatusPopupMessage("", "", key="popup:dismiss")

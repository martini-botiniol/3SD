from __future__ import annotations

from dataclasses import dataclass

from cartridge_launcher.app.state import AppState
from cartridge_launcher.domain.models import RegisteredCartridge
from cartridge_launcher.domain.states import LauncherState
from cartridge_launcher.ui.error_messages import FriendlyError, friendlyErrorFromCode


FRIENDLY_LAUNCHER_STATE_NAMES = {
    LauncherState.NOT_INSERTED: "Sin cartucho",
    LauncherState.VALIDATING: "Validando",
    LauncherState.READY: "Listo",
    LauncherState.OPENING: "Abriendo",
    LauncherState.GAME_RUNNING: "Juego en ejecucion",
    LauncherState.NOT_INSTALLED: "No instalado",
    LauncherState.STEAM_REQUIRED: "Steam requerido",
    LauncherState.INVALID_CARTRIDGE: "Cartucho invalido",
    LauncherState.DEVICE_MISMATCH: "SSD no coincide",
    LauncherState.ERROR: "Error",
}


@dataclass(frozen=True)
class LauncherViewModel:
    title: str
    subtitle: str
    detail: str
    status: str
    canRunSteamAction: bool
    technicalDetail: str = ""
    friendlyError: FriendlyError | None = None


@dataclass(frozen=True)
class LibraryCardViewModel:
    cartridgeId: str
    displayName: str
    appId: str
    coverUrl: str
    statusText: str
    isActive: bool = False


@dataclass(frozen=True)
class LibraryDetailViewModel:
    title: str
    appId: str
    cartridgeId: str
    volumeSerialNumber: str
    capacityText: str
    statusText: str


def viewModelFromState(state: AppState) -> LauncherViewModel:
    if state.state == LauncherState.NOT_INSERTED:
        return LauncherViewModel("Listo para recibir un cartucho", "Conecta un SSD preparado para jugar.", state.message or "Cuando insertes un cartucho valido, lo veras aqui.", friendlyLauncherStateName(state.state), False)
    if state.state == LauncherState.VALIDATING:
        return LauncherViewModel("Validando cartucho", state.rootPath or "", "Revisando que el disco sea autentico y este listo para usarse.", friendlyLauncherStateName(state.state), False)
    if state.state == LauncherState.READY and state.manifest is not None:
        return LauncherViewModel(state.manifest.displayName, "Cartucho listo", "Puedes abrir el juego o dejar que Steam lo instale si hace falta.", friendlyLauncherStateName(state.state), True, f"{state.rootPath or ''} - Steam AppID {state.manifest.appId}")
    if state.state == LauncherState.OPENING and state.manifest is not None:
        return LauncherViewModel(state.manifest.displayName, "Iniciando juego", state.message or "Steam esta abriendo el juego.", friendlyLauncherStateName(state.state), False, f"{state.rootPath or ''} - Steam AppID {state.manifest.appId}")
    if state.state == LauncherState.NOT_INSTALLED and state.manifest is not None:
        return LauncherViewModel(state.manifest.displayName, "Instalando juego", state.message or "Steam esta preparando la instalacion.", friendlyLauncherStateName(state.state), False, f"{state.rootPath or ''} - Steam AppID {state.manifest.appId}")
    if state.errorCode is not None:
        friendlyError = friendlyErrorFromCode(state.errorCode)
        return LauncherViewModel(friendlyError.title, friendlyError.message, friendlyError.action, friendlyLauncherStateName(state.state), False, f"{state.errorCode}: {state.rootPath or ''} {state.message}".strip(), friendlyError)
    return LauncherViewModel(friendlyLauncherStateName(state.state), state.rootPath or "", state.message, friendlyLauncherStateName(state.state), False)


def friendlyLauncherStateName(state: LauncherState) -> str:
    return FRIENDLY_LAUNCHER_STATE_NAMES.get(state, state.value.replace("_", " ").title())


def libraryCardsFromRegistry(cartridges: tuple[RegisteredCartridge, ...]) -> tuple[LibraryCardViewModel, ...]:
    return libraryCardsWithState(cartridges)


def libraryCardsWithState(cartridges: tuple[RegisteredCartridge, ...], activeCartridgeId: str | None = None) -> tuple[LibraryCardViewModel, ...]:
    return tuple(
        LibraryCardViewModel(item.cartridgeId, cartridgeDisplayName(item), item.appId, steamLibraryCoverUrl(item.appId), "Insertado" if item.cartridgeId == activeCartridgeId else "No insertado", item.cartridgeId == activeCartridgeId)
        for item in sorted(cartridges, key=lambda value: (value.displayName or value.appId).lower())
    )


def libraryDetailFromRegistry(cartridge: RegisteredCartridge) -> LibraryDetailViewModel:
    return LibraryDetailViewModel(cartridgeDisplayName(cartridge), cartridge.appId, cartridge.cartridgeId, cartridge.volumeSerialNumber, formatCapacity(cartridge.capacityBytes), "Registrado")


def cartridgeDisplayName(cartridge: RegisteredCartridge) -> str:
    displayName = cartridge.displayName.strip()
    return displayName if displayName else "Juego sin nombre"


def librarySelectionSummary(detail: LibraryDetailViewModel) -> str:
    return f"Juego: {detail.title}\nEstado: {detail.statusText}"


def libraryAdvancedDetails(detail: LibraryDetailViewModel) -> str:
    return f"Steam AppID: {detail.appId}\nSerial del disco: {detail.volumeSerialNumber}\nCapacidad: {detail.capacityText}\nCartridge ID: {detail.cartridgeId}"


def steamLibraryCoverUrl(appId: str) -> str:
    return f"https://cdn.cloudflare.steamstatic.com/steam/apps/{appId}/library_600x900_2x.jpg"


def formatCapacity(capacityBytes: int) -> str:
    if capacityBytes <= 0:
        return "Desconocida"
    gibibytes = capacityBytes / (1024**3)
    if gibibytes >= 1024:
        return f"{gibibytes / 1024:.1f} TB"
    return f"{gibibytes:.1f} GB"

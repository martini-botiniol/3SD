from __future__ import annotations

from dataclasses import dataclass

from cartridge_launcher.domain.errors import ErrorCode
from cartridge_launcher.domain.models import CartridgeManifest
from cartridge_launcher.domain.states import LauncherState


@dataclass(frozen=True)
class AppState:
    state: LauncherState
    rootPath: str | None = None
    cartridgeId: str | None = None
    manifest: CartridgeManifest | None = None
    errorCode: ErrorCode | None = None
    message: str = ""

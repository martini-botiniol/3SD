from __future__ import annotations

import json
import logging
from pathlib import Path

from cartridge_launcher.domain.models import RegisteredCartridge
from cartridge_launcher.domain.errors import CartridgeError, ErrorCode
from cartridge_launcher.infrastructure.storage import atomicWrite, fileLock


class LocalRegistry:
    def __init__(self, path: Path):
        self.path = path
        self.warning: str | None = None

    def _read(self, path: Path) -> tuple[RegisteredCartridge, ...]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("cartridges"), list):
            raise ValueError("Invalid registry")
        result = tuple(RegisteredCartridge(**item) for item in payload["cartridges"])
        for item in result:
            if not isinstance(item.appId, str) or not item.appId.isascii() or not item.appId.isdigit() or len(item.appId) > 10:
                raise ValueError("Invalid registry AppID")
            if not 0 < int(item.appId) <= 4294967295:
                raise ValueError("Invalid registry AppID range")
            if not isinstance(item.cartridgeId, str) or not item.cartridgeId:
                raise ValueError("Invalid registry identity")
            if not isinstance(item.displayName, str) or not isinstance(item.volumeSerialNumber, str) or type(item.capacityBytes) is not int or item.capacityBytes < 0:
                raise ValueError("Invalid registry fields")
        return result

    def all(self) -> tuple[RegisteredCartridge, ...]:
        if not self.path.exists():
            return ()
        try:
            return self._read(self.path)
        except (OSError, ValueError, TypeError) as exc:
            self.warning = "Registro dañado: se utiliza el respaldo cuando esta disponible."
            logging.getLogger("3SD").warning(self.warning)
            try:
                return self._read(self.path.with_suffix(".json.bak"))
            except (OSError, ValueError, TypeError):
                raise CartridgeError(ErrorCode.STORAGE_ERROR, "Registro dañado sin respaldo valido; conserva registry.json para recuperarlo.") from exc

    def get(self, cartridgeId: str) -> RegisteredCartridge | None:
        return next((item for item in self.all() if item.cartridgeId == cartridgeId), None)

    def upsert(self, cartridge: RegisteredCartridge) -> None:
        with fileLock(self.path.with_suffix(".lock")):
            cartridges = [item for item in self.all() if item.cartridgeId != cartridge.cartridgeId]
            cartridges.append(cartridge)
            self._write(cartridges)

    def delete(self, cartridgeId: str) -> bool:
        with fileLock(self.path.with_suffix(".lock")):
            cartridges = list(self.all())
            filtered = [item for item in cartridges if item.cartridgeId != cartridgeId]
            if len(filtered) == len(cartridges):
                return False
            self._write(filtered)
            return True

    def _write(self, cartridges: list[RegisteredCartridge]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"cartridges": [item.__dict__ for item in sorted(cartridges, key=lambda value: value.cartridgeId)]}
        if self.path.exists():
            try:
                self._read(self.path)
                atomicWrite(self.path.with_suffix(".json.bak"), self.path.read_bytes())
            except (ValueError, TypeError):
                atomicWrite(self.path.with_suffix(".json.corrupt"), self.path.read_bytes())
        atomicWrite(self.path, json.dumps(payload, indent=2).encode("utf-8"))

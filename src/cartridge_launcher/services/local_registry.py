from __future__ import annotations

import json
import os
from pathlib import Path

from cartridge_launcher.domain.models import RegisteredCartridge


class LocalRegistry:
    def __init__(self, path: Path):
        self.path = path

    def all(self) -> tuple[RegisteredCartridge, ...]:
        if not self.path.is_file():
            return ()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            cartridges = payload.get("cartridges", []) if isinstance(payload, dict) else []
            if not isinstance(cartridges, list):
                return ()
            return tuple(RegisteredCartridge(**item) for item in cartridges if isinstance(item, dict))
        except (OSError, json.JSONDecodeError, TypeError):
            return ()

    def get(self, cartridgeId: str) -> RegisteredCartridge | None:
        return next((item for item in self.all() if item.cartridgeId == cartridgeId), None)

    def upsert(self, cartridge: RegisteredCartridge) -> None:
        cartridges = [item for item in self.all() if item.cartridgeId != cartridge.cartridgeId]
        cartridges.append(cartridge)
        self._write(cartridges)

    def delete(self, cartridgeId: str) -> bool:
        cartridges = list(self.all())
        filtered = [item for item in cartridges if item.cartridgeId != cartridgeId]
        if len(filtered) == len(cartridges):
            return False
        self._write(filtered)
        return True

    def _write(self, cartridges: list[RegisteredCartridge]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"cartridges": [item.__dict__ for item in sorted(cartridges, key=lambda value: value.cartridgeId)]}
        temporaryPath = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporaryPath.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(temporaryPath, self.path)

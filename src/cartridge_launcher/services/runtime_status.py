from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from cartridge_launcher.infrastructure.storage import atomicWrite


RUNTIME_STATUS_TTL_SECONDS = 4.0


@dataclass(frozen=True)
class RuntimeStatus:
    cartridgeId: str
    appId: str
    displayName: str
    action: str
    phase: str
    timestamp: float


class RuntimeStatusStore:
    def __init__(self, path: Path):
        self.path = path

    def write(self, status: RuntimeStatus) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        atomicWrite(self.path, json.dumps(status.__dict__).encode("utf-8"))

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)

    def read(self) -> RuntimeStatus | None:
        if not self.path.is_file():
            return None
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            status = RuntimeStatus(**payload)
        except (OSError, json.JSONDecodeError, TypeError):
            return None
        if time.time() - status.timestamp > RUNTIME_STATUS_TTL_SECONDS:
            return None
        return status


def defaultRuntimeStatusStore() -> RuntimeStatusStore:
    return RuntimeStatusStore(Path.home() / ".3sd" / "runtime-status.json")

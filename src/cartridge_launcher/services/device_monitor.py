from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cartridge_launcher.domain.models import DeviceInfo


@dataclass(frozen=True)
class DeviceChange:
    root: Path
    device: DeviceInfo


@dataclass(frozen=True)
class DeviceSnapshot:
    inserted: tuple[DeviceChange, ...]
    removed: tuple[DeviceChange, ...]


class DeviceMonitor:
    def __init__(self, scanner):
        self.scanner = scanner
        self.previous: dict[str, DeviceInfo] = {}

    def captureInitialState(self) -> None:
        self.previous = self.scanner.scan()

    def pollOnce(self) -> DeviceSnapshot:
        current = self.scanner.scan()
        inserted = tuple(
            DeviceChange(root=Path(root), device=device)
            for root, device in current.items()
            if root not in self.previous
        )
        removed = tuple(
            DeviceChange(root=Path(root), device=device)
            for root, device in self.previous.items()
            if root not in current
        )
        self.previous = current
        return DeviceSnapshot(inserted=inserted, removed=removed)

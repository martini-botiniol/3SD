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
    updated: tuple[DeviceChange, ...] = ()


class DeviceMonitor:
    def __init__(self, scanner):
        self.scanner = scanner
        self.previous: dict[str, DeviceInfo] = {}
        self.metadata: dict[str, tuple | None] = {}

    @staticmethod
    def fingerprint(root: str):
        try:
            stat = (Path(root) / ".cartridge" / "manifest.json").stat()
            return stat.st_mtime_ns, stat.st_size
        except OSError:
            return None

    def captureInitialState(self) -> None:
        self.previous = self.scanner.scan()
        self.metadata = {root: self.fingerprint(root) for root in self.previous}

    def pollOnce(self) -> DeviceSnapshot:
        current = self.scanner.scan()
        inserted = tuple(
            DeviceChange(root=Path(root), device=device)
            for root, device in current.items()
            if root not in self.previous or self.previous[root] != device
        )
        removed = tuple(
            DeviceChange(root=Path(root), device=device)
            for root, device in self.previous.items()
            if root not in current or current[root] != device
        )
        metadata = {root: self.fingerprint(root) for root in current}
        updated = tuple(DeviceChange(Path(root), device) for root, device in current.items()
                        if self.previous.get(root) == device and metadata[root] != self.metadata.get(root))
        self.previous = current
        self.metadata = metadata
        return DeviceSnapshot(inserted=inserted, removed=removed, updated=updated)

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from cartridge_launcher.domain.errors import CartridgeError, ErrorCode
from cartridge_launcher.domain.manifest import manifestFromBytes, manifestFromDict
from cartridge_launcher.domain.models import CartridgeManifest, DeviceInfo, RegisteredCartridge
from cartridge_launcher.services.cartridge_validator import FORBIDDEN_METADATA_EXTENSIONS
from cartridge_launcher.services.local_registry import LocalRegistry
from cartridge_launcher.services.security_service import SecurityService


class CartridgeRepairService:
    def __init__(self, security: SecurityService, registry: LocalRegistry, deviceScanner):
        self.security = security
        self.registry = registry
        self.deviceScanner = deviceScanner

    def repair(self, root: Path, displayName: str, appId: str) -> CartridgeManifest:
        device = self.deviceScanner.findDeviceByRoot(root)
        if device is None:
            raise CartridgeError(ErrorCode.DEVICE_REMOVED, "Selected device is no longer available.")

        metadataDir = root / ".cartridge"
        metadataDir.mkdir(parents=True, exist_ok=True)
        (root / "SteamLibrary").mkdir(exist_ok=True)
        self._removeForbiddenMetadata(metadataDir)

        current = self._readExistingManifest(metadataDir / "manifest.json")
        manifest = manifestFromDict(
            {
                "schemaVersion": 1,
                "cartridgeId": current.cartridgeId if current is not None and current.cartridgeId else str(uuid.uuid4()),
                "displayName": displayName.strip(),
                "platform": "STEAM",
                "appId": appId.strip(),
                "libraryPath": "SteamLibrary",
                "createdAt": current.createdAt if current is not None and current.createdAt else datetime.now(UTC).isoformat(),
            }
        )
        self._writeManifest(metadataDir, manifest)
        self.registry.upsert(_registeredFromManifest(manifest, device))
        return manifest

    def _readExistingManifest(self, manifestPath: Path) -> CartridgeManifest | None:
        if not manifestPath.is_file():
            return None
        try:
            return manifestFromBytes(manifestPath.read_bytes())
        except CartridgeError:
            return None
        except OSError:
            return None

    def _removeForbiddenMetadata(self, metadataDir: Path) -> None:
        for path in metadataDir.rglob("*"):
            if path.is_file() and path.suffix.lower() in FORBIDDEN_METADATA_EXTENSIONS:
                path.unlink()

    def _writeManifest(self, metadataDir: Path, manifest: CartridgeManifest) -> None:
        manifestBytes = json.dumps(manifest.__dict__, indent=2).encode("utf-8")
        (metadataDir / "manifest.json").write_bytes(manifestBytes)
        (metadataDir / "signature.sig").write_text(self.security.sign(manifestBytes), encoding="utf-8")


def _registeredFromManifest(manifest: CartridgeManifest, device: DeviceInfo) -> RegisteredCartridge:
    return RegisteredCartridge(
        manifest.cartridgeId,
        manifest.appId,
        device.volumeSerialNumber,
        device.capacityBytes,
        manifest.displayName,
    )

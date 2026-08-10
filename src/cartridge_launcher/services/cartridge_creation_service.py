from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from cartridge_launcher.domain.errors import CartridgeError, ErrorCode
from cartridge_launcher.domain.manifest import manifestFromDict
from cartridge_launcher.domain.models import CartridgeManifest, DeviceInfo, RegisteredCartridge
from cartridge_launcher.services.local_registry import LocalRegistry
from cartridge_launcher.services.security_service import SecurityService


class CartridgeCreationService:
    def __init__(self, security: SecurityService, registry: LocalRegistry, deviceScanner):
        self.security = security
        self.registry = registry
        self.deviceScanner = deviceScanner

    def create(self, root: Path, displayName: str, appId: str) -> CartridgeManifest:
        device = self.deviceScanner.findDeviceByRoot(root)
        if device is None:
            raise CartridgeError(ErrorCode.DEVICE_REMOVED, "Selected device is no longer available.")

        metadataDir = root / ".cartridge"
        if (metadataDir / "manifest.json").is_file() or (metadataDir / "signature.sig").is_file():
            raise CartridgeError(
                ErrorCode.CARTRIDGE_ALREADY_EXISTS,
                "This SSD already has a cartridge. Use update instead of create.",
            )

        metadataDir.mkdir(parents=True, exist_ok=True)
        (root / "SteamLibrary").mkdir(exist_ok=True)

        manifest = manifestFromDict(
            {
                "schemaVersion": 1,
                "cartridgeId": str(uuid.uuid4()),
                "displayName": displayName.strip(),
                "platform": "STEAM",
                "appId": appId.strip(),
                "libraryPath": "SteamLibrary",
                "createdAt": datetime.now(UTC).isoformat(),
            }
        )
        self._writeManifest(root, manifest)
        self.registry.upsert(_registeredFromManifest(manifest, device))
        return manifest

    def _writeManifest(self, root: Path, manifest: CartridgeManifest) -> None:
        metadataDir = root / ".cartridge"
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

from __future__ import annotations

import json
from pathlib import Path

from cartridge_launcher.domain.errors import CartridgeError, ErrorCode
from cartridge_launcher.domain.manifest import manifestFromBytes, manifestFromDict
from cartridge_launcher.domain.models import CartridgeManifest, RegisteredCartridge
from cartridge_launcher.services.local_registry import LocalRegistry
from cartridge_launcher.services.security_service import SecurityService


class CartridgeUpdateService:
    def __init__(self, security: SecurityService, registry: LocalRegistry, deviceScanner):
        self.security = security
        self.registry = registry
        self.deviceScanner = deviceScanner

    def update(self, root: Path, displayName: str, appId: str) -> CartridgeManifest:
        device = self.deviceScanner.findDeviceByRoot(root)
        if device is None:
            raise CartridgeError(ErrorCode.DEVICE_REMOVED, "Selected device is no longer available.")

        metadataDir = root / ".cartridge"
        manifestPath = metadataDir / "manifest.json"
        signaturePath = metadataDir / "signature.sig"
        if not metadataDir.is_dir() or not manifestPath.is_file() or not signaturePath.is_file():
            raise CartridgeError(ErrorCode.INVALID_STRUCTURE, "Cartridge metadata was not found.")

        rawManifest = manifestPath.read_bytes()
        if not self.security.verify(rawManifest, signaturePath.read_text(encoding="utf-8")):
            raise CartridgeError(ErrorCode.INVALID_SIGNATURE, "manifest.json signature does not match.")

        current = manifestFromBytes(rawManifest)
        updated = manifestFromDict(
            {
                **current.__dict__,
                "displayName": displayName.strip(),
                "appId": appId.strip(),
            }
        )
        manifestBytes = json.dumps(updated.__dict__, indent=2).encode("utf-8")
        manifestPath.write_bytes(manifestBytes)
        signaturePath.write_text(self.security.sign(manifestBytes), encoding="utf-8")
        self.registry.upsert(
            RegisteredCartridge(updated.cartridgeId, updated.appId, device.volumeSerialNumber, device.capacityBytes, updated.displayName)
        )
        return updated

from __future__ import annotations

from pathlib import Path

from cartridge_launcher.domain.errors import CartridgeError, ErrorCode
from cartridge_launcher.domain.manifest import manifestFromBytes
from cartridge_launcher.domain.models import CartridgeManifest, DeviceInfo
from cartridge_launcher.services.local_registry import LocalRegistry
from cartridge_launcher.services.security_service import SecurityService


FORBIDDEN_METADATA_EXTENSIONS = {".exe", ".bat", ".cmd", ".ps1", ".dll", ".msi"}


class CartridgeValidator:
    def __init__(self, security: SecurityService, registry: LocalRegistry):
        self.security = security
        self.registry = registry

    def validate(self, root: Path, device: DeviceInfo) -> CartridgeManifest:
        metadataDir = root / ".cartridge"
        manifestPath = metadataDir / "manifest.json"
        signaturePath = metadataDir / "signature.sig"
        libraryPath = root / "SteamLibrary"

        if not metadataDir.is_dir() or not manifestPath.is_file() or not signaturePath.is_file():
            raise CartridgeError(ErrorCode.INVALID_STRUCTURE, "Cartridge metadata was not found.")
        if not libraryPath.is_dir():
            raise CartridgeError(ErrorCode.INVALID_STRUCTURE, "SteamLibrary directory was not found.")
        self._rejectExecutableMetadata(metadataDir)

        rawManifest = manifestPath.read_bytes()
        signature = signaturePath.read_text(encoding="utf-8")
        if not self.security.verify(rawManifest, signature):
            raise CartridgeError(ErrorCode.INVALID_SIGNATURE, "manifest.json signature does not match.")

        manifest = manifestFromBytes(rawManifest)
        registered = self.registry.get(manifest.cartridgeId)
        if registered is not None and registered.volumeSerialNumber != device.volumeSerialNumber:
            raise CartridgeError(ErrorCode.DEVICE_MISMATCH, "Cartridge is registered to another device.")

        return manifest

    def _rejectExecutableMetadata(self, metadataDir: Path) -> None:
        for path in metadataDir.rglob("*"):
            if path.is_file() and path.suffix.lower() in FORBIDDEN_METADATA_EXTENSIONS:
                raise CartridgeError(ErrorCode.INVALID_STRUCTURE, "Executable metadata is not allowed.")

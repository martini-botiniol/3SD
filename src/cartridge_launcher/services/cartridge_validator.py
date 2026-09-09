from __future__ import annotations

from pathlib import Path

from cartridge_launcher.domain.errors import CartridgeError, ErrorCode
from cartridge_launcher.domain.manifest import manifestFromBytes, payloadFromBytes, MAX_MANIFEST_BYTES
from cartridge_launcher.domain.models import CartridgeManifest, DeviceInfo
from cartridge_launcher.services.local_registry import LocalRegistry
from cartridge_launcher.services.security_service import SecurityService
from cartridge_launcher.services.portable_authorization import verifyAuthorization


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

        if not metadataDir.is_dir() or not manifestPath.is_file():
            raise CartridgeError(ErrorCode.INVALID_STRUCTURE, "Cartridge metadata was not found.")
        if not libraryPath.is_dir():
            raise CartridgeError(ErrorCode.INVALID_STRUCTURE, "SteamLibrary directory was not found.")
        if libraryPath.is_symlink() or (hasattr(libraryPath, "is_junction") and libraryPath.is_junction()):
            raise CartridgeError(ErrorCode.INVALID_STRUCTURE, "SteamLibrary no puede ser un enlace.")
        self._rejectExecutableMetadata(metadataDir)

        if manifestPath.stat().st_size > MAX_MANIFEST_BYTES:
            raise CartridgeError(ErrorCode.INVALID_MANIFEST, "Manifiesto demasiado grande.")
        rawManifest = manifestPath.read_bytes()
        manifest = manifestFromBytes(rawManifest)
        if manifest.schemaVersion == 2:
            verifyAuthorization(payloadFromBytes(rawManifest))
            return manifest
        if not signaturePath.is_file() or signaturePath.stat().st_size > 256 or not self.security.verify(rawManifest, signaturePath.read_text(encoding="utf-8")):
            raise CartridgeError(ErrorCode.CONVERSION_REQUIRED, "Preparar para usar en cualquier PC.")
        registered = self.registry.get(manifest.cartridgeId)
        if registered is not None and registered.volumeSerialNumber != device.volumeSerialNumber:
            raise CartridgeError(ErrorCode.DEVICE_MISMATCH, "Cartridge is registered to another device.")

        return manifest

    def _rejectExecutableMetadata(self, metadataDir: Path) -> None:
        if metadataDir.is_symlink() or (hasattr(metadataDir, "is_junction") and metadataDir.is_junction()):
            raise CartridgeError(ErrorCode.INVALID_STRUCTURE, "La metadata no puede ser un enlace.")
        for path in metadataDir.rglob("*"):
            if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                raise CartridgeError(ErrorCode.INVALID_STRUCTURE, "La metadata no puede contener enlaces.")
            if path.is_file() and path.suffix.lower() in FORBIDDEN_METADATA_EXTENSIONS:
                raise CartridgeError(ErrorCode.INVALID_STRUCTURE, "Executable metadata is not allowed.")

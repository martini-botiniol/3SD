from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import uuid

from cartridge_launcher.domain.errors import CartridgeError, ErrorCode
from cartridge_launcher.domain.manifest import manifestFromBytes, manifestFromDict, payloadFromBytes, MAX_MANIFEST_BYTES
from cartridge_launcher.domain.models import RegisteredCartridge
from cartridge_launcher.infrastructure.storage import atomicWrite, fileLock, writePortableManifest
from cartridge_launcher.services.cartridge_validator import CartridgeValidator, FORBIDDEN_METADATA_EXTENSIONS
from cartridge_launcher.services.portable_authorization import authorize, verifyAuthorization


class CartridgeWriter:
    def __init__(self, security, registry, deviceScanner):
        self.security, self.registry, self.deviceScanner = security, registry, deviceScanner

    def write(self, root: Path, operation: str, displayName: str = "", appId: str = ""):
        device = self.deviceScanner.findDeviceByRoot(root)
        if device is None:
            raise CartridgeError(ErrorCode.DEVICE_REMOVED, "El disco no esta disponible.")
        if operation not in ("create", "update", "convert", "repair"):
            raise ValueError("Operacion de cartucho desconocida")
        if operation != "convert":
            manifestFromDict({"schemaVersion": 2, "cartridgeId": str(uuid.uuid4()),
                "displayName": displayName, "platform": "STEAM", "appId": appId,
                "libraryPath": "SteamLibrary", "createdAt": datetime.now(UTC).isoformat()})
        metadata = root / ".cartridge"
        library = root / "SteamLibrary"
        # Reject redirects before creating a lock or writing any metadata.
        for path in (metadata, library):
            if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                raise CartridgeError(ErrorCode.INVALID_STRUCTURE, "El cartucho no admite carpetas enlazadas.")
        if metadata.exists():
            for path in metadata.rglob("*"):
                if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                    raise CartridgeError(ErrorCode.INVALID_STRUCTURE, "La metadata contiene enlaces.")
        # A lock lives on the SSD so different processes share the same transaction.
        with fileLock(metadata / "write.lock"):
            manifestPath = metadata / "manifest.json"
            if operation == "create" and (manifestPath.exists() or (metadata / "signature.sig").exists()):
                raise CartridgeError(ErrorCode.CARTRIDGE_ALREADY_EXISTS, "Usa actualizar o convertir.")
            current = None
            if manifestPath.is_file():
                if manifestPath.stat().st_size > MAX_MANIFEST_BYTES:
                    raise CartridgeError(ErrorCode.INVALID_MANIFEST, "Manifiesto demasiado grande.")
                try:
                    raw = manifestPath.read_bytes()
                    data = payloadFromBytes(raw)
                    if data.get("schemaVersion") == 2 and operation == "repair":
                        try:
                            verifyAuthorization(data)
                        except CartridgeError as exc:
                            if exc.code == ErrorCode.UNSUPPORTED_AUTHORIZATION:
                                raise
                    current = manifestFromBytes(raw)
                except CartridgeError as exc:
                    if operation != "repair" or exc.code in (ErrorCode.UNSUPPORTED_SCHEMA, ErrorCode.UNSUPPORTED_AUTHORIZATION):
                        raise
            if operation in ("update", "convert"):
                if current is None:
                    raise CartridgeError(ErrorCode.INVALID_STRUCTURE, "No existe un manifiesto para esta operacion.")
                CartridgeValidator(self.security, self.registry)._rejectExecutableMetadata(metadata)
                if current.schemaVersion == 2:
                    verifyAuthorization(payloadFromBytes(manifestPath.read_bytes()))
                    if operation == "convert":
                        return current
                elif operation == "update":
                    CartridgeValidator(self.security, self.registry).validate(root, device)
            if operation == "repair" and current is not None and current.schemaVersion == 2:
                try:
                    verifyAuthorization(payloadFromBytes(manifestPath.read_bytes()))
                except CartridgeError as exc:
                    if exc.code == ErrorCode.UNSUPPORTED_AUTHORIZATION:
                        raise
            payload = {
                "schemaVersion": 2,
                "cartridgeId": current.cartridgeId if current else str(uuid.uuid4()),
                "displayName": current.displayName if operation == "convert" else displayName.strip(),
                "platform": "STEAM",
                "appId": current.appId if operation == "convert" else appId.strip(),
                "libraryPath": "SteamLibrary",
                "createdAt": current.createdAt if current else datetime.now(UTC).isoformat(),
            }
            manifestFromDict(payload)  # Validate BEFORE backup, cleanup or commit.
            payload = authorize(payload)
            if self.deviceScanner.findDeviceByRoot(root) != device:
                raise CartridgeError(ErrorCode.DEVICE_REMOVED, "El dispositivo cambio durante la operacion.")
            if operation == "convert":
                for name in ("manifest.json", "signature.sig"):
                    source = metadata / name
                    backup = metadata / (name + ".v1.bak")
                    if name == "signature.sig" and source.is_file() and source.stat().st_size > 256:
                        raise CartridgeError(ErrorCode.INVALID_STRUCTURE, "La firma antigua excede el tamaño esperado.")
                    if source.is_file() and not backup.exists():
                        atomicWrite(backup, source.read_bytes())
            if operation == "repair":
                # Explicit repair only; retain a recoverable copy before cleanup.
                for path in metadata.rglob("*"):
                    if path.is_file() and path.suffix.lower() in FORBIDDEN_METADATA_EXTENSIONS:
                        atomicWrite(path.with_name(path.name + ".disabled"), path.read_bytes())
                        path.unlink()
            writePortableManifest(root, payload)
            result = manifestFromDict(payload)
            self.registry.upsert(RegisteredCartridge(result.cartridgeId, result.appId,
                device.volumeSerialNumber, device.capacityBytes, result.displayName))
            return result

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceInfo:
    rootPath: str
    volumeSerialNumber: str
    capacityBytes: int


@dataclass(frozen=True)
class CartridgeManifest:
    schemaVersion: int
    cartridgeId: str
    displayName: str
    platform: str
    appId: str
    libraryPath: str
    createdAt: str


@dataclass(frozen=True)
class RegisteredCartridge:
    cartridgeId: str
    appId: str
    volumeSerialNumber: str
    capacityBytes: int
    displayName: str = ""

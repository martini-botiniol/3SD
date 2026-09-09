from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID
from typing import Any

from cartridge_launcher.domain.errors import CartridgeError, ErrorCode
from cartridge_launcher.domain.models import CartridgeManifest


MAX_STEAM_APP_ID = 4294967295
MAX_MANIFEST_BYTES = 65536


def _uniqueObject(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate field")
        result[key] = value
    return result


def payloadFromBytes(rawManifest: bytes) -> dict:
    try:
        if len(rawManifest) > MAX_MANIFEST_BYTES:
            raise ValueError("Manifest too large")
        payload = json.loads(rawManifest.decode("utf-8"), object_pairs_hook=_uniqueObject,
                             parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        if not isinstance(payload, dict):
            raise ValueError("Manifest must be an object")
        return payload
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise CartridgeError(ErrorCode.INVALID_MANIFEST, "manifest.json no es JSON valido.") from exc


def manifestFromBytes(rawManifest: bytes) -> CartridgeManifest:
    return manifestFromDict(payloadFromBytes(rawManifest))


def manifestFromDict(payload: dict[str, Any]) -> CartridgeManifest:
    required = ("schemaVersion", "cartridgeId", "displayName", "platform", "appId", "libraryPath", "createdAt")
    for key in required:
        if key not in payload:
            raise CartridgeError(ErrorCode.INVALID_MANIFEST, f"manifest.json is missing {key}.")

    if type(payload["schemaVersion"]) is not int or payload["schemaVersion"] not in (1, 2):
        raise CartridgeError(ErrorCode.UNSUPPORTED_SCHEMA, "Unsupported manifest schema.")

    appId = str(payload["appId"])
    if not appId.isascii() or not appId.isdigit() or len(appId) > 10 or int(appId) <= 0 or int(appId) > MAX_STEAM_APP_ID:
        raise CartridgeError(ErrorCode.INVALID_APP_ID, "Steam AppID must be a positive 32-bit integer.")

    libraryPath = payload["libraryPath"]
    if libraryPath != "SteamLibrary":
        raise CartridgeError(ErrorCode.INVALID_LIBRARY_PATH, "Steam library path must be SteamLibrary.")

    try:
        if payload["platform"] != "STEAM":
            raise ValueError("Unsupported platform")
        for key in ("cartridgeId", "displayName", "createdAt"):
            if not isinstance(payload[key], str) or not payload[key].strip():
                raise ValueError("Empty field")
        UUID(payload["cartridgeId"])
        if datetime.fromisoformat(payload["createdAt"].replace("Z", "+00:00")).tzinfo is None:
            raise ValueError("Timestamp needs timezone")
    except (ValueError, TypeError, AttributeError) as exc:
        raise CartridgeError(ErrorCode.INVALID_MANIFEST, "Identidad, nombre, plataforma o fecha invalidos.") from exc

    return CartridgeManifest(
        schemaVersion=payload["schemaVersion"],
        cartridgeId=str(payload["cartridgeId"]).strip(),
        displayName=str(payload["displayName"]).strip(),
        platform=str(payload["platform"]).strip(),
        appId=appId,
        libraryPath=libraryPath,
        createdAt=str(payload["createdAt"]).strip(),
        authorization=payload.get("authorization"),
    )

from __future__ import annotations

import json
from typing import Any

from cartridge_launcher.domain.errors import CartridgeError, ErrorCode
from cartridge_launcher.domain.models import CartridgeManifest


MAX_STEAM_APP_ID = 4294967295


def manifestFromBytes(rawManifest: bytes) -> CartridgeManifest:
    try:
        payload = json.loads(rawManifest.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CartridgeError(ErrorCode.INVALID_MANIFEST, "manifest.json is not valid UTF-8 JSON.") from exc

    if not isinstance(payload, dict):
        raise CartridgeError(ErrorCode.INVALID_MANIFEST, "manifest.json must be an object.")

    return manifestFromDict(payload)


def manifestFromDict(payload: dict[str, Any]) -> CartridgeManifest:
    required = ("schemaVersion", "cartridgeId", "displayName", "platform", "appId", "libraryPath", "createdAt")
    for key in required:
        if key not in payload:
            raise CartridgeError(ErrorCode.INVALID_MANIFEST, f"manifest.json is missing {key}.")

    if payload["schemaVersion"] != 1:
        raise CartridgeError(ErrorCode.UNSUPPORTED_SCHEMA, "Unsupported manifest schema.")

    appId = str(payload["appId"]).strip()
    if not appId.isdigit() or int(appId) <= 0 or int(appId) > MAX_STEAM_APP_ID:
        raise CartridgeError(ErrorCode.INVALID_APP_ID, "Steam AppID must be a positive 32-bit integer.")

    libraryPath = str(payload["libraryPath"]).strip()
    if libraryPath != "SteamLibrary":
        raise CartridgeError(ErrorCode.INVALID_LIBRARY_PATH, "Steam library path must be SteamLibrary.")

    return CartridgeManifest(
        schemaVersion=1,
        cartridgeId=str(payload["cartridgeId"]).strip(),
        displayName=str(payload["displayName"]).strip(),
        platform=str(payload["platform"]).strip(),
        appId=appId,
        libraryPath=libraryPath,
        createdAt=str(payload["createdAt"]).strip(),
    )

from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    INVALID_STRUCTURE = "INVALID_STRUCTURE"
    INVALID_MANIFEST = "INVALID_MANIFEST"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"
    UNSUPPORTED_SCHEMA = "UNSUPPORTED_SCHEMA"
    INVALID_APP_ID = "INVALID_APP_ID"
    INVALID_LIBRARY_PATH = "INVALID_LIBRARY_PATH"
    DEVICE_MISMATCH = "DEVICE_MISMATCH"
    STEAM_NOT_FOUND = "STEAM_NOT_FOUND"
    GAME_NOT_INSTALLED = "GAME_NOT_INSTALLED"
    DEVICE_REMOVED = "DEVICE_REMOVED"
    CARTRIDGE_ALREADY_EXISTS = "CARTRIDGE_ALREADY_EXISTS"


class CartridgeError(Exception):
    def __init__(self, code: ErrorCode, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

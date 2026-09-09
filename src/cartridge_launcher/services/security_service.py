from __future__ import annotations

import base64
import hmac
import secrets
import os
from hashlib import sha256
from pathlib import Path
from cartridge_launcher.infrastructure.storage import atomicWrite, fileLock


class SecurityService:
    def __init__(self, secretPath: Path):
        self.secretPath = secretPath

    def sign(self, manifestBytes: bytes) -> str:
        return hmac.new(self._secret(), manifestBytes, sha256).hexdigest()

    def verify(self, manifestBytes: bytes, signature: str) -> bool:
        # Reading a foreign V1 must never generate a local secret or mutate SSD.
        if not self.secretPath.is_file():
            return False
        try:
            expected = self.sign(manifestBytes)
            return hmac.compare_digest(expected, signature.strip())
        except Exception:
            return False

    def _secret(self) -> bytes:
        if self.secretPath.is_file():
            return self._readSecret()
        with fileLock(self.secretPath.with_suffix(".lock")):
            if self.secretPath.is_file():
                return self._readSecret()
            secret = secrets.token_bytes(32)
            if os.name == "nt":
                import win32crypt
                encrypted = win32crypt.CryptProtectData(secret, "3SD legacy HMAC", None, None, None, 0)
                data = b"DPAPI:" + base64.b64encode(encrypted)
            else:
                data = base64.b64encode(secret)
            atomicWrite(self.secretPath, data)
            return secret

    def _readSecret(self) -> bytes:
        data = self.secretPath.read_bytes()
        if data.startswith(b"DPAPI:"):
            import win32crypt
            secret = win32crypt.CryptUnprotectData(base64.b64decode(data[6:], validate=True), None, None, None, 0)[1]
        else:
            secret = base64.b64decode(data, validate=True)
        if len(secret) != 32:
            raise ValueError("Invalid legacy key length")
        return secret

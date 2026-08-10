from __future__ import annotations

import base64
import hmac
import secrets
from hashlib import sha256
from pathlib import Path


class SecurityService:
    def __init__(self, secretPath: Path):
        self.secretPath = secretPath

    def sign(self, manifestBytes: bytes) -> str:
        return hmac.new(self._secret(), manifestBytes, sha256).hexdigest()

    def verify(self, manifestBytes: bytes, signature: str) -> bool:
        expected = self.sign(manifestBytes)
        return hmac.compare_digest(expected, signature.strip())

    def _secret(self) -> bytes:
        if self.secretPath.is_file():
            return base64.b64decode(self.secretPath.read_text(encoding="utf-8"))

        self.secretPath.parent.mkdir(parents=True, exist_ok=True)
        secret = secrets.token_bytes(32)
        self.secretPath.write_text(base64.b64encode(secret).decode("ascii"), encoding="utf-8")
        return secret

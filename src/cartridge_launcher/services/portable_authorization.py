"""Offline recognition, not publisher attestation. Keep old keys when rotating.

This key is distributed with 3SD: it is not a secret against a determined user.
Never generate a replacement key during a build or installation.
"""
from __future__ import annotations
import base64
import binascii
import json
import secrets
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cartridge_launcher.domain.errors import CartridgeError, ErrorCode

KEY_ID = "3sd-portable-2026-01"
KEYS = {KEY_ID: bytes.fromhex("9ad640690b861268532b57c04f0954cc33e82eb148862b6a2238d41052f04ee1")}
MARKER = "3SD-CARTRIDGE"

def canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")

def unsigned(payload: dict) -> dict:
    return {key: value for key, value in payload.items() if key != "authorization"}

def claims(payload: dict) -> dict:
    return {"marker": MARKER, "schemaVersion": 2, "cartridgeId": payload["cartridgeId"], "appId": payload["appId"]}

def authorize(payload: dict) -> dict:
    body = unsigned(payload)
    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(KEYS[KEY_ID]).encrypt(nonce, canonical(claims(body)), canonical(body))
    return {**body, "authorization": {"version": 1, "keyId": KEY_ID,
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii")}}

def verifyAuthorization(payload: dict) -> None:
    auth = payload.get("authorization")
    if not isinstance(auth, dict):
        raise CartridgeError(ErrorCode.INVALID_SIGNATURE, "Falta la autorizacion V2.")
    if type(auth.get("version")) is not int or auth["version"] != 1 or not isinstance(auth.get("keyId"), str) or auth["keyId"] not in KEYS:
        raise CartridgeError(ErrorCode.UNSUPPORTED_AUTHORIZATION, "Actualiza 3SD para leer esta autorizacion.")
    try:
        nonce = base64.b64decode(auth["nonce"], validate=True)
        ciphertext = base64.b64decode(auth["ciphertext"], validate=True)
        if len(nonce) != 12:
            raise ValueError("Invalid nonce")
        decoded = AESGCM(KEYS[auth["keyId"]]).decrypt(nonce, ciphertext, canonical(unsigned(payload)))
        if decoded != canonical(claims(payload)):
            raise ValueError("Invalid marker or identity")
    except (InvalidTag, ValueError, TypeError, KeyError, binascii.Error) as exc:
        raise CartridgeError(ErrorCode.INVALID_SIGNATURE, "La autorizacion no coincide con el manifiesto.") from exc

import base64
import copy
import json
import uuid
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from pathlib import Path
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from cartridge_launcher.domain.errors import CartridgeError, ErrorCode
from cartridge_launcher.domain.models import DeviceInfo, RegisteredCartridge
from cartridge_launcher.infrastructure.storage import atomicWrite
from cartridge_launcher.services.cartridge_creation_service import CartridgeCreationService
from cartridge_launcher.services.cartridge_update_service import CartridgeUpdateService
from cartridge_launcher.services.cartridge_conversion_service import CartridgeConversionService
from cartridge_launcher.services.cartridge_repair_service import CartridgeRepairService
from cartridge_launcher.services.cartridge_validator import CartridgeValidator
from cartridge_launcher.services.local_registry import LocalRegistry
from cartridge_launcher.services.security_service import SecurityService
from cartridge_launcher.services.portable_authorization import authorize, verifyAuthorization, canonical, claims, unsigned, KEYS, KEY_ID


class Scanner:
    def __init__(self, root):
        self.device = DeviceInfo(str(root), "ABC123", 100)

    def findDeviceByRoot(self, root):
        return self.device if self.device and str(root) == self.device.rootPath else None


@pytest.fixture
def cartridge(tmp_path):
    root = tmp_path / "ssd"
    root.mkdir()
    scanner = Scanner(root)
    a = (SecurityService(tmp_path / "A" / "secret"), LocalRegistry(tmp_path / "A" / "registry.json"), scanner)
    b = (SecurityService(tmp_path / "B" / "secret"), LocalRegistry(tmp_path / "B" / "registry.json"), scanner)
    manifest = CartridgeCreationService(*a).create(root, "Juego ñ", "111")
    return root, scanner, a, b, manifest


def read(root):
    return json.loads((root / ".cartridge" / "manifest.json").read_text(encoding="utf-8"))


def test_exchange_A_B_A_and_update_without_original_secret(cartridge):
    root, scanner, a, b, first = cartridge
    original = (root / ".cartridge" / "manifest.json").read_bytes()
    assert CartridgeValidator(*b[:2]).validate(root, scanner.device) == first
    assert (root / ".cartridge" / "manifest.json").read_bytes() == original
    changed = CartridgeUpdateService(*b).update(root, "Otro juego", "222")
    assert changed.cartridgeId == first.cartridgeId
    assert changed.authorization["nonce"] != first.authorization["nonce"]
    assert CartridgeValidator(*a[:2]).validate(root, scanner.device) == changed
    assert not a[0].secretPath.exists() and not b[0].secretPath.exists()


@pytest.mark.parametrize("field,value", [("displayName", "Alterado"), ("appId", "222"),
    ("cartridgeId", "00000000-0000-4000-8000-000000000002"), ("extra", "injected")])
def test_all_manifest_fields_are_authenticated(cartridge, field, value):
    root, *_ = cartridge
    data = read(root)
    data[field] = value
    with pytest.raises(CartridgeError) as exc:
        verifyAuthorization(data)
    assert exc.value.code == ErrorCode.INVALID_SIGNATURE


def test_authorization_cannot_be_copied_between_cartridges(cartridge):
    root, *_ = cartridge
    first = read(root)
    second = authorize({**unsigned(first), "cartridgeId": str(uuid.uuid4())})
    second["authorization"] = first["authorization"]
    with pytest.raises(CartridgeError):
        verifyAuthorization(second)


@pytest.mark.parametrize("mutation,code", [
    (lambda d: d.pop("authorization"), ErrorCode.INVALID_SIGNATURE),
    (lambda d: d["authorization"].update(nonce="AA=="), ErrorCode.INVALID_SIGNATURE),
    (lambda d: d["authorization"].update(ciphertext="not base64!"), ErrorCode.INVALID_SIGNATURE),
    (lambda d: d["authorization"].update(keyId="future"), ErrorCode.UNSUPPORTED_AUTHORIZATION),
    (lambda d: d["authorization"].update(version=20), ErrorCode.UNSUPPORTED_AUTHORIZATION),
])
def test_bad_authorization_never_falls_back_to_v1(cartridge, mutation, code):
    root, scanner, a, b, _ = cartridge
    data = read(root)
    mutation(data)
    raw = canonical(data)
    (root / ".cartridge" / "manifest.json").write_bytes(raw)
    (root / ".cartridge" / "signature.sig").write_text(a[0].sign(raw))
    with pytest.raises(CartridgeError) as exc:
        CartridgeValidator(*a[:2]).validate(root, scanner.device)
    assert exc.value.code == code
    with pytest.raises(CartridgeError):
        CartridgeConversionService(*b).convert(root)
    assert (root / ".cartridge" / "manifest.json").read_bytes() == raw


def test_encrypted_wrong_marker_is_rejected(cartridge):
    root, *_ = cartridge
    data = read(root)
    nonce = base64.b64decode(data["authorization"]["nonce"])
    ciphertext = AESGCM(KEYS[KEY_ID]).encrypt(nonce, canonical({**claims(data), "marker": "OTHER"}), canonical(unsigned(data)))
    data["authorization"]["ciphertext"] = base64.b64encode(ciphertext).decode()
    with pytest.raises(CartridgeError):
        verifyAuthorization(data)


def test_foreign_v1_conversion_is_explicit_and_preserves_backup(cartridge):
    root, scanner, a, b, first = cartridge
    legacy = {**unsigned(read(root)), "schemaVersion": 1}
    raw = canonical(legacy)
    metadata = root / ".cartridge"
    (metadata / "manifest.json").write_bytes(raw)
    signature = a[0].sign(raw)
    (metadata / "signature.sig").write_text(signature)
    with pytest.raises(CartridgeError) as exc:
        CartridgeValidator(*b[:2]).validate(root, scanner.device)
    assert exc.value.code == ErrorCode.CONVERSION_REQUIRED
    assert (metadata / "manifest.json").read_bytes() == raw
    assert not b[0].secretPath.exists()
    assert CartridgeValidator(*a[:2]).validate(root, scanner.device).schemaVersion == 1
    converted = CartridgeConversionService(*b).convert(root)
    assert converted.cartridgeId == first.cartridgeId and converted.appId == first.appId
    assert (metadata / "manifest.json.v1.bak").read_bytes() == raw
    assert (metadata / "signature.sig.v1.bak").read_text() == signature
    assert CartridgeValidator(*a[:2]).validate(root, scanner.device) == converted


def test_interrupted_commit_preserves_previous_readable_manifest(cartridge):
    root, scanner, a, _, first = cartridge
    from cartridge_launcher.infrastructure import storage
    realReplace = storage.os.replace
    def fail_manifest(source, destination):
        if destination.name == "manifest.json":
            raise OSError("unplugged")
        realReplace(source, destination)
    with patch.object(storage.os, "replace", side_effect=fail_manifest), pytest.raises(OSError):
        CartridgeUpdateService(*a).update(root, "Changed", "222")
    assert CartridgeValidator(*a[:2]).validate(root, scanner.device) == first
    assert (root / ".cartridge" / "manifest.previous.json").is_file()


def test_invalid_repair_input_does_not_delete_metadata(cartridge):
    root, scanner, a, _, _ = cartridge
    executable = root / ".cartridge" / "fix.ps1"
    executable.write_text("untrusted")
    original = read(root)
    with pytest.raises(CartridgeError):
        CartridgeRepairService(*a).repair(root, "", "abc")
    assert executable.exists() and read(root) == original


def test_registry_backup_recovers_and_preserves_corrupt_data(tmp_path):
    registry = LocalRegistry(tmp_path / "registry.json")
    first = RegisteredCartridge("a", "111", "A", 100, "Game")
    registry.upsert(first)
    registry.upsert(RegisteredCartridge("b", "222", "B", 100, "Game 2"))
    registry.path.write_text("broken")
    assert registry.all() == (first,)
    assert registry.warning
    registry.upsert(RegisteredCartridge("c", "333", "C", 100, "Game 3"))
    assert registry.path.with_suffix(".json.corrupt").read_text() == "broken"


def test_concurrent_registry_updates_are_not_lost(tmp_path):
    path = tmp_path / "registry.json"
    def write(index):
        LocalRegistry(path).upsert(RegisteredCartridge(str(index), str(index + 1), "A", 100))
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(write, range(30)))
    assert len(LocalRegistry(path).all()) == 30


def _writeFromProcess(task):
    path, index = task
    LocalRegistry(Path(path)).upsert(RegisteredCartridge(str(index), str(index + 1), "A", 100))


def test_registry_serializes_independent_processes(tmp_path):
    path = tmp_path / "registry.json"
    with ProcessPoolExecutor(max_workers=4) as pool:
        list(pool.map(_writeFromProcess, [(str(path), index) for index in range(16)]))
    assert len(LocalRegistry(path).all()) == 16


def test_unknown_key_cannot_be_repaired_even_with_other_invalid_fields(cartridge):
    root, _, a, _, _ = cartridge
    data = read(root)
    data["authorization"]["keyId"] = "future"
    data["createdAt"] = "invalid"
    raw = canonical(data)
    (root / ".cartridge" / "manifest.json").write_bytes(raw)
    with pytest.raises(CartridgeError) as exc:
        CartridgeRepairService(*a).repair(root, "Game", "111")
    assert exc.value.code == ErrorCode.UNSUPPORTED_AUTHORIZATION
    assert (root / ".cartridge" / "manifest.json").read_bytes() == raw

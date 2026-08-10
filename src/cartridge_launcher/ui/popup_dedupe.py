from __future__ import annotations

import json
import time
from pathlib import Path


DEDUPLICATION_SECONDS = 20.0


def shouldShowPopupKey(key: str, dataDirectory: Path | None = None, now: float | None = None) -> bool:
    if key == "":
        return True

    currentTime = time.monotonic() if now is None else now
    path = dedupePath(dataDirectory)
    seen = readSeenKeys(path)
    seen = {itemKey: timestamp for itemKey, timestamp in seen.items() if currentTime - timestamp <= DEDUPLICATION_SECONDS}

    if key in seen:
        writeSeenKeys(path, seen)
        return False

    seen[key] = currentTime
    writeSeenKeys(path, seen)
    return True


def dedupePath(dataDirectory: Path | None = None) -> Path:
    directory = dataDirectory or (Path.home() / ".cartridge-launcher")
    return directory / "status-popup-dedupe.json"


def readSeenKeys(path: Path) -> dict[str, float]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(key): float(value) for key, value in payload.items() if isinstance(value, int | float)}


def writeSeenKeys(path: Path, seen: dict[str, float]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(seen), encoding="utf-8")
    except OSError:
        pass

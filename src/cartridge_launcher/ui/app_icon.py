from __future__ import annotations

from pathlib import Path


APP_ICON_RELATIVE_PATHS = (Path("assets") / "3SD.ico",)


def appIconPath() -> Path | None:
    candidates = []
    for relativePath in APP_ICON_RELATIVE_PATHS:
        candidates.append(Path.cwd() / relativePath)
        candidates.append(Path(__file__).resolve().parents[3] / relativePath)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None

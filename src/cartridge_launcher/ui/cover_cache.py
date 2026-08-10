from __future__ import annotations

from pathlib import Path
from urllib.request import Request, urlopen

try:
    from PIL import Image, ImageTk
except ModuleNotFoundError:
    Image = None
    ImageTk = None


class CoverCache:
    def __init__(self, cacheDirectory: Path):
        self.cacheDirectory = cacheDirectory
        self.memory: dict[tuple[str, tuple[int, int]], object] = {}

    def get(self, appId: str, url: str, size: tuple[int, int]):
        if Image is None or ImageTk is None:
            return None
        key = (appId, size)
        if key in self.memory:
            return self.memory[key]
        self.cacheDirectory.mkdir(parents=True, exist_ok=True)
        imagePath = self.cacheDirectory / f"{appId}.jpg"
        if not imagePath.is_file():
            if not downloadCover(url, imagePath):
                return None
        try:
            image = Image.open(imagePath).resize(size)
            photo = ImageTk.PhotoImage(image)
            self.memory[key] = photo
            return photo
        except Exception:
            try:
                imagePath.unlink()
            except OSError:
                pass
            return None


def downloadCover(url: str, imagePath: Path) -> bool:
    tempPath = imagePath.with_suffix(".tmp")
    try:
        request = Request(url, headers={"User-Agent": "3SD/0.1"})
        with urlopen(request, timeout=10) as response:
            tempPath.write_bytes(response.read())
        tempPath.replace(imagePath)
        return True
    except Exception:
        try:
            tempPath.unlink()
        except OSError:
            pass
        return False

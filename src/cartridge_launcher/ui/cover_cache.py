from __future__ import annotations

from pathlib import Path
from urllib.request import Request, urlopen
from cartridge_launcher.infrastructure.storage import atomicWrite

try:
    from PIL import Image, ImageTk
except ModuleNotFoundError:
    Image = None
    ImageTk = None


class CoverCache:
    def __init__(self, cacheDirectory: Path, tasks=None, onReady=lambda: None):
        self.cacheDirectory = cacheDirectory
        self.memory: dict[tuple[str, tuple[int, int]], object] = {}
        self.tasks, self.onReady = tasks, onReady
        self.failed: set[str] = set()

    def get(self, appId: str, url: str, size: tuple[int, int]):
        if Image is None or ImageTk is None:
            return None
        key = (appId, size)
        if key in self.memory:
            return self.memory[key]
        self.cacheDirectory.mkdir(parents=True, exist_ok=True)
        imagePath = self.cacheDirectory / f"{appId}.jpg"
        if not imagePath.is_file():
            if self.tasks is not None:
                if appId not in self.failed:
                    def complete(success):
                        if success:
                            self.onReady()
                        else:
                            self.failed.add(appId)
                    self.tasks.submit(("cover", appId), lambda: downloadCover(url, imagePath),
                                      complete, lambda _exc: self.failed.add(appId))
                return None
            if not downloadCover(url, imagePath):
                return None
        try:
            with Image.open(imagePath) as original:
                image = original.resize(size)
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
    try:
        request = Request(url, headers={"User-Agent": "3SD/0.1"})
        with urlopen(request, timeout=10) as response:
            atomicWrite(imagePath, response.read())
        return True
    except Exception:
        return False

from __future__ import annotations

from dataclasses import dataclass
import json
from urllib.parse import urlencode
from urllib.request import urlopen


@dataclass(frozen=True)
class SteamSearchResult:
    appId: str
    displayName: str
    imageUrl: str


class SteamStoreSearchClient:
    def search(self, term: str, limit: int = 8) -> tuple[SteamSearchResult, ...]:
        query = urlencode({"term": term, "cc": "us", "l": "spanish"})
        with urlopen(f"https://store.steampowered.com/api/storesearch/?{query}", timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        results = []
        for item in payload.get("items", [])[:limit]:
            appId = str(item.get("id", "")).strip()
            name = str(item.get("name", "")).strip()
            if appId and name:
                results.append(SteamSearchResult(appId, name, str(item.get("tiny_image", ""))))
        return tuple(results)

"""Page domain model."""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from lib.weeb import WeebClient


@dataclass(slots=True)
class Page:
    index: str
    url: str

    _client: WeebClient = field(init=False, default_factory=WeebClient)

    def __hash__(self) -> int:
        return hash(self.url)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Page) and self.url == other.url

    async def download(self, dir: Path, semaphore: asyncio.Semaphore) -> None:
        """Downloads the page to the given directory."""
        file_path = dir / self.index
        if file_path.exists():
            return

        async with semaphore:
            response = await self._client.get_response(self.url)
            file_path.write_bytes(response.content)

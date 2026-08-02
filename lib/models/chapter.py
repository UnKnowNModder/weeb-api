"""Chapter domain model."""

import asyncio
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from lib.caches import _CHAPTER_PAGES_CACHE
from lib.config import Config
from lib.enums import DownloadType
from lib.extractor import Extractor
from lib.models.page import Page
from lib.weeb import WeebClient


@dataclass(slots=True)
class Chapter:
    index: str
    url: str
    manga: str

    _client: WeebClient = field(init=False, default_factory=WeebClient)
    _extractor: Extractor = field(init=False, default_factory=Extractor)
    _config: Config = field(init=False, default_factory=Config)

    def __hash__(self) -> int:
        # using url for hashing.
        return hash(self.url)

    def __eq__(self, other: object) -> bool:
        # eq based on url match.
        return isinstance(other, Chapter) and self.url == other.url

    async def pages(self) -> list[Page]:
        """returns list of pages of the current manga chapter."""
        if (cached := _CHAPTER_PAGES_CACHE.get(self.url)) is not None:
            return cached

        url = f"{self.url}/images"
        params = {"is_prev": "False", "reading_style": "long_strip"}
        fields = ["image url"]
        parser = await self._client.create_parser(url, params)
        pages = await self._extractor.extract("chapter_pages", parser, fields)
        page_list = []
        for index, page in enumerate(pages["image url"]):
            page_list.append(
                Page(
                    index=f"{index:03d}.png",
                    url=page,
                )
            )
        _CHAPTER_PAGES_CACHE[self.url] = page_list
        return page_list

    async def download(self, dir: Path, download_type: DownloadType) -> None:
        """Downloads the chapter to the specified directory.

        Args:
            dir: The directory where the chapter will be saved.
            download_type: The type of download to perform.
        """
        chapter_dir = dir / self.manga / self.index
        chapter_dir.mkdir(parents=True, exist_ok=True)
        pages = await self.pages()
        # semaphore with limit so we can download pages much faster without being rate-limited.
        semaphore = asyncio.Semaphore(self._config.get("max_concurrent_requests", 15))
        tasks = [page.download(chapter_dir, semaphore) for page in pages]
        # runs all the tasks concurrently.
        await asyncio.gather(*tasks)

        if download_type == DownloadType.IMAGE:
            return

        elif download_type == DownloadType.PDF:
            from lib.conversions import convert_images_to_pdf

            convert_images_to_pdf(
                chapter_dir, chapter_dir.with_name(f"{chapter_dir.name}.pdf")
            )
        else:
            from lib.conversions import convert_images_to_cbz

            convert_images_to_cbz(
                chapter_dir, chapter_dir.with_name(f"{chapter_dir.name}.cbz")
            )

        # clean-up of directory because the images are no longer needed.
        shutil.rmtree(chapter_dir)

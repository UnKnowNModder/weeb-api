import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from cachetools import TTLCache

from lib.config import Config
from lib.client import WeebClient
from lib.enums import (
    AdultContent,
    AnimeAdaptation,
    DownloadType,
    Genre,
    OfficialTranslation,
    Order,
    SeriesStatus,
    SeriesType,
    Sort,
)
from lib.extractor import Extractor

import shutil

_MANGA_DETAILS_CACHE: TTLCache = TTLCache(maxsize=256, ttl=600)
_CHAPTER_LIST_CACHE: TTLCache = TTLCache(maxsize=256, ttl=600)
_CHAPTER_PAGES_CACHE: TTLCache = TTLCache(maxsize=256, ttl=1800)


class Weeb:
    """Provides methods to interact with WeebCentral.com."""

    def __init__(self) -> None:
        self._client: WeebClient = WeebClient()
        self._extractor: Extractor = Extractor()
        # special cache for search.
        self._search_cache: TTLCache[str, list[Manga]] = TTLCache(maxsize=256, ttl=600)

    async def search(
        self,
        query: str = "",
        sort: Sort = Sort.BEST_MATCH,
        order: Order = Order.DESCENDING,
        official: OfficialTranslation = OfficialTranslation.ANY,
        anime: AnimeAdaptation = AnimeAdaptation.ANY,
        adult: AdultContent = AdultContent.ANY,
        status: list[SeriesStatus] | None = None,
        type: list[SeriesType] | None = None,
        genre: list[Genre] | None = None,
    ) -> list[Manga]:
        """Searches for manga on WeebCentral with various filtering options.

        Results are cached based on search parameters to speed up repeated queries.

        Args:
            query: The search term for the manga title.
            sort: The sorting criteria (e.g., BEST_MATCH, LATEST_UPDATE).
            order: The sorting order (ASCENDING or DESCENDING).
            official: Filter by official translation status.
            anime: Filter by anime adaptation status.
            adult: Filter by adult content.
            status: A list of series statuses to include (e.g., ONGOING, COMPLETED).
            type: A list of series types to include (e.g., MANGA, MANHWA).
            genre: A list of genres to include.

        Returns:
            A list of Manga objects matching the search criteria.
        """
        params = {
            "text": query,
            "sort": sort,
            "order": order,
            "official": official,
            "anime": anime,
            "adult": adult,
            "included_status": status or [],
            "included_type": type or [],
            "included_tag": genre or [],
            "display_mode": "Full Display",
        }
        cache_key = str(sorted(params.items()))
        if (cached := self._search_cache.get(cache_key)) is not None:
            return cached

        url = f"{self._client.BASE_URL}/search/data"
        fields = ["title", "url"]

        parser = await self._client.create_parser(url, params)

        matches = await self._extractor.extract("search", parser, fields)

        manga_list = []
        for manga in matches:
            manga_list.append(Manga(title=manga["title"], url=manga["url"]))

        self._search_cache[cache_key] = manga_list
        return manga_list

    async def recently_added(self, page: int = 1) -> list[Manga]:
        """Retrieves a list of recently added manga series from a specific page.

        Args:
            page: The page number to retrieve. Defaults to 1.

        Returns:
            A list of Manga objects.
        """
        url = f"{self._client.BASE_URL}/recently-added/{page}"
        fields = ["title", "url"]

        parser = await self._client.create_parser(url)
        matches = await self._extractor.extract("recently_added", parser, fields)

        manga_list = []
        for manga in matches:
            manga_list.append(Manga(title=manga["title"], url=manga["url"]))

        return manga_list


@dataclass(slots=True)
class Manga:
    title: str
    url: str

    _client: WeebClient = field(init=False, default=WeebClient())
    _extractor: Extractor = field(init=False, default=Extractor())

    def __hash__(self) -> int:
        return hash(self.url)

    async def details(self) -> dict[str, str | list[str]]:
        if (cached := _MANGA_DETAILS_CACHE.get(self.url)) is not None:
            return cached
        fields = [
            "description",
            "released",
            "authors",
            "tags",
            "translation",
            "anime",
            "type",
            "status",
            "adult",
            "names",
        ]
        parser = await self._client.create_parser(self.url)
        details = await self._extractor.extract(
            "manga_details", parser.css_first("main"), fields
        )
        _MANGA_DETAILS_CACHE[self.url] = details
        return details

    async def chapters(self) -> list[Chapter]:
        if (cached := _CHAPTER_LIST_CACHE.get(self.url)) is not None:
            return cached
        fields = ["chapter index", "chapter url"]
        parser = await self._client.create_parser(self.chapters_url())
        chapters = await self._extractor.extract("chapter_list", parser, fields)
        chapter_list = []
        for chapter in chapters:
            chapter_list.append(
                Chapter(
                    index=chapter["chapter index"],
                    url=f"{self._client.BASE_URL}{chapter['chapter url']}",
                )
            )
        _CHAPTER_LIST_CACHE[self.url] = chapter_list
        return chapter_list

    def chapters_url(self) -> str:
        """Returns the URL for the manga's chapter list."""
        split_url = self.url.split("/")
        split_url[-1] = "full-chapter-url"
        return "/".join(split_url)


@dataclass(slots=True)
class Chapter:
    index: str
    url: str

    _client: WeebClient = field(init=False, default=WeebClient())
    _extractor: Extractor = field(init=False, default=Extractor())
    _config: Config = field(init=False, default_factory=Config)

    def __hash__(self) -> int:
        return hash(self.url)

    async def pages(self) -> list[Page]:
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
        chapter_dir = dir / self.index
        chapter_dir.mkdir(parents=True, exist_ok=True)
        pages = await self.pages()
        semaphore = asyncio.Semaphore(self._config.get("max_concurrent_requests", 10))
        tasks = [page.download(chapter_dir, semaphore) for page in pages]
        await asyncio.gather(*tasks)

        if download_type == DownloadType.IMAGE:
            return

        elif download_type == DownloadType.PDF:
            from lib.utils import convert_images_to_pdf

            convert_images_to_pdf(chapter_dir, chapter_dir.with_suffix(".pdf"))
        else:
            from lib.utils import convert_images_to_cbz

            convert_images_to_cbz(chapter_dir, chapter_dir.with_suffix(".cbz"))

        shutil.rmtree(chapter_dir)
        


@dataclass(slots=True)
class Page:
    index: int
    url: str

    _client: WeebClient = field(init=False, default=WeebClient())

    def __hash__(self) -> int:
        return hash(self.url)

    async def download(self, dir: Path, semaphore: asyncio.Semaphore) -> None:
        file_path = dir / self.index
        if file_path.exists():
            return

        async with semaphore:
            response = await self._client.get_response(self.url)
            file_path.write_bytes(response.content)


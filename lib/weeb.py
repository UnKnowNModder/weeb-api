from dataclasses import dataclass, field

from cachetools import TTLCache

from lib.client import WeebClient
from lib.enums import (
    AdultContent,
    AnimeAdaptation,
    Genre,
    OfficialTranslation,
    Order,
    SeriesStatus,
    SeriesType,
    Sort,
)
from lib.extractor import Extractor

_CHAPTER_LIST_CACHE: TTLCache = TTLCache(maxsize=256, ttl=600)


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
        fields = ["title", "link"]

        parser = await self._client.create_parser(url, params)

        matches = await self._extractor.extract("search", parser, fields)

        manga_list = []
        for manga in matches:
            manga_list.append(Manga(title=manga["title"], link=manga["link"]))

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
        fields = ["title", "link"]

        parser = await self._client.create_parser(url)
        matches = await self._extractor.extract("recently_added", parser, fields)

        manga_list = []
        for manga in matches:
            manga_list.append(Manga(title=manga["title"], link=manga["link"]))

        return manga_list


@dataclass(slots=True)
class Manga:
    title: str
    link: str
    _details: dict[str, str | list[str]] = field(default_factory=dict)

    _client: WeebClient = field(init=False, default=WeebClient())
    _extractor: Extractor = field(init=False, default=Extractor())

    def __hash__(self) -> int:
        return hash(self.link)

    async def details(self) -> dict[str, str | list[str]]:
        if not self._details:
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
            parser = await self._client.create_parser(self.link)
            self._details = await self._extractor.extract(
                "manga_details", parser.css_first("main"), fields
            )
        return self._details

"""Core Weeb file."""

from lib.caches import _MANGA_SEARCH_CACHE
from lib.client import WeebClient
from lib.enums import (
    AdultContent,
    AnimeAdaptation,
    Genre,
    HotSeriesSort,
    OfficialTranslation,
    Order,
    SeriesStatus,
    SeriesType,
    Sort,
)
from lib.extractor import Extractor
from lib.models.manga import Manga


class Weeb:
    """Provides methods to interact with WeebCentral.com."""

    def __init__(self) -> None:
        self._client: WeebClient = WeebClient()
        self._extractor: Extractor = Extractor()

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
        if (cached := _MANGA_SEARCH_CACHE.get(cache_key)) is not None:
            return cached

        url = f"{self._client.BASE_URL}/search/data"
        fields = ["title", "url"]

        parser = await self._client.create_parser(url, params)

        matches = await self._extractor.extract("search", parser, fields)

        manga_list = []
        for manga in matches:
            manga_list.append(
                Manga(title=manga["title"], url=self.fix_url(manga["url"]))
            )

        _MANGA_SEARCH_CACHE[cache_key] = manga_list
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
            manga_list.append(
                Manga(title=manga["title"], url=self.fix_url(manga["url"]))
            )

        return manga_list

    async def hot_series(
        self, sort: HotSeriesSort = HotSeriesSort.WEEKLY
    ) -> list[Manga]:
        """Retrieves a list of trending manga series from a specific page.

        Args:
            sort: The sorting criteria for the hot series (e.g., WEEKLY, MONTHLY).
        """
        url = f"{self._client.BASE_URL}/hot-series?sort={sort}"
        fields = ["title", "url"]

        parser = await self._client.create_parser(url)
        matches = await self._extractor.extract("hot_series", parser, fields)

        manga_list = []
        for manga in matches:
            manga_list.append(
                Manga(title=manga["title"], url=self.fix_url(manga["url"]))
            )

        return manga_list

    def fix_url(self, url: str) -> str:
        """Fixes the URL to ensure it points to the manga's main page.

        Args:
            url: The original URL.

        Returns:
            The fixed URL pointing to the manga's main page.
        """
        if not url.startswith(self._client.BASE_URL):
            url = f"{self._client.BASE_URL}{url}"
        return url

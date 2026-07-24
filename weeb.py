import asyncio
import re
from client import WeebClient
from cachetools import TTLCache
from dataclasses import dataclass

from enums import (
    AdultContent,
    AnimeAdaptation,
    DownloadType,
    Genre,
    HotSeriesSort,
    OfficialTranslation,
    Order,
    SeriesStatus,
    SeriesType,
    Sort,
)


class Weeb:
    """Provides methods to interact with WeebCentral.com.
    """

    def __init__(self) -> None:
        self._client: WeebClient = WeebClient()
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

        markdown = await self._client.create_markdown(f"{self._client.BASE_URL}/search/data", params=params)

        pattern = rf"(?<!\! )\[([^\]]+)\]\({re.escape(self._client.BASE_URL)}/series/[^\)]+\)"
        matches = re.findall(pattern, markdown)

        manga_list = []
        for title, link in matches:
            manga_list.append(Manga(title=title, link=link))

        self._search_cache[cache_key] = manga_list
        return manga_list

@dataclass
class Manga:
    title: str = ""
    link: str = ""
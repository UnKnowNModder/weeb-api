from dataclasses import dataclass

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


class Weeb:
    """Provides methods to interact with WeebCentral.com."""

    def __init__(self) -> None:
        self._client: WeebClient = WeebClient()
        self.extractor: Extractor = Extractor()
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

        parser = await self._client.create_parser(url, params)

        matches = await self.extractor.extract("search", parser, ["title", "link"])

        manga_list = []
        for manga in matches:
            manga_list.append(Manga(title=manga["title"], link=manga["link"]))

        self._search_cache[cache_key] = manga_list
        return manga_list


@dataclass
class Manga:
    title: str = ""
    link: str = ""

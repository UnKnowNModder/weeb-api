"""Manga domain model."""

from dataclasses import dataclass, field

from lib.caches import _CHAPTER_LIST_CACHE, _MANGA_DETAILS_CACHE
from lib.extractor import Extractor
from lib.models.chapter import Chapter
from lib.weeb import WeebClient


@dataclass(slots=True)
class Manga:
    title: str
    url: str

    _client: WeebClient = field(init=False, default_factory=WeebClient)
    _extractor: Extractor = field(init=False, default_factory=Extractor)

    def __hash__(self) -> int:
        return hash(self.url)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Manga) and self.url == other.url

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
        """Returns the list of chapters of the current manga."""
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
                    manga=self.title,
                )
            )
        _CHAPTER_LIST_CACHE[self.url] = chapter_list
        return chapter_list

    def chapters_url(self) -> str:
        """Returns the URL for the manga's chapter list."""
        split_url = self.url.split("/")
        split_url[-1] = "full-chapter-url"
        return "/".join(split_url)

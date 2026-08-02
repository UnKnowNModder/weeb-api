"""Caches for faster pulling for same required data, yeah this consumes RAM. (temporarily)"""

from cachetools import TTLCache

_MANGA_SEARCH_CACHE: TTLCache = TTLCache(maxsize=256, ttl=600)
_MANGA_DETAILS_CACHE: TTLCache = TTLCache(maxsize=256, ttl=600)
_CHAPTER_LIST_CACHE: TTLCache = TTLCache(maxsize=256, ttl=600)
_CHAPTER_PAGES_CACHE: TTLCache = TTLCache(maxsize=256, ttl=1800)

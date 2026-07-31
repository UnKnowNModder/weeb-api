from __future__ import annotations

import os
from typing import Any

import httpx
from dotenv import load_dotenv
from selectolax.parser import HTMLParser
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)
from ua_generator import generate

load_dotenv()


class NetworkError(Exception):
    """Raised for network-related errors, such as connection timeouts or HTTP status codes that survived retries."""


class ParsingError(Exception):
    """Raised when there's an error parsing HTML content, e.g. site layout changed or we got an empty response."""


class WeebClient:
    """Async HTTP client for weebcentral.com."""

    BASE_URL = "https://weebcentral.com"
    TIMEOUT = int(os.getenv("REQUEST_TIMEOUT"))
    MAX_RETRIES = int(os.getenv("MAX_RETRIES"))

    def __init__(self) -> None:
        """Sets up the client."""
        self._client = httpx.AsyncClient(http2=True, timeout=self.TIMEOUT)

    def __new__(cls) -> WeebClient:
        """Ensures that only one instance of this class exists."""
        if not hasattr(cls, "_instance"):
            cls._instance = super().__new__(cls)
        return cls._instance

    @retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        wait=wait_random_exponential(multiplier=0.5, max=8),
        stop=stop_after_attempt(MAX_RETRIES),
        reraise=True,
    )
    async def _request(self, url: str, params: dict[str, Any] | None) -> httpx.Response:
        # retries are handled by the decorator, so we just raise the exception if it fails.
        headers = {"User-Agent": generate().text}
        response = await self._client.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response

    async def get_response(
        self, url: str, params: dict[str, Any] | None = None
    ) -> httpx.Response:
        """Fetches a URL with retries on failure.

        Args:
            url: The target URL to request.
            params: Optional dictionary of query parameters.

        Returns:
            A httpx.Response object.

        Raises:
            NetworkError: If the request fails after all retries.
        """
        try:
            return await self._request(url, params)
        except httpx.HTTPError as e:
            raise NetworkError(f"Failed to get response from {url} due to {e}")

    async def create_parser(
        self, url: str, params: dict[str, Any] | None = None
    ) -> HTMLParser:
        """Fetches a URL and returns an HTML parser.
        Args:
            url: The target URL to request.
            params: Optional dictionary of query parameters.

        Returns:
            A selectolax.parser.HTMLParser object.
        """
        response = await self.get_response(url, params)

        return self.clean_html(HTMLParser(response.text))

    def clean_html(self, parser: HTMLParser) -> HTMLParser:
        DROP_TAGS = [
            "nav",
            "footer",
            "header",
            "script",
            "style",
            "noscript",
            "svg",
            "iframe",
        ]
        parser.strip_tags(DROP_TAGS)
        return parser

from __future__ import annotations

import asyncio
import httpx
from markdownify import markdownify as md
from typing import Any
from tenacity import retry, retry_if_exception_type, wait_random_exponential, stop_after_attempt
from ua_generator import generate

class NetworkError(Exception):
    """Raised for network-related errors, such as connection timeouts or HTTP status codes that survived retries."""

    pass


class WeebClient:
    """Async HTTP client for weebcentral.com.
    """

    BASE_URL = "https://weebcentral.com"
    TIMEOUT = 60.0  # seconds
    MAX_RETRIES = 3

    def __init__(self) -> None:
        """Sets up the client."""
        self._client = httpx.AsyncClient(http2=True, timeout=self.TIMEOUT)

    def __new__(cls) -> WeebClient:
        """Ensures that only one instance of the client exists (singleton pattern)."""
        if not hasattr(cls, "_instance"):
            cls._instance = super(WeebClient, cls).__new__(cls)
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

    async def create_markdown(
             self, url: str, params: dict[str, Any] | None = None
                ) -> md:
        """Fetches a URL and converts html to markdown.
        Args:
            url: The target URL to request.
            params: Optional dictionary of query parameters.

        Returns:
            A markdownify.markdownify object.
        """
        response = await self.get_response(url, params)
        return md(response.text)
"""One HTTP client for all scrapers: polite delay, retries, cancellation."""

import logging
import threading
import time
from typing import Any

import httpx

log = logging.getLogger(__name__)

DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


class ScraperCancelled(Exception):
    """The run gave up on this scraper (timeout or shutdown)."""


def _is_refusal(exc: httpx.HTTPError) -> bool:
    """A 4xx the server will repeat (not found, forbidden, payment required...)."""
    if not isinstance(exc, httpx.HTTPStatusError):
        return False
    status = exc.response.status_code
    return 400 <= status < 500 and status not in (408, 425, 429)


def describe_error(exc: Exception) -> str:
    """"403 Forbidden (e-licitatie.ro)" instead of httpx's three-line message."""
    if isinstance(exc, httpx.HTTPStatusError):
        response = exc.response
        return f"{response.status_code} {response.reason_phrase} ({response.url.host})"
    return f"{type(exc).__name__}: {str(exc).splitlines()[0] if str(exc) else ''}".rstrip(": ")


class HttpClient:
    """Thin wrapper over a shared `httpx.Client`.

    `get`/`post` raise on failure. The `try_*` helpers return None instead, for
    the many places where a failed page just means "skip it".
    """

    def __init__(
        self,
        *,
        headers: dict[str, str] | None = None,
        timeout: float = 15,
        retries: int = 3,
        delay: float = 0.25,
        verify: bool = True,
    ):
        self.retries = max(1, retries)
        self.delay = delay
        self.cancelled = threading.Event()
        self._client = httpx.Client(
            headers={**DEFAULT_HEADERS, **(headers or {})},
            timeout=timeout,
            follow_redirects=True,
            verify=verify,
        )

    def close(self) -> None:
        self._client.close()

    def cancel(self) -> None:
        self.cancelled.set()

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            # The wait doubles as the cancellation point between requests.
            if self.cancelled.wait(self.delay):
                raise ScraperCancelled(url)
            try:
                response = self._client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except httpx.HTTPError as exc:
                error = exc
                log.debug("%s %s failed (%s/%s): %s", method, url, attempt, self.retries, exc)
                if self.cancelled.is_set():
                    raise ScraperCancelled(url) from exc
                if _is_refusal(exc):
                    break  # asking again will not change the answer
        assert error is not None
        raise error

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def try_get(self, url: str, **kwargs: Any) -> httpx.Response | None:
        try:
            return self.get(url, **kwargs)
        except httpx.HTTPError:
            return None

    def try_html(self, url: str, **kwargs: Any) -> str | None:
        response = self.try_get(url, **kwargs)
        return response.text if response is not None else None

    def try_json(self, url: str, **kwargs: Any) -> Any | None:
        response = self.try_get(url, **kwargs)
        if response is None:
            return None
        try:
            return response.json()
        except ValueError:
            return None

"""Pobieranie JSON przez HTTP z ponawianiem (błędy sieci, 429, 5xx)."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import httpx

log = logging.getLogger(__name__)

RETRY_STATUS = {429, 500, 502, 503, 504}


class FetchError(RuntimeError):
    """Nie udało się pobrać danych po wszystkich próbach."""


def get_json(
    client: httpx.Client,
    url: str,
    params: dict[str, Any] | None = None,
    *,
    retries: int = 5,
    backoff: float = 2.0,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    """GET → JSON. Ponawia `retries` razy z opóźnieniem backoff * 2**próba."""
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = client.get(url, params=params)
            if resp.status_code in RETRY_STATUS:
                raise httpx.HTTPStatusError(
                    f"HTTP {resp.status_code}", request=resp.request, response=resp
                )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in RETRY_STATUS:
                raise FetchError(f"{url}: HTTP {exc.response.status_code}") from exc
            last = exc
        except httpx.TransportError as exc:
            last = exc
        if attempt < retries:
            delay = backoff * 2**attempt
            log.warning("Ponawiam %s za %.0f s (%s)", url, delay, last)
            sleep(delay)
    raise FetchError(f"{url}: nieudane po {retries + 1} próbach: {last}") from last

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import httpx

from src.config import MarketConfig, get_env
from src.utils.cache import cached_request

logger = logging.getLogger(__name__)

SERPAPI_BASE = "https://serpapi.com/search"
MAX_RETRIES = 3
BACKOFF_BASE = 2.0


@dataclass
class SearchResult:
    position: int
    title: str
    link: str
    snippet: str
    date: str | None


def _serpapi_search(params: dict) -> dict:
    api_key = get_env("TTD_SERPAPI_KEY")
    params["api_key"] = api_key

    for attempt in range(MAX_RETRIES):
        try:
            response = httpx.get(SERPAPI_BASE, params=params, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPStatusError, httpx.TransportError) as e:
            if attempt == MAX_RETRIES - 1:
                raise
            wait = BACKOFF_BASE ** (attempt + 1)
            logger.warning(f"SerpAPI search failed (attempt {attempt + 1}): {e}. Retrying in {wait}s...")
            time.sleep(wait)
    return {}


def search_destination(destination: str, market_config: MarketConfig) -> list[SearchResult]:
    all_results: list[SearchResult] = []

    for template in market_config.google_search_templates:
        query = template.format(destination=destination)
        cache_key = f"search_{market_config.code}_{query}"

        params = {
            "engine": "google",
            "q": query,
            "gl": market_config.code.lower(),
            "hl": market_config.language,
            "num": 10,
        }

        logger.info(f"Searching Google for: {query}")
        data = cached_request(cache_key, lambda p=params: _serpapi_search(p))

        organic = data.get("organic_results", [])
        logger.info(f"  → {len(organic)} organic results for '{query}'")

        for item in organic:
            all_results.append(SearchResult(
                position=item.get("position", 0),
                title=item.get("title", ""),
                link=item.get("link", ""),
                snippet=item.get("snippet", ""),
                date=item.get("date"),
            ))

    logger.info(f"Total search results for '{destination}': {len(all_results)}")
    return all_results

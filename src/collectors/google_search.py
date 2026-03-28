from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

import httpx

from src.config import MarketConfig, get_env
from src.utils.cache import cached_request

logger = logging.getLogger(__name__)

SERPAPI_BASE = "https://serpapi.com/search"
MAX_RETRIES = 3
BACKOFF_BASE = 2.0

# URLs matching these patterns are search-engine result pages, not real articles.
_SEARCH_ENGINE_RE = re.compile(
    r"(?:search(?:test)?\.seznam\.cz"
    r"|google\.com/search"
    r"|bing\.com/search"
    r"|yahoo\.com/search)",
    re.IGNORECASE,
)


@dataclass
class SearchResult:
    position: int
    title: str
    link: str
    snippet: str
    date: str | None


@dataclass
class QueryResults:
    query: str
    results: list[SearchResult] = field(default_factory=list)


@dataclass
class DestinationSearchData:
    results: list[SearchResult]             # flat list (all queries merged, for scoring)
    total_results: int
    per_query: list[QueryResults] = field(default_factory=list)  # per-query breakdown


def _is_search_engine_url(url: str) -> bool:
    return bool(_SEARCH_ENGINE_RE.search(url))


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


def search_destination(destination: str, market_config: MarketConfig) -> DestinationSearchData:
    all_results: list[SearchResult] = []
    per_query: list[QueryResults] = []
    max_total_results = 0
    filtered_count = 0

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

        total = data.get("search_information", {}).get("total_results", 0)
        if total > max_total_results:
            max_total_results = total
        logger.info(f"  → total_results={total:,} for '{query}'")

        organic = data.get("organic_results", [])
        query_results = QueryResults(query=query)

        for item in organic:
            link = item.get("link", "")
            if _is_search_engine_url(link):
                filtered_count += 1
                logger.debug(f"  Filtered search-engine URL: {link}")
                continue

            result = SearchResult(
                position=item.get("position", 0),
                title=item.get("title", ""),
                link=link,
                snippet=item.get("snippet", ""),
                date=item.get("date"),
            )
            query_results.results.append(result)
            all_results.append(result)

        per_query.append(query_results)
        logger.info(f"  → {len(query_results.results)} organic results for '{query}'")

    if filtered_count:
        logger.info(f"Filtered {filtered_count} search-engine URLs for '{destination}'")
    logger.info(f"Total search results for '{destination}': {len(all_results)}, max total_results={max_total_results:,}")
    return DestinationSearchData(results=all_results, total_results=max_total_results, per_query=per_query)

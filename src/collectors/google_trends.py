from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import httpx

from src.config import MarketConfig, get_env
from src.utils.cache import cached_request

logger = logging.getLogger(__name__)

SERPAPI_BASE = "https://serpapi.com/search"
MAX_RETRIES = 3
BACKOFF_BASE = 2.0


@dataclass
class TimelinePoint:
    date: str
    value: int


@dataclass
class RelatedQuery:
    query: str
    value: int | str
    source: str = "rising"  # "rising" | "top"


@dataclass
class TrendResult:
    query: str
    timeline: list[TimelinePoint]
    rising_queries: list[RelatedQuery]
    top_queries: list[RelatedQuery]


@dataclass
class TrendData:
    market_code: str
    results: list[TrendResult] = field(default_factory=list)
    all_rising_queries: list[RelatedQuery] = field(default_factory=list)
    all_top_queries: list[RelatedQuery] = field(default_factory=list)


def _serpapi_request(params: dict) -> dict:
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
            logger.warning(f"SerpAPI request failed (attempt {attempt + 1}): {e}. Retrying in {wait}s...")
            time.sleep(wait)
    return {}


def fetch_interest_over_time(query: str, geo: str, date: str = "today 12-m") -> list[TimelinePoint]:
    cache_key = f"trends_iot_{geo}_{query}_{date}"
    params = {
        "engine": "google_trends",
        "q": query,
        "geo": geo,
        "date": date,
    }

    data = cached_request(cache_key, lambda: _serpapi_request(params))
    timeline_data = data.get("interest_over_time", {}).get("timeline_data", [])

    points = []
    for point in timeline_data:
        values = point.get("values", [])
        if values:
            points.append(TimelinePoint(
                date=point.get("date", ""),
                value=values[0].get("extracted_value", 0),
            ))
    return points


def fetch_related_queries(query: str, geo: str) -> tuple[list[RelatedQuery], list[RelatedQuery]]:
    cache_key = f"trends_rq_{geo}_{query}"
    params = {
        "engine": "google_trends",
        "q": query,
        "geo": geo,
        "data_type": "RELATED_QUERIES",
    }

    data = cached_request(cache_key, lambda: _serpapi_request(params))
    related = data.get("related_queries", {})

    rising = [
        RelatedQuery(query=r["query"], value=r.get("value", 0), source="rising")
        for r in related.get("rising", [])
    ]
    top = [
        RelatedQuery(query=r["query"], value=r.get("value", 0), source="top")
        for r in related.get("top", [])
    ]
    return rising, top


def collect_trends(market_config: MarketConfig) -> TrendData:
    geo = market_config.google_trends_geo
    trend_data = TrendData(market_code=market_config.code)
    seen_rising: set[str] = set()
    seen_top: set[str] = set()

    for query in market_config.all_seed_queries:
        logger.info(f"Fetching Google Trends for: {query}")

        timeline = fetch_interest_over_time(query, geo)
        rising, top = fetch_related_queries(query, geo)

        trend_data.results.append(TrendResult(
            query=query,
            timeline=timeline,
            rising_queries=rising,
            top_queries=top,
        ))

        for rq in rising:
            if rq.query.lower() not in seen_rising:
                seen_rising.add(rq.query.lower())
                trend_data.all_rising_queries.append(rq)

        for tq in top:
            if tq.query.lower() not in seen_top:
                seen_top.add(tq.query.lower())
                trend_data.all_top_queries.append(tq)

    logger.info(
        f"Collected {len(trend_data.results)} trend queries, "
        f"{len(trend_data.all_rising_queries)} unique rising, "
        f"{len(trend_data.all_top_queries)} unique top"
    )
    return trend_data

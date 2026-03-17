from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import httpx

from src.config import get_env
from src.utils.cache import cached_request

logger = logging.getLogger(__name__)

APIFY_BASE = "https://api.apify.com/v2"
ACTOR_ID = "apify~instagram-hashtag-scraper"
POLL_INTERVAL = 5
MAX_WAIT = 300


@dataclass
class InstagramPost:
    caption: str
    likes: int
    comments_count: int
    timestamp: str
    hashtags: list[str]
    location: str
    url: str


@dataclass
class HashtagMetrics:
    hashtag: str
    posts_last_4_weeks: int
    posts_previous_4_weeks: int
    velocity_change_pct: float
    total_posts: int


@dataclass
class InstagramData:
    hashtag_metrics: list[HashtagMetrics] = field(default_factory=list)
    all_posts: list[InstagramPost] = field(default_factory=list)


def fetch_hashtag_posts(hashtag: str, limit: int = 50) -> list[InstagramPost]:
    token = get_env("TTD_APIFY_TOKEN")
    cache_key = f"instagram_{hashtag}_{limit}"

    def _run_actor() -> list[dict]:
        # Start actor run
        run_resp = httpx.post(
            f"{APIFY_BASE}/acts/{ACTOR_ID}/runs",
            params={"token": token},
            json={
                "hashtags": [hashtag],
                "resultsType": "posts",
                "resultsLimit": limit,
            },
            timeout=30.0,
        )
        run_resp.raise_for_status()
        run_data = run_resp.json()["data"]
        run_id = run_data["id"]
        dataset_id = run_data["defaultDatasetId"]

        # Poll for completion
        elapsed = 0
        while elapsed < MAX_WAIT:
            status_resp = httpx.get(
                f"{APIFY_BASE}/actor-runs/{run_id}",
                params={"token": token},
                timeout=30.0,
            )
            status = status_resp.json()["data"]["status"]
            if status == "SUCCEEDED":
                break
            if status in ("FAILED", "ABORTED"):
                raise RuntimeError(f"Apify actor run {status} for hashtag #{hashtag}")
            time.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL

        if elapsed >= MAX_WAIT:
            raise TimeoutError(f"Apify actor run timed out for hashtag #{hashtag}")

        # Fetch results
        items_resp = httpx.get(
            f"{APIFY_BASE}/datasets/{dataset_id}/items",
            params={"token": token, "format": "json"},
            timeout=30.0,
        )
        return items_resp.json()

    raw_posts = cached_request(cache_key, _run_actor)

    posts = []
    for p in raw_posts:
        posts.append(InstagramPost(
            caption=p.get("caption", ""),
            likes=p.get("likesCount", 0),
            comments_count=p.get("commentsCount", 0),
            timestamp=p.get("timestamp", ""),
            hashtags=p.get("hashtags", []),
            location=p.get("locationName", ""),
            url=p.get("url", ""),
        ))
    return posts


def _compute_velocity(posts: list[InstagramPost]) -> tuple[int, int, float]:
    now = datetime.now(timezone.utc)
    cutoff_4w = now - timedelta(weeks=4)
    cutoff_8w = now - timedelta(weeks=8)

    recent = 0
    previous = 0

    for post in posts:
        try:
            ts = datetime.fromisoformat(post.timestamp.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue

        if ts >= cutoff_4w:
            recent += 1
        elif ts >= cutoff_8w:
            previous += 1

    velocity_pct = ((recent - previous) / max(previous, 1)) * 100
    return recent, previous, velocity_pct


def collect_instagram_data(hashtags: list[str], limit_per_hashtag: int = 50) -> InstagramData:
    data = InstagramData()

    for hashtag in hashtags:
        logger.info(f"Fetching Instagram data for #{hashtag}")
        try:
            posts = fetch_hashtag_posts(hashtag, limit=limit_per_hashtag)
        except Exception as e:
            logger.error(f"Failed to fetch #{hashtag}: {e}")
            continue

        data.all_posts.extend(posts)

        recent, previous, velocity = _compute_velocity(posts)
        data.hashtag_metrics.append(HashtagMetrics(
            hashtag=hashtag,
            posts_last_4_weeks=recent,
            posts_previous_4_weeks=previous,
            velocity_change_pct=velocity,
            total_posts=len(posts),
        ))

    logger.info(f"Collected Instagram data for {len(data.hashtag_metrics)} hashtags, {len(data.all_posts)} total posts")
    return data

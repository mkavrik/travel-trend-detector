from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from src.collectors.google_trends import TrendData, TimelinePoint, fetch_interest_over_time
from src.collectors.instagram import InstagramData

logger = logging.getLogger(__name__)

# Adjusted weights for PoC (no Twitter)
WEIGHT_GOOGLE_TRENDS = 0.60
WEIGHT_INSTAGRAM = 0.30
WEIGHT_CROSS_PLATFORM = 0.10

LOW_VOLUME_THRESHOLD = 10
LOW_VOLUME_PENALTY = 0.50


class VolumeStatus(Enum):
    OK = "ok"
    LOW_VOLUME = "low_volume"
    ZERO = "zero"


@dataclass
class VolumeCheck:
    status: VolumeStatus
    avg_last_4w: float
    timeline: list[TimelinePoint]


def check_search_volume(query: str, geo: str) -> VolumeCheck:
    """Fetch interest_over_time for a rising query and check its absolute volume."""
    timeline = fetch_interest_over_time(query, geo)
    values = [p.value for p in timeline]

    last_4w = values[-4:] if len(values) >= 4 else values
    if not last_4w:
        logger.info(f"Volume check '{query}': no data — marking as zero")
        return VolumeCheck(status=VolumeStatus.ZERO, avg_last_4w=0.0, timeline=timeline)

    avg = sum(last_4w) / len(last_4w)

    if all(v == 0 for v in last_4w):
        logger.info(f"Volume check '{query}': all zeros in last 4w — excluding")
        return VolumeCheck(status=VolumeStatus.ZERO, avg_last_4w=0.0, timeline=timeline)

    if avg < LOW_VOLUME_THRESHOLD:
        logger.info(f"Volume check '{query}': avg={avg:.1f} < {LOW_VOLUME_THRESHOLD} — low_volume")
        return VolumeCheck(status=VolumeStatus.LOW_VOLUME, avg_last_4w=avg, timeline=timeline)

    logger.info(f"Volume check '{query}': avg={avg:.1f} — ok")
    return VolumeCheck(status=VolumeStatus.OK, avg_last_4w=avg, timeline=timeline)


@dataclass
class TrendClassification:
    label: str
    emoji: str
    short_term_change_pct: float
    yoy_change_pct: float


def _extract_windows(timeline: list[TimelinePoint]) -> tuple[float, float, float]:
    """Extract current 4w, previous 4w, and same-period-last-year averages."""
    values = [p.value for p in timeline]
    if not values:
        return 0.0, 0.0, 0.0

    # Current 4 weeks = last 4 data points
    current_4w = sum(values[-4:]) / max(len(values[-4:]), 1)
    # Previous 4 weeks = 5th-8th from end
    previous_4w = sum(values[-8:-4]) / max(len(values[-8:-4]), 1)
    # Same period last year (roughly 48-52 weeks back = first 4 data points in 12m data)
    same_4w_ly = sum(values[:4]) / max(len(values[:4]), 1)

    return current_4w, previous_4w, same_4w_ly


def classify_trend(timeline: list[TimelinePoint]) -> TrendClassification:
    current_4w, previous_4w, same_4w_ly = _extract_windows(timeline)

    short_term_change = (current_4w - previous_4w) / max(previous_4w, 1) * 100
    yoy_change = (current_4w - same_4w_ly) / max(same_4w_ly, 1) * 100

    if previous_4w < 5 and current_4w > 30:
        label, emoji = "Breakout", "🚀"
    elif yoy_change > 50:
        label, emoji = "Accelerating", "📈"
    elif -20 < yoy_change < 50:
        label, emoji = "Seasonal Peak", "🔄"
    else:
        label, emoji = "Fading", "📉"

    return TrendClassification(
        label=label,
        emoji=emoji,
        short_term_change_pct=round(short_term_change, 1),
        yoy_change_pct=round(yoy_change, 1),
    )


def calculate_google_trends_score(timeline: list[TimelinePoint]) -> float:
    """Score 0-100 based on trend momentum."""
    current_4w, previous_4w, same_4w_ly = _extract_windows(timeline)

    # Short-term momentum (0-50)
    st_change = (current_4w - previous_4w) / max(previous_4w, 1) * 100
    st_score = min(max(st_change, 0), 100) * 0.5

    # YoY momentum (0-50)
    yoy_change = (current_4w - same_4w_ly) / max(same_4w_ly, 1) * 100
    yoy_score = min(max(yoy_change, 0), 200) * 0.25

    return min(st_score + yoy_score, 100)


def calculate_instagram_score(hashtag_velocity_pct: float) -> float:
    """Score 0-100 based on Instagram hashtag velocity."""
    return min(max(hashtag_velocity_pct, 0), 100)


def calculate_trend_score(
    google_score: float,
    instagram_score: float,
    has_cross_platform: bool,
) -> float:
    score = (
        google_score * WEIGHT_GOOGLE_TRENDS
        + instagram_score * WEIGHT_INSTAGRAM
        + (100 if has_cross_platform else 0) * WEIGHT_CROSS_PLATFORM
    )
    return round(min(score, 100), 1)

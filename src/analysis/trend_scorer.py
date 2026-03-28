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
    INSUFFICIENT_DATA = "insufficient_data"
    ZERO = "zero"


INSUFFICIENT_DATA_PENALTY = 0.30
INSUFFICIENT_DATA_MAX_NONZERO_MONTHS = 2


@dataclass
class VolumeCheck:
    status: VolumeStatus
    avg_last_4w: float
    timeline: list[TimelinePoint]
    nonzero_months: int = 0


def check_search_volume(query: str, geo: str) -> VolumeCheck:
    """Fetch interest_over_time for a rising query and check its absolute volume."""
    timeline = fetch_interest_over_time(query, geo)
    values = [p.value for p in timeline]

    last_4w = values[-4:] if len(values) >= 4 else values
    if not last_4w:
        logger.info(f"Volume check '{query}': no data — marking as zero")
        return VolumeCheck(status=VolumeStatus.ZERO, avg_last_4w=0.0, timeline=timeline, nonzero_months=0)

    avg = sum(last_4w) / len(last_4w)

    if all(v == 0 for v in last_4w):
        logger.info(f"Volume check '{query}': all zeros in last 4w — excluding")
        return VolumeCheck(status=VolumeStatus.ZERO, avg_last_4w=0.0, timeline=timeline, nonzero_months=0)

    # Count non-zero months (aggregate weekly data into ~monthly buckets of 4 weeks)
    nonzero_months = 0
    for i in range(0, len(values), 4):
        chunk = values[i:i + 4]
        if any(v > 0 for v in chunk):
            nonzero_months += 1

    if nonzero_months <= INSUFFICIENT_DATA_MAX_NONZERO_MONTHS:
        logger.info(
            f"Volume check '{query}': avg={avg:.1f}, nonzero_months={nonzero_months} "
            f"<= {INSUFFICIENT_DATA_MAX_NONZERO_MONTHS} — insufficient_data"
        )
        return VolumeCheck(status=VolumeStatus.INSUFFICIENT_DATA, avg_last_4w=avg, timeline=timeline, nonzero_months=nonzero_months)

    if avg < LOW_VOLUME_THRESHOLD:
        logger.info(f"Volume check '{query}': avg={avg:.1f} < {LOW_VOLUME_THRESHOLD} — low_volume")
        return VolumeCheck(status=VolumeStatus.LOW_VOLUME, avg_last_4w=avg, timeline=timeline, nonzero_months=nonzero_months)

    logger.info(f"Volume check '{query}': avg={avg:.1f}, nonzero_months={nonzero_months} — ok")
    return VolumeCheck(status=VolumeStatus.OK, avg_last_4w=avg, timeline=timeline, nonzero_months=nonzero_months)


@dataclass
class TrendClassification:
    label: str
    emoji: str
    short_term_change_pct: float
    yoy_change_pct: float


def _extract_windows(timeline: list[TimelinePoint]) -> tuple[float, float, float]:
    """Extract current 4w peak, previous 4w peak, and same-period-last-year peak.

    Uses weekly peaks (not averages) to better capture seasonal spikes.
    """
    values = [p.value for p in timeline]
    if not values:
        return 0.0, 0.0, 0.0

    # Current 4 weeks = last 4 data points — peak
    current_4w = max(values[-4:]) if len(values) >= 4 else max(values)
    # Previous 4 weeks = 5th-8th from end — peak
    prev_slice = values[-8:-4]
    previous_4w = max(prev_slice) if prev_slice else 0.0
    # Same period last year (first 4 data points in 12m data) — peak
    ly_slice = values[:4]
    same_4w_ly = max(ly_slice) if ly_slice else 0.0

    return float(current_4w), float(previous_4w), float(same_4w_ly)


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

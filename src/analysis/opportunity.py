from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.analysis.content_gap import ContentGapScore


@dataclass
class WeeklyTrendPoint:
    week: str        # e.g. "Mar 3–9"
    value: int       # 0–100
    bar: str         # visual bar ██████


@dataclass
class SeasonalComparison:
    label: str = ""             # e.g. "týden 10–13"
    values_ly: list[int] = field(default_factory=list)
    values_now: list[int] = field(default_factory=list)
    peak_ly: int = 0
    peak_now: int = 0
    yoy_peak_pct: float = 0.0


@dataclass
class TrendTimeline:
    # Part 1: 12-month sparkline (all weekly datapoints)
    sparkline: str = ""
    peak_value: int = 0
    peak_label: str = ""
    peak_index: int = 0         # position in sparkline (0-based)
    total_weeks: int = 0
    # Part 2: last 8 weeks detail table
    weeks: list[WeeklyTrendPoint] = field(default_factory=list)
    # Part 3: seasonal YoY comparison
    seasonal: SeasonalComparison = field(default_factory=SeasonalComparison)


# Sparkline block chars mapped to value ranges (0–100 → 8 levels)
_SPARK_CHARS = "▁▂▃▄▅▆▇█"


def _value_to_spark(value: int, max_val: int) -> str:
    if max_val <= 0 or value <= 0:
        return _SPARK_CHARS[0]
    normalized = value / max_val
    idx = min(int(normalized * (len(_SPARK_CHARS) - 1) + 0.5), len(_SPARK_CHARS) - 1)
    return _SPARK_CHARS[idx]


def _format_week_label(date_str: str) -> str:
    """Turn 'Mar 23 – 29, 2025' into 'Mar 23–29'."""
    m_start = re.match(r"([A-Z][a-z]{2})\s+(\d+)", date_str)
    if not m_start:
        return date_str[:12]
    month_s, day_s = m_start.group(1), m_start.group(2)
    m_end = re.search(r"[–—-]\s*(?:([A-Z][a-z]{2})\s+)?(\d+)", date_str)
    if m_end:
        end_month = m_end.group(1)
        end_day = m_end.group(2)
        if end_month and end_month != month_s:
            return f"{month_s} {day_s}–{end_month} {end_day}"
        return f"{month_s} {day_s}–{end_day}"
    return f"{month_s} {day_s}"


def _format_week_short(date_str: str) -> str:
    """Turn 'Mar 23 – 29, 2025' into 'Mar 2025' for seasonal label."""
    m = re.search(r"([A-Z][a-z]{2}).*?(\d{4})", date_str)
    return f"{m.group(1)} {m.group(2)}" if m else date_str[:8]


def build_trend_timeline(timeline_points: list) -> TrendTimeline:
    """Build three-part trend timeline from raw TimelinePoints."""
    if not timeline_points:
        return TrendTimeline()

    values = [p.value for p in timeline_points]
    n = len(values)
    max_val = max(values) or 1

    # --- Part 1: Sparkline (all weeks) ---
    peak_value = 0
    peak_index = 0
    for i, v in enumerate(values):
        if v > peak_value:
            peak_value = v
            peak_index = i

    sparkline = "".join(_value_to_spark(v, max_val) for v in values)
    peak_label = _format_week_label(timeline_points[peak_index].date)

    # --- Part 2: Last 8 weeks detail table ---
    last_8 = timeline_points[-8:] if n >= 8 else timeline_points
    max_recent = max((p.value for p in last_8), default=1) or 1
    max_blocks = 18
    weeks: list[WeeklyTrendPoint] = []
    for p in last_8:
        label = _format_week_label(p.date)
        n_blocks = round(p.value / max_recent * max_blocks) if p.value > 0 else 0
        bar = "█" * max(n_blocks, 1) if p.value > 0 else "—"
        weeks.append(WeeklyTrendPoint(week=label, value=p.value, bar=bar))

    # --- Part 3: Seasonal comparison (current 4w vs same 4w last year) ---
    values_now = values[-4:] if n >= 4 else values
    values_ly = values[:4] if n >= 4 else []
    peak_now = max(values_now) if values_now else 0
    peak_ly = max(values_ly) if values_ly else 0
    yoy_peak_pct = (peak_now - peak_ly) / max(peak_ly, 1) * 100

    # Build week-range label from the last 4 datapoints
    if n >= 4:
        first_w = _format_week_short(timeline_points[-4].date)
        last_w = _format_week_short(timeline_points[-1].date)
        seasonal_label = f"{first_w} – {last_w}" if first_w != last_w else first_w
    else:
        seasonal_label = ""

    seasonal = SeasonalComparison(
        label=seasonal_label,
        values_ly=list(values_ly),
        values_now=list(values_now),
        peak_ly=peak_ly,
        peak_now=peak_now,
        yoy_peak_pct=round(yoy_peak_pct, 1),
    )

    return TrendTimeline(
        sparkline=sparkline,
        peak_value=peak_value,
        peak_label=peak_label,
        peak_index=peak_index,
        total_weeks=n,
        weeks=weeks,
        seasonal=seasonal,
    )


@dataclass
class TopSearchResult:
    title: str
    link: str
    date: str
    is_czech: bool
    is_fresh: bool


@dataclass
class ContentGapDetail:
    assessment: str = ""
    score: float = 0.0
    quality_score: float = 0.0
    freshness_score: float = 0.0
    language_score: float = 0.0
    top_results: list[TopSearchResult] = field(default_factory=list)
    total_results: int = 0
    czech_count: int = 0
    other_lang_count: int = 0
    fresh_count: int = 0
    old_count: int = 0
    content_types_found: list[str] = field(default_factory=list)
    content_types_missing: list[str] = field(default_factory=list)


def build_content_gap_detail(
    search_results: list,
    gap_score: "ContentGapScore",
) -> ContentGapDetail:
    """Build rich content gap detail from search results and scored gap."""
    czech_chars = {"č", "ř", "ž", "š", "ě", "ů", "ú", "ý", "á", "í", "é"}
    fresh_years = {"2025", "2026"}

    top5: list[TopSearchResult] = []
    czech_count = 0
    fresh_count = 0

    for r in search_results[:10]:
        text = (r.title + " " + r.snippet).lower()
        is_czech = any(c in text for c in czech_chars)
        is_fresh = bool(r.date and any(y in r.date for y in fresh_years))

        if is_czech:
            czech_count += 1
        if is_fresh:
            fresh_count += 1

        if len(top5) < 5:
            top5.append(TopSearchResult(
                title=r.title,
                link=r.link,
                date=r.date or "neuvedeno",
                is_czech=is_czech,
                is_fresh=is_fresh,
            ))

    analyzed = min(len(search_results), 10)
    return ContentGapDetail(
        assessment=gap_score.assessment,
        score=gap_score.score,
        quality_score=gap_score.quality_score,
        freshness_score=gap_score.freshness_score,
        language_score=gap_score.language_score,
        top_results=top5,
        total_results=gap_score.total_results,
        czech_count=czech_count,
        other_lang_count=analyzed - czech_count,
        fresh_count=fresh_count,
        old_count=analyzed - fresh_count,
        content_types_found=gap_score.content_types_found,
        content_types_missing=gap_score.content_types_missing,
    )


BOTH_BONUS = 15


@dataclass
class Destination:
    name: str
    name_cs: str
    country: str
    region: str
    activity_type: str
    season: str
    trend_score: float
    content_gap_score: float
    opportunity_score: float
    trend_classification: str
    trend_emoji: str
    content_gap_assessment: str
    market_category: str
    verdict: str
    trend_timeline: TrendTimeline = field(default_factory=TrendTimeline)
    rising_query: str = ""
    rising_value: str = ""
    instagram_velocity_pct: float | None = None
    instagram_hashtag: str = ""
    content_gap_detail: ContentGapDetail = field(default_factory=ContentGapDetail)
    # Reliability indicators
    trend_score_raw: float = 0.0
    opportunity_score_raw: float = 0.0
    volume_assessment: str = "sufficient"          # sufficient / low_volume / insufficient_data
    cross_platform_status: str = "unconfirmed"     # confirmed / unconfirmed
    search_volume_proxy: str = ""                   # e.g. "niche (3,200)"
    # Source / opportunity type
    source: str = "rising"                          # "rising" | "top" | "both"
    opportunity_type: str = "🚀 Trending"           # display label
    popularity_score: float = 0.0                   # top query value (0–100)
    evergreen_opportunity: float = 0.0              # popularity × gap / 100


def calculate_opportunity(trend_score: float, gap_score: float) -> float:
    return round((trend_score * gap_score) / 100, 1)


def calculate_final_opportunity(
    source: str,
    trend_opportunity: float,
    evergreen_opportunity: float,
) -> float:
    """Pick the best opportunity score based on source type."""
    if source == "both":
        return round(max(trend_opportunity, evergreen_opportunity) + BOTH_BONUS, 1)
    if source == "top":
        return round(evergreen_opportunity, 1)
    return round(trend_opportunity, 1)


def opportunity_type_label(source: str) -> str:
    if source == "both":
        return "🔥 Trending+Evergreen"
    if source == "top":
        return "🏔️ Evergreen"
    return "🚀 Trending"


def rank_destinations(destinations: list[Destination], top_n: int = 30) -> list[Destination]:
    sorted_dest = sorted(destinations, key=lambda d: d.opportunity_score, reverse=True)
    return sorted_dest[:top_n]


def categorize_destinations(destinations: list[Destination]) -> tuple[list[Destination], list[Destination], list[Destination]]:
    """Split into (both, rising-only, top-only) lists, each sorted appropriately."""
    both = sorted([d for d in destinations if d.source == "both"], key=lambda d: d.opportunity_score, reverse=True)
    rising = sorted([d for d in destinations if d.source == "rising"], key=lambda d: d.opportunity_score, reverse=True)
    # Evergreen sorted by content_gap_score (not popularity — that's high for all)
    top = sorted([d for d in destinations if d.source == "top"], key=lambda d: d.content_gap_score, reverse=True)
    return both, rising, top

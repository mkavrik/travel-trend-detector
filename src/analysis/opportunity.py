from __future__ import annotations

from dataclasses import dataclass


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


def calculate_opportunity(trend_score: float, gap_score: float) -> float:
    return round((trend_score * gap_score) / 100, 1)


def rank_destinations(destinations: list[Destination], top_n: int = 20) -> list[Destination]:
    sorted_dest = sorted(destinations, key=lambda d: d.opportunity_score, reverse=True)
    return sorted_dest[:top_n]

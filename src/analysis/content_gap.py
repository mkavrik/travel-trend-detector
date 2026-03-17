from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from anthropic import Anthropic

from src.collectors.google_search import SearchResult

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> dict:
    """Extract JSON from Claude response, handling markdown code fences."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"No valid JSON found in response: {text[:200]}")


def classify_market_category(total_results: int) -> str:
    if total_results < 5_000:
        return "niche"
    elif total_results < 50_000:
        return "emerging"
    elif total_results < 500_000:
        return "established"
    else:
        return "mainstream"


@dataclass
class ContentGapScore:
    score: float
    quality_score: float
    freshness_score: float
    language_score: float
    social_score: float
    assessment: str
    market_category: str = ""
    total_results: int = 0
    content_types_found: list[str] = field(default_factory=list)
    content_types_missing: list[str] = field(default_factory=list)


def _score_freshness(results: list[SearchResult]) -> float:
    """Score 0-100: older/missing dates = higher gap."""
    if not results:
        return 100.0

    now = datetime.now(timezone.utc)
    dated = 0
    fresh = 0

    for r in results:
        if r.date:
            dated += 1
            # Simple heuristic: if "2025" or "2026" in date, consider fresh
            if "2026" in r.date or "2025" in r.date:
                fresh += 1

    if dated == 0:
        return 70.0  # No dates = likely not fresh

    freshness_ratio = fresh / dated
    # Invert: less fresh content = higher gap
    return round((1 - freshness_ratio) * 100, 1)


def _score_language_quality(results: list[SearchResult], target_language: str) -> float:
    """Score 0-100: fewer native-language results = higher gap."""
    if not results:
        return 100.0

    # Heuristic: Czech characters indicate Czech content
    czech_indicators = ["č", "ř", "ž", "š", "ě", "ů", "ú", "ý", "á", "í", "é"]

    native_count = 0
    for r in results[:10]:
        text = (r.title + " " + r.snippet).lower()
        if any(c in text for c in czech_indicators):
            native_count += 1

    native_ratio = native_count / min(len(results), 10)
    # Invert: fewer native results = higher gap
    return round((1 - native_ratio) * 100, 1)


def _score_search_quality(results: list[SearchResult]) -> float:
    """Score 0-100: fewer quality results = higher gap."""
    if not results:
        return 100.0

    # Fewer results in top 10 = higher gap
    count = min(len(results), 10)
    return round((1 - count / 10) * 100, 1)


def score_content_gap(
    search_results: list[SearchResult],
    destination: str,
    claude_client: Anthropic | None = None,
    total_results: int = 0,
) -> ContentGapScore:
    quality_score = _score_search_quality(search_results)
    freshness_score = _score_freshness(search_results)
    language_score = _score_language_quality(search_results, "cs")
    social_score = 50.0  # Default; would be refined with social data

    assessment = ""
    content_types_found: list[str] = []
    content_types_missing: list[str] = []

    # Claude qualitative assessment
    if claude_client and search_results:
        try:
            formatted = "\n".join(
                f"{i+1}. {r.title}\n   {r.snippet}\n   Date: {r.date or 'N/A'}"
                for i, r in enumerate(search_results[:10])
            )
            response = claude_client.messages.create(
                model="claude-sonnet-4-6-20250514",
                max_tokens=1000,
                messages=[{
                    "role": "user",
                    "content": f"""Analyzuj tyto Google Search výsledky pro destinaci "{destination}" v češtině a zhodnoť kvalitu cestovatelského obsahu.

Výsledky:
{formatted}

Odpověz POUZE validním JSON:
{{
  "quality_score": 0-100,
  "assessment_cs": "stručné zhodnocení v češtině (2-3 věty)",
  "quality_articles_count": number,
  "content_types_found": ["blog", "agentura", "wiki"],
  "content_types_missing": ["hiking guide", "practical tips"],
  "freshness_assessment": "aktuální/zastaralé/smíšené",
  "language_quality": "nativní/přeložené/smíšené"
}}""",
                }],
            )
            raw_text = response.content[0].text
            logger.debug(f"Claude content gap response for '{destination}': {raw_text[:300]}")
            result = _extract_json(raw_text)
            quality_score = result.get("quality_score", quality_score)
            assessment = result.get("assessment_cs", "")
            content_types_found = result.get("content_types_found", [])
            content_types_missing = result.get("content_types_missing", [])
        except Exception as e:
            logger.warning(f"Claude content gap analysis failed for {destination}: {e}")

    # Weighted composite score
    weights = {"quality": 0.40, "freshness": 0.30, "language": 0.20, "social": 0.10}
    composite = (
        quality_score * weights["quality"]
        + freshness_score * weights["freshness"]
        + language_score * weights["language"]
        + social_score * weights["social"]
    )

    market_category = classify_market_category(total_results)
    logger.info(f"Market category for '{destination}': {market_category} (total_results={total_results:,})")

    return ContentGapScore(
        score=round(composite, 1),
        quality_score=quality_score,
        freshness_score=freshness_score,
        language_score=language_score,
        social_score=social_score,
        assessment=assessment,
        market_category=market_category,
        total_results=total_results,
        content_types_found=content_types_found,
        content_types_missing=content_types_missing,
    )

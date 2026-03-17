from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime, timezone

import click

from src.analysis.claude_analyzer import classify_destination, generate_verdict, get_claude_client
from src.analysis.content_gap import score_content_gap
from src.analysis.opportunity import Destination, calculate_opportunity, rank_destinations
from src.analysis.trend_scorer import (
    calculate_google_trends_score,
    calculate_instagram_score,
    calculate_trend_score,
    classify_trend,
)
from src.collectors.google_search import search_destination
from src.collectors.google_trends import collect_trends
from src.collectors.instagram import collect_instagram_data
from src.config import load_market_config
from src.report.generator import generate_report
from src.utils.normalization import normalize_destination_name

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _current_week() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%G-W%V")


@click.command()
@click.option("--market", required=True, help="Market code (e.g. cz)")
@click.option("--week", default=None, help="Week identifier (e.g. 2026-W12). Defaults to current week.")
@click.option("--dry-run", is_flag=True, help="Only collect data, don't generate report.")
@click.option("--skip-instagram", is_flag=True, help="Skip Instagram data collection.")
def cli(market: str, week: str | None, dry_run: bool, skip_instagram: bool) -> None:
    """Travel Trend × Content Gap Detector — CLI entry point."""
    week = week or _current_week()
    logger.info(f"Starting TTD for market={market.upper()}, week={week}")

    # Load config
    market_config = load_market_config(market)

    # Step 1: Collect Google Trends data
    logger.info("Step 1/5: Collecting Google Trends data...")
    trend_data = collect_trends(market_config)

    # Step 2: Collect Instagram data (optional)
    instagram_data = None
    if not skip_instagram:
        logger.info("Step 2/5: Collecting Instagram data...")
        all_hashtags = market_config.instagram_hashtags.get("generic", [])
        instagram_data = collect_instagram_data(all_hashtags)
    else:
        logger.info("Step 2/5: Skipping Instagram (--skip-instagram)")

    # Step 3: Classify destinations with Claude
    logger.info("Step 3/5: Classifying destinations with Claude...")
    claude_client = get_claude_client()

    seen_destinations: dict[str, dict] = {}
    for rq in trend_data.all_rising_queries:
        try:
            info = classify_destination(rq.query, claude_client)
            if info is None:
                continue
            norm_name = normalize_destination_name(info.destination_name)
            if norm_name not in seen_destinations:
                seen_destinations[norm_name] = {
                    "info": info,
                    "rising_value": rq.value,
                    "query": rq.query,
                }
        except Exception as e:
            logger.warning(f"Failed to classify '{rq.query}': {e}")

    # Step 4: Score and rank
    logger.info("Step 4/5: Scoring and ranking destinations...")
    destinations: list[Destination] = []
    all_search_results: dict[str, list[dict]] = {}

    for norm_name, dest_data in seen_destinations.items():
        info = dest_data["info"]

        # Find matching trend timeline (best effort)
        timeline = []
        for result in trend_data.results:
            if info.destination_name_cs.lower() in result.query.lower() or info.destination_name.lower() in result.query.lower():
                timeline = result.timeline
                break

        # Google Trends score
        gt_score = calculate_google_trends_score(timeline) if timeline else 50.0

        # Instagram score
        ig_score = 0.0
        has_cross_platform = False
        if instagram_data:
            for metrics in instagram_data.hashtag_metrics:
                if info.destination_name_cs.lower() in metrics.hashtag.lower():
                    ig_score = calculate_instagram_score(metrics.velocity_change_pct)
                    has_cross_platform = True
                    break

        trend_score = calculate_trend_score(gt_score, ig_score, has_cross_platform)
        classification = classify_trend(timeline) if timeline else classify_trend([])

        # Content gap
        search_results = search_destination(info.destination_name_cs, market_config)
        all_search_results[info.destination_name_cs] = [asdict(r) for r in search_results]
        logger.info(f"Google Search for '{info.destination_name_cs}': {len(search_results)} results")
        gap = score_content_gap(search_results, info.destination_name_cs, claude_client)

        opportunity = calculate_opportunity(trend_score, gap.score)

        # Verdict
        try:
            verdict = generate_verdict(
                info.destination_name_cs,
                {"trend_score": trend_score, "classification": classification.label, "rising_value": dest_data["rising_value"]},
                {"gap_score": gap.score, "assessment": gap.assessment, "types_missing": gap.content_types_missing},
                claude_client,
            )
        except Exception as e:
            logger.warning(f"Failed to generate verdict for {info.destination_name_cs}: {e}")
            verdict = ""

        destinations.append(Destination(
            name=info.destination_name,
            name_cs=info.destination_name_cs,
            country=info.country,
            region=info.region,
            activity_type=info.activity_type,
            season=info.season,
            trend_score=trend_score,
            content_gap_score=gap.score,
            opportunity_score=opportunity,
            trend_classification=classification.label,
            trend_emoji=classification.emoji,
            content_gap_assessment=gap.assessment,
            verdict=verdict,
        ))

    ranked = rank_destinations(destinations)
    logger.info(f"Found {len(ranked)} destinations")

    if dry_run:
        logger.info("Dry run — skipping report generation")
        for i, d in enumerate(ranked[:10], 1):
            logger.info(f"  {i}. {d.name_cs} ({d.country}) — Opportunity: {d.opportunity_score}")
        return

    # Step 5: Generate report
    logger.info("Step 5/5: Generating report...")
    raw_data = {
        "google-trends": [asdict(r) for r in trend_data.results],
        "search-results": all_search_results,
    }
    if instagram_data:
        raw_data["instagram"] = [asdict(m) for m in instagram_data.hashtag_metrics]

    report_dir = generate_report(ranked, market_config.code, week, raw_data)
    logger.info(f"Done! Report at: {report_dir}")


if __name__ == "__main__":
    cli()

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime, timezone

import click

from src.analysis.claude_analyzer import classify_destination, generate_verdict, get_claude_client
from src.analysis.content_gap import score_content_gap
from src.analysis.opportunity import (
    Destination,
    build_content_gap_detail,
    build_trend_timeline,
    calculate_final_opportunity,
    calculate_opportunity,
    categorize_destinations,
    opportunity_type_label,
    rank_destinations,
)
from src.analysis.trend_scorer import (
    VolumeStatus,
    calculate_google_trends_score,
    calculate_instagram_score,
    calculate_trend_score,
    check_search_volume,
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
@click.option("--yes", "-y", is_flag=True, help="Skip API call confirmation prompt.")
def cli(market: str, week: str | None, dry_run: bool, skip_instagram: bool, yes: bool) -> None:
    """Travel Trend × Content Gap Detector — CLI entry point."""
    week = week or _current_week()
    logger.info(f"Starting TTD for market={market.upper()}, week={week}")

    # Load config
    market_config = load_market_config(market)

    # --- API call estimate ---
    n_seeds = len(market_config.all_seed_queries)
    trends_calls = n_seeds * 2  # interest_over_time + related_queries
    est_destinations = n_seeds * 3  # rough: ~3 unique destinations per seed
    volume_calls = est_destinations  # interest_over_time per destination
    search_calls = min(est_destinations, 30) * len(market_config.google_search_templates)
    total_est = trends_calls + volume_calls + search_calls

    logger.info(f"API call estimate: {n_seeds} seeds × 2 = {trends_calls} trends calls")
    logger.info(f"  + ~{volume_calls} volume checks + ~{search_calls} search calls")
    logger.info(f"  = ~{total_est} total SerpAPI calls")

    if not yes:
        confirm = click.prompt(f"Estimated ~{total_est} SerpAPI calls. Pokračovat? (y/n)", default="y")
        if confirm.lower() not in ("y", "yes"):
            logger.info("Aborted by user.")
            return

    # Step 1: Collect Google Trends data
    logger.info("Step 1/6: Collecting Google Trends data...")
    trend_data = collect_trends(market_config)

    # Step 2: Collect Instagram data (optional)
    instagram_data = None
    if not skip_instagram:
        logger.info("Step 2/6: Collecting Instagram data...")
        all_hashtags = market_config.instagram_hashtags.get("generic", [])
        instagram_data = collect_instagram_data(all_hashtags)
    else:
        logger.info("Step 2/6: Skipping Instagram (--skip-instagram)")

    # Step 3: Classify destinations from BOTH rising and top queries
    logger.info("Step 3/6: Classifying destinations with Claude...")
    claude_client = get_claude_client()

    # Track which sources each destination came from
    # dest_data: {norm_name: {info, rising_value, top_value, query, source}}
    seen_destinations: dict[str, dict] = {}

    # Process rising queries
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
                    "top_value": None,
                    "query": rq.query,
                    "source": "rising",
                }
            else:
                # Already seen — might already have top, upgrade to both
                if seen_destinations[norm_name]["source"] == "top":
                    seen_destinations[norm_name]["source"] = "both"
                    seen_destinations[norm_name]["rising_value"] = rq.value
                    seen_destinations[norm_name]["query"] = rq.query  # prefer rising query for volume check
        except Exception as e:
            logger.warning(f"Failed to classify rising '{rq.query}': {e}")

    # Process top queries
    for tq in trend_data.all_top_queries:
        try:
            info = classify_destination(tq.query, claude_client)
            if info is None:
                continue
            norm_name = normalize_destination_name(info.destination_name)
            if norm_name not in seen_destinations:
                seen_destinations[norm_name] = {
                    "info": info,
                    "rising_value": None,
                    "top_value": tq.value,
                    "query": tq.query,
                    "source": "top",
                }
            else:
                existing = seen_destinations[norm_name]
                existing["top_value"] = tq.value
                if existing["source"] == "rising":
                    existing["source"] = "both"
        except Exception as e:
            logger.warning(f"Failed to classify top '{tq.query}': {e}")

    src_counts = {"rising": 0, "top": 0, "both": 0}
    for d in seen_destinations.values():
        src_counts[d["source"]] += 1
    logger.info(
        f"Classified {len(seen_destinations)} unique destinations: "
        f"{src_counts['rising']} rising-only, {src_counts['top']} top-only, {src_counts['both']} both"
    )

    # Step 3b: Volume filter
    logger.info("Step 3b/6: Checking search volume for classified destinations...")
    geo = market_config.google_trends_geo
    filtered_destinations: dict[str, dict] = {}
    excluded_zero = 0
    flagged_low = 0
    flagged_insufficient = 0

    for norm_name, dest_data in seen_destinations.items():
        volume = check_search_volume(dest_data["query"], geo)

        if volume.status == VolumeStatus.ZERO:
            excluded_zero += 1
            continue

        dest_data["volume_check"] = volume
        dest_data["timeline"] = volume.timeline
        filtered_destinations[norm_name] = dest_data

        if volume.status == VolumeStatus.LOW_VOLUME:
            flagged_low += 1
        elif volume.status == VolumeStatus.INSUFFICIENT_DATA:
            flagged_insufficient += 1

    logger.info(
        f"Volume filter: {len(filtered_destinations)} kept, "
        f"{excluded_zero} excluded (zero volume), "
        f"{flagged_low} flagged as low_volume, "
        f"{flagged_insufficient} flagged as insufficient_data"
    )

    # Step 4: Score and rank
    logger.info("Step 4/6: Scoring and ranking destinations...")
    destinations: list[Destination] = []
    all_search_results: dict[str, list[dict]] = {}

    for norm_name, dest_data in filtered_destinations.items():
        info = dest_data["info"]
        volume = dest_data["volume_check"]
        timeline = dest_data["timeline"]
        source = dest_data["source"]

        # Google Trends score
        gt_score = calculate_google_trends_score(timeline) if timeline else 50.0

        # Instagram score + cross-platform detection
        ig_score = 0.0
        has_cross_platform = False
        ig_velocity_pct: float | None = None
        ig_hashtag = ""
        if instagram_data:
            for metrics in instagram_data.hashtag_metrics:
                if info.destination_name_cs.lower() in metrics.hashtag.lower():
                    ig_score = calculate_instagram_score(metrics.velocity_change_pct)
                    ig_velocity_pct = metrics.velocity_change_pct
                    ig_hashtag = metrics.hashtag
                    has_cross_platform = True
                    break

        trend_score_raw = calculate_trend_score(gt_score, ig_score, has_cross_platform)
        trend_score = trend_score_raw

        # --- Filter 1: Volume assessment ---
        if volume.status == VolumeStatus.INSUFFICIENT_DATA:
            volume_assessment = "insufficient_data"
            trend_score = round(trend_score * 0.30, 1)
            logger.info(f"Volume: insufficient_data for '{info.destination_name_cs}': {trend_score_raw} → {trend_score}")
        elif volume.status == VolumeStatus.LOW_VOLUME:
            volume_assessment = "low_volume"
            trend_score = round(trend_score * 0.50, 1)
            logger.info(f"Volume: low_volume for '{info.destination_name_cs}': {trend_score_raw} → {trend_score}")
        else:
            volume_assessment = "sufficient"

        # --- Filter 2: Cross-platform validation ---
        if ig_velocity_pct is not None and ig_velocity_pct > 30:
            cross_platform_status = "confirmed"
            trend_score = round(min(trend_score + 10, 100), 1)
        else:
            cross_platform_status = "unconfirmed"
            trend_score = round(trend_score * 0.8, 1)

        classification = classify_trend(timeline) if timeline else classify_trend([])
        trend_tl = build_trend_timeline(timeline)

        # Content gap
        search_data = search_destination(info.destination_name_cs, market_config)
        all_search_results[info.destination_name_cs] = {
            "total_results": search_data.total_results,
            "queries": [
                {"query": qr.query, "results": [asdict(r) for r in qr.results]}
                for qr in search_data.per_query
            ],
        }
        logger.info(f"Google Search for '{info.destination_name_cs}': {len(search_data.results)} organic, {search_data.total_results:,} total")
        gap = score_content_gap(search_data.results, info.destination_name_cs, claude_client, total_results=search_data.total_results)

        search_volume_proxy = f"{gap.market_category} ({search_data.total_results:,})"

        # --- Opportunity scoring ---
        trend_opportunity = calculate_opportunity(trend_score, gap.score)
        trend_opportunity_raw = calculate_opportunity(trend_score_raw, gap.score)

        # Evergreen score (top query popularity × gap)
        top_value = dest_data.get("top_value")
        popularity_score = float(top_value) if top_value is not None else 0.0
        evergreen_opportunity = round(popularity_score * gap.score / 100, 1)

        # Final opportunity based on source
        opportunity = calculate_final_opportunity(source, trend_opportunity, evergreen_opportunity)

        gap_detail = build_content_gap_detail(search_data.results, gap)

        # Verdict
        verdict = ""
        try:
            rv_display = dest_data.get("rising_value")
            verdict = generate_verdict(
                info.destination_name_cs,
                {
                    "trend_score": trend_score, "trend_score_raw": trend_score_raw,
                    "classification": classification.label,
                    "rising_value": rv_display, "source": source,
                    "popularity_score": popularity_score,
                    "volume_assessment": volume_assessment,
                    "cross_platform": cross_platform_status,
                },
                {"gap_score": gap.score, "assessment": gap.assessment, "types_missing": gap.content_types_missing, "market_category": gap.market_category},
                claude_client,
            )
        except Exception as e:
            logger.warning(f"Failed to generate verdict for {info.destination_name_cs}: {e}")

        if not verdict:
            verdict = (
                f"{info.destination_name_cs} představuje zajímavou příležitost "
                f"s Opportunity Score {opportunity}. "
                f"Trend Score {trend_score}/100 a Content Gap Score {gap.score}/100 "
                f"naznačují prostor pro tvorbu kvalitního českého obsahu."
            )

        # Format rising value for display
        rv = dest_data.get("rising_value")
        if rv is not None:
            rising_display = str(rv) if isinstance(rv, str) and not str(rv).isdigit() else f"+{rv} %"
        else:
            rising_display = "—"

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
            market_category=gap.market_category,
            verdict=verdict,
            trend_timeline=trend_tl,
            rising_query=dest_data["query"],
            rising_value=rising_display,
            instagram_velocity_pct=ig_velocity_pct,
            instagram_hashtag=ig_hashtag,
            content_gap_detail=gap_detail,
            trend_score_raw=trend_score_raw,
            opportunity_score_raw=trend_opportunity_raw,
            volume_assessment=volume_assessment,
            cross_platform_status=cross_platform_status,
            search_volume_proxy=search_volume_proxy,
            source=source,
            opportunity_type=opportunity_type_label(source),
            popularity_score=popularity_score,
            evergreen_opportunity=evergreen_opportunity,
        ))

    ranked = rank_destinations(destinations)
    logger.info(f"Found {len(ranked)} destinations")

    if dry_run:
        logger.info("Dry run — skipping report generation")
        for i, d in enumerate(ranked[:10], 1):
            logger.info(f"  {i}. {d.name_cs} ({d.country}) — {d.opportunity_type}: {d.opportunity_score}")
        return

    # Step 5: Generate report
    logger.info("Step 5/6: Generating report...")
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

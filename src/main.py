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
from src.utils.log_stream import PipelineLogger
from src.utils.normalization import normalize_destination_name

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _current_week() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%G-W%V")


def run_pipeline(
    market: str,
    week: str | None = None,
    dry_run: bool = False,
    skip_instagram: bool = False,
    selected_queries: dict[str, list[str]] | None = None,
    log: PipelineLogger | None = None,
) -> str | None:
    """Run the pipeline programmatically.

    Args:
        market: Market code (e.g. "cz").
        week: Week identifier (e.g. "2026-W12"). Defaults to current week.
        dry_run: Only collect data, don't generate report.
        skip_instagram: Skip Instagram data collection.
        selected_queries: If provided, only use these seed queries (category -> list).
        log: Optional PipelineLogger for streaming progress to the web UI.

    Returns:
        Path to the generated report directory, or None for dry runs.
    """
    if log is None:
        log = PipelineLogger()

    week = week or _current_week()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log.log(f"Starting pipeline for {market.upper()}, week={week}")

    # Load config
    market_config = load_market_config(market)

    # If selected_queries provided, override the config's seed_queries
    if selected_queries is not None:
        market_config.seed_queries = selected_queries

    # --- API call estimate ---
    n_seeds = len(market_config.all_seed_queries)
    trends_calls = n_seeds * 2
    est_destinations = n_seeds * 3
    volume_calls = est_destinations
    search_calls = min(est_destinations, 30) * len(market_config.google_search_templates)
    total_est = trends_calls + volume_calls + search_calls
    log.log(f"Estimated ~{total_est} SerpAPI calls ({n_seeds} seeds)")

    # Step 1: Collect Google Trends data
    log.log("Phase 1: Collecting Google Trends data...")
    trend_data = collect_trends(market_config)

    n_rising = len(trend_data.all_rising_queries)
    n_top = len(trend_data.all_top_queries)
    log.log(f"Google Trends: found {n_rising} rising queries, {n_top} top queries")

    # Step 2: Collect Instagram data (optional)
    instagram_data = None
    if not skip_instagram:
        log.log("Phase 2: Collecting Instagram data...")
        all_hashtags = market_config.instagram_hashtags.get("generic", [])
        instagram_data = collect_instagram_data(all_hashtags)
    else:
        log.log("Phase 2: Skipping Instagram")

    # Step 3: Classify destinations
    all_queries_list = trend_data.all_rising_queries + trend_data.all_top_queries
    total_to_classify = len(all_queries_list)
    log.log(f"Claude: classifying {total_to_classify} queries...")
    claude_client = get_claude_client()

    seen_destinations: dict[str, dict] = {}
    classified_count = 0
    skipped_count = 0

    for rq in trend_data.all_rising_queries:
        classified_count += 1
        if classified_count % 5 == 0 or classified_count == 1:
            log.log(f"Claude: classified {classified_count}/{total_to_classify} queries...")
        try:
            info = classify_destination(rq.query, claude_client, market=market_config)
            if info is None:
                skipped_count += 1
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
                if seen_destinations[norm_name]["source"] == "top":
                    seen_destinations[norm_name]["source"] = "both"
                    seen_destinations[norm_name]["rising_value"] = rq.value
                    seen_destinations[norm_name]["query"] = rq.query
        except Exception as e:
            log.log(f"\u26a0\ufe0f Failed to classify rising '{rq.query}': {e}")

    for tq in trend_data.all_top_queries:
        classified_count += 1
        if classified_count % 5 == 0:
            log.log(f"Claude: classified {classified_count}/{total_to_classify} queries...")
        try:
            info = classify_destination(tq.query, claude_client, market=market_config)
            if info is None:
                skipped_count += 1
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
            log.log(f"\u26a0\ufe0f Failed to classify top '{tq.query}': {e}")

    log.log(f"Claude: {len(seen_destinations)} destinations identified, {skipped_count} skipped (not destinations)")

    # Step 3b: Volume filter
    dest_names = list(seen_destinations.keys())
    log.log(f"Volume filter: checking {len(dest_names)} destinations...")
    geo = market_config.google_trends_geo
    filtered_destinations: dict[str, dict] = {}
    excluded_zero = 0
    flagged_low = 0
    flagged_insufficient = 0

    for vol_idx, (norm_name, dest_data) in enumerate(seen_destinations.items(), 1):
        log.log(f"Volume filter: checking \"{dest_data['query']}\" ({vol_idx}/{len(dest_names)})")
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

    log.log(f"Volume filter: {len(filtered_destinations)} passed, {excluded_zero} filtered out (zero volume)")

    # Step 4: Score and rank
    log.log("Phase 2: Content gap analysis...")
    destinations: list[Destination] = []
    all_search_results: dict[str, list[dict]] = {}
    dest_list = list(filtered_destinations.items())

    for idx, (norm_name, dest_data) in enumerate(dest_list, 1):
        info = dest_data["info"]
        volume = dest_data["volume_check"]
        timeline = dest_data["timeline"]
        source = dest_data["source"]
        local_name = info.destination_name_local

        log.log(f"Google Search: analyzing \"{local_name}\" ({idx}/{len(dest_list)})")

        # Google Trends score
        gt_score = calculate_google_trends_score(timeline) if timeline else 50.0

        # Instagram score + cross-platform detection
        ig_score = 0.0
        has_cross_platform = False
        ig_velocity_pct: float | None = None
        ig_hashtag = ""
        if instagram_data:
            for metrics in instagram_data.hashtag_metrics:
                if local_name.lower() in metrics.hashtag.lower():
                    ig_score = calculate_instagram_score(metrics.velocity_change_pct)
                    ig_velocity_pct = metrics.velocity_change_pct
                    ig_hashtag = metrics.hashtag
                    has_cross_platform = True
                    break

        trend_score_raw = calculate_trend_score(gt_score, ig_score, has_cross_platform)
        trend_score = trend_score_raw

        # Volume assessment
        if volume.status == VolumeStatus.INSUFFICIENT_DATA:
            volume_assessment = "insufficient_data"
            trend_score = round(trend_score * 0.30, 1)
        elif volume.status == VolumeStatus.LOW_VOLUME:
            volume_assessment = "low_volume"
            trend_score = round(trend_score * 0.50, 1)
        else:
            volume_assessment = "sufficient"

        # Cross-platform validation
        if ig_velocity_pct is not None and ig_velocity_pct > 30:
            cross_platform_status = "confirmed"
            trend_score = round(min(trend_score + 10, 100), 1)
        else:
            cross_platform_status = "unconfirmed"
            trend_score = round(trend_score * 0.8, 1)

        classification = classify_trend(timeline) if timeline else classify_trend([])
        trend_tl = build_trend_timeline(timeline)

        # Content gap
        search_data = search_destination(local_name, market_config)
        all_search_results[info.destination_name_cs] = {
            "total_results": search_data.total_results,
            "queries": [
                {"query": qr.query, "results": [asdict(r) for r in qr.results]}
                for qr in search_data.per_query
            ],
        }

        log.log(f"Content gap: scoring \"{local_name}\"...")
        gap = score_content_gap(search_data.results, local_name, claude_client, total_results=search_data.total_results, market=market_config)

        search_volume_proxy = f"{gap.market_category} ({search_data.total_results:,})"

        # Opportunity scoring
        trend_opportunity = calculate_opportunity(trend_score, gap.score)
        trend_opportunity_raw = calculate_opportunity(trend_score_raw, gap.score)

        top_value = dest_data.get("top_value")
        popularity_score = float(top_value) if top_value is not None else 0.0
        evergreen_opportunity = round(popularity_score * gap.score / 100, 1)

        opportunity = calculate_final_opportunity(source, trend_opportunity, evergreen_opportunity)
        gap_detail = build_content_gap_detail(search_data.results, gap)

        # Verdict
        log.log(f"Verdict: generating for \"{local_name}\" ({idx}/{len(dest_list)})")
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
                market=market_config,
            )
        except Exception as e:
            logger.warning(f"Failed to generate verdict for {info.destination_name_cs}: {e}")

        if not verdict:
            verdict = (
                f"{info.destination_name_cs}: Opportunity Score {opportunity}, "
                f"Trend Score {trend_score}/100, Content Gap Score {gap.score}/100."
            )

        # Format rising value for display
        rv = dest_data.get("rising_value")
        if rv is not None:
            rising_display = str(rv) if isinstance(rv, str) and not str(rv).isdigit() else f"+{rv} %"
        else:
            rising_display = "\u2014"

        destinations.append(Destination(
            name=info.destination_name,
            name_local=info.destination_name_local,
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
    log.log(f"Scoring complete: {len(ranked)} destinations ranked")

    if dry_run:
        log.log("Dry run \u2014 skipping report generation")
        for i, d in enumerate(ranked[:10], 1):
            log.log(f"  {i}. {d.name_cs} ({d.country}) \u2014 {d.opportunity_type}: {d.opportunity_score}")
        return None

    # Generate report
    log.log("Phase 3: Generating report...")
    raw_data = {
        "google-trends": [asdict(r) for r in trend_data.results],
        "search-results": all_search_results,
    }
    if instagram_data:
        raw_data["instagram"] = [asdict(m) for m in instagram_data.hashtag_metrics]

    report_dir = generate_report(ranked, market_config.code, week, raw_data, timestamp=timestamp)
    log.done(str(report_dir))
    return str(report_dir)


@click.command()
@click.option("--market", required=True, help="Market code (e.g. cz)")
@click.option("--week", default=None, help="Week identifier (e.g. 2026-W12). Defaults to current week.")
@click.option("--dry-run", is_flag=True, help="Only collect data, don't generate report.")
@click.option("--skip-instagram", is_flag=True, help="Skip Instagram data collection.")
@click.option("--yes", "-y", is_flag=True, help="Skip API call confirmation prompt.")
def cli(market: str, week: str | None, dry_run: bool, skip_instagram: bool, yes: bool) -> None:
    """Travel Trend \u00d7 Content Gap Detector \u2014 CLI entry point."""
    if not yes:
        mc = load_market_config(market)
        n_seeds = len(mc.all_seed_queries)
        total_est = n_seeds * 2 + n_seeds * 3 + min(n_seeds * 3, 30) * len(mc.google_search_templates)
        confirm = click.prompt(f"Estimated ~{total_est} SerpAPI calls. Pokra\u010dovat? (y/n)", default="y")
        if confirm.lower() not in ("y", "yes"):
            logger.info("Aborted by user.")
            return

    run_pipeline(
        market=market,
        week=week,
        dry_run=dry_run,
        skip_instagram=skip_instagram,
    )


if __name__ == "__main__":
    cli()

from unittest.mock import patch

from src.analysis.trend_scorer import (
    TrendClassification,
    VolumeCheck,
    VolumeStatus,
    calculate_google_trends_score,
    calculate_trend_score,
    check_search_volume,
    classify_trend,
)
from src.collectors.google_trends import TimelinePoint


def _make_timeline(values: list[int]) -> list[TimelinePoint]:
    return [TimelinePoint(date=f"week-{i}", value=v) for i, v in enumerate(values)]


def test_classify_trend_breakout():
    # Low previous, high current
    values = [0] * 8 + [0, 0, 0, 0, 2, 3, 2, 3, 40, 50, 60, 70]
    result = classify_trend(_make_timeline(values))
    assert result.label == "Breakout"
    assert result.emoji == "🚀"


def test_classify_trend_accelerating():
    # Strong YoY growth
    values = [10, 12, 11, 13] + [20] * 12 + [30, 35, 40, 45]
    result = classify_trend(_make_timeline(values))
    assert result.label == "Accelerating"


def test_classify_trend_seasonal():
    # Similar to last year
    values = [50, 48, 52, 50] + [30] * 12 + [55, 53, 50, 52]
    result = classify_trend(_make_timeline(values))
    assert result.label == "Seasonal Peak"


def test_classify_trend_fading():
    # Lower than last year
    values = [80, 75, 78, 82] + [40] * 12 + [30, 28, 25, 22]
    result = classify_trend(_make_timeline(values))
    assert result.label == "Fading"


def test_calculate_trend_score():
    score = calculate_trend_score(
        google_score=80.0,
        instagram_score=60.0,
        has_cross_platform=True,
    )
    expected = 80.0 * 0.60 + 60.0 * 0.30 + 100 * 0.10
    assert score == round(expected, 1)


def test_calculate_trend_score_no_cross():
    score = calculate_trend_score(
        google_score=50.0,
        instagram_score=0.0,
        has_cross_platform=False,
    )
    expected = 50.0 * 0.60
    assert score == round(expected, 1)


@patch("src.analysis.trend_scorer.fetch_interest_over_time")
def test_volume_check_ok(mock_fetch):
    mock_fetch.return_value = _make_timeline([20, 25, 30, 35] + [40] * 8 + [50, 55, 60, 65])
    result = check_search_volume("dolomity", "CZ")
    assert result.status == VolumeStatus.OK
    assert result.avg_last_4w == 57.5
    assert len(result.timeline) == 16


@patch("src.analysis.trend_scorer.fetch_interest_over_time")
def test_volume_check_low(mock_fetch):
    mock_fetch.return_value = _make_timeline([0] * 12 + [3, 5, 7, 8])
    result = check_search_volume("obscure destination", "CZ")
    assert result.status == VolumeStatus.LOW_VOLUME
    assert result.avg_last_4w == 5.75


@patch("src.analysis.trend_scorer.fetch_interest_over_time")
def test_volume_check_zero(mock_fetch):
    mock_fetch.return_value = _make_timeline([0] * 12 + [0, 0, 0, 0])
    result = check_search_volume("nonexistent place", "CZ")
    assert result.status == VolumeStatus.ZERO
    assert result.avg_last_4w == 0.0


@patch("src.analysis.trend_scorer.fetch_interest_over_time")
def test_volume_check_empty_timeline(mock_fetch):
    mock_fetch.return_value = []
    result = check_search_volume("no data", "CZ")
    assert result.status == VolumeStatus.ZERO

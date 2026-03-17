from src.analysis.content_gap import classify_market_category
from src.utils.normalization import normalize_destination_name, slugify


def test_normalize_removes_diacritics():
    assert normalize_destination_name("Dolomity") == "dolomity"
    assert normalize_destination_name("Albánie") == "albanie"


def test_normalize_removes_suffixes():
    assert normalize_destination_name("Albánie dovolená") == "albanie"
    assert normalize_destination_name("Gruzie cestování") == "gruzie"


def test_normalize_collapses_whitespace():
    assert normalize_destination_name("  Dolomity   léto  ") == "dolomity leto"


def test_slugify():
    assert slugify("Albánské Alpy") == "albanske-alpy"
    assert slugify("Dolomity") == "dolomity"


def test_classify_market_category():
    assert classify_market_category(0) == "niche"
    assert classify_market_category(3_200) == "niche"
    assert classify_market_category(4_999) == "niche"
    assert classify_market_category(5_000) == "emerging"
    assert classify_market_category(25_000) == "emerging"
    assert classify_market_category(50_000) == "established"
    assert classify_market_category(350_000) == "established"
    assert classify_market_category(500_000) == "mainstream"
    assert classify_market_category(2_000_000) == "mainstream"

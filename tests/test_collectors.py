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

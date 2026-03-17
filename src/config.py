from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config" / "markets"
REPORTS_DIR = PROJECT_ROOT / "reports"
CACHE_DIR = PROJECT_ROOT / ".cache"


@dataclass
class MarketConfig:
    code: str
    language: str
    country_name: str
    google_trends_geo: str
    timezone: str
    seed_queries: dict[str, list[str]]
    instagram_hashtags: dict[str, list[str] | str]
    google_search_templates: list[str]
    scoring: dict

    @property
    def all_seed_queries(self) -> list[str]:
        queries: list[str] = []
        for group in self.seed_queries.values():
            queries.extend(group)
        return queries


def load_market_config(market_code: str) -> MarketConfig:
    config_path = CONFIG_DIR / f"{market_code.lower()}.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Market config not found: {config_path}")

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    market = raw["market"]
    return MarketConfig(
        code=market["code"],
        language=market["language"],
        country_name=market["country_name"],
        google_trends_geo=market["google_trends_geo"],
        timezone=market["timezone"],
        seed_queries=raw["seed_queries"],
        instagram_hashtags=raw["instagram_hashtags"],
        google_search_templates=raw["google_search_templates"],
        scoring=raw["scoring"],
    )


def get_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise EnvironmentError(f"Missing required environment variable: {name}")
    return value

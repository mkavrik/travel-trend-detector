from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from anthropic import Anthropic

from src.config import MarketConfig, get_env

logger = logging.getLogger(__name__)


@dataclass
class DestinationInfo:
    destination_name: str        # English canonical name
    destination_name_local: str  # In target market language
    destination_name_cs: str     # Czech name (for reports)
    country: str
    region: str
    activity_type: str
    season: str


def get_claude_client() -> Anthropic:
    return Anthropic(api_key=get_env("TTD_ANTHROPIC_KEY"))


def _extract_json(text: str) -> dict:
    """Extract JSON from Claude response, handling markdown code fences."""
    text = text.strip()

    # Strip markdown code fences if present
    match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()

    # Try parsing directly
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Last resort: find first { ... } block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))

    raise ValueError(f"No valid JSON found in response: {text[:200]}")


_LANG_NAMES = {
    "cs": "Czech", "sk": "Slovak", "de": "German", "en": "English",
    "fr": "French", "ja": "Japanese", "ko": "Korean", "pt": "Portuguese",
}


def classify_destination(query: str, client: Anthropic, market: MarketConfig | None = None) -> DestinationInfo | None:
    """Classify a query as a travel destination. Returns None if not a valid destination."""
    country_name = market.country_name if market else "Česká republika"
    language = market.language if market else "cs"
    lang_name = _LANG_NAMES.get(language, language)
    is_czech_market = language == "cs"

    # For CZ market, local = cs, so we only need two names
    # For other markets, we need local + cs + en
    if is_czech_market:
        name_fields = (
            '  "destination_name": "string (English canonical name)",\n'
            '  "destination_name_local": "string (česky)",\n'
            '  "destination_name_cs": "string (česky, same as local)",\n'
        )
    else:
        name_fields = (
            f'  "destination_name": "string (English canonical name)",\n'
            f'  "destination_name_local": "string (in {lang_name})",\n'
            f'  "destination_name_cs": "string (in Czech)",\n'
        )

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"""Analyze this Google Trends search query from the {country_name} market: "{query}"

Decide if this is a FOREIGN travel destination suitable for content gap analysis.

DISCARD (return {{"is_destination": false}}):
- Services and platforms: Invia, Airbnb, Booking, Kiwi
- TV shows, competitions: Love Island, Amazing Race
- Generic terms: dovolená, last minute, all inclusive, dovolenka
- Domestic/local locations within {country_name}
- Overly broad destinations (entire countries like Austria, Greece, Croatia) — too wide

KEEP (return full JSON):
- Specific foreign destinations: Lake Braies, Seceda, Brenta, Valbona
- Specific regions: Dolomites, Albanian Alps, Cappadocia
- Smaller/specific countries: Oman, Georgia, Albania, Iceland

If the query is NOT a suitable foreign destination, respond ONLY:
{{"is_destination": false}}

If it IS a suitable destination, respond ONLY:
{{
  "is_destination": true,
{name_fields}  "country": "string",
  "region": "string",
  "activity_type": "string",
  "season": "string (best season)"
}}""",
        }],
    )

    raw_text = response.content[0].text
    logger.debug(f"Claude classify response for '{query}': {raw_text[:300]}")

    result = _extract_json(raw_text)

    if not result.get("is_destination", False):
        logger.info(f"Skipping non-destination query: '{query}'")
        return None

    # Fallback: if local/cs missing, fill from each other or from English name
    name_en = result.get("destination_name", "")
    name_local = result.get("destination_name_local", "")
    name_cs = result.get("destination_name_cs", "")

    if not name_local:
        name_local = name_cs or name_en
    if not name_cs:
        name_cs = name_local or name_en

    return DestinationInfo(
        destination_name=name_en,
        destination_name_local=name_local,
        destination_name_cs=name_cs,
        country=result["country"],
        region=result["region"],
        activity_type=result["activity_type"],
        season=result["season"],
    )


def generate_verdict(
    destination_name: str,
    trend_data: dict,
    content_gap_data: dict,
    client: Anthropic,
    market: MarketConfig | None = None,
) -> str:
    country_name = market.country_name if market else "Česká republika"
    language = market.language if market else "cs"
    lang_name = _LANG_NAMES.get(language, language)

    perspective_note = ""
    if language != "cs":
        perspective_note = (
            f"\nDŮLEŽITÉ: Hodnotíš content gap z pohledu uživatelů z trhu {country_name}. "
            f"Ti hledají obsah v {lang_name.lower()}čině. "
            f"Verdikt piš ČESKY, ale perspektiva = {country_name} trh."
        )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": f"""Na základě těchto dat vygeneruj stručný verdikt (3-5 vět česky) o příležitosti pro cestovatelský obsah o destinaci "{destination_name}" cílený na uživatele z {country_name}.
{perspective_note}
Trend data:
{json.dumps(trend_data, ensure_ascii=False, indent=2)}

Content gap data:
{json.dumps(content_gap_data, ensure_ascii=False, indent=2)}

Zahrň: proč to trenduje, jak velký je content gap pro {lang_name.lower()} obsah, jaký typ obsahu by měl největší šanci uspět.
Odpověz POUZE textem verdiktu česky, bez JSON.""",
        }],
    )

    return response.content[0].text.strip()

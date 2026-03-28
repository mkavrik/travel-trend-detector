from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from anthropic import Anthropic

from src.config import get_env

logger = logging.getLogger(__name__)


@dataclass
class DestinationInfo:
    destination_name: str
    destination_name_cs: str
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


def classify_destination(query: str, client: Anthropic) -> DestinationInfo | None:
    """Classify a query as a travel destination. Returns None if not a valid destination."""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"""Analyzuj tento Google Trends search query z českého trhu: "{query}"

Rozhodni, jestli jde o ZAHRANIČNÍ cestovatelskou destinaci vhodnou pro content gap analýzu.

ZAHOĎ (vrať {{"is_destination": false}}):
- Služby a platformy: Invia, Airbnb, Booking, Kiwi
- TV pořady, soutěže: Love Island, Amazing Race
- Obecné pojmy: dovolená, last minute, all inclusive
- České/lokální lokace: ferraty Hluboká, Český ráj, Sněžka
- Příliš obecné destinace (celé země jako Rakousko, Řecko, Chorvatsko) — jsou moc široké

NECH (vrať plný JSON):
- Konkrétní zahraniční destinace: Jezero Braies, Seceda, Brenta, Valbona
- Konkrétní regiony: Dolomity, Albánské Alpy, Kappadokie
- Menší/specifické země: Omán, Gruzie, Albánie, Island

Pokud query NENÍ vhodná zahraniční destinace, odpověz POUZE:
{{"is_destination": false}}

Pokud JE vhodná destinace, odpověz POUZE:
{{
  "is_destination": true,
  "destination_name": "string (anglicky)",
  "destination_name_cs": "string (česky)",
  "country": "string",
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

    return DestinationInfo(
        destination_name=result["destination_name"],
        destination_name_cs=result["destination_name_cs"],
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
) -> str:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": f"""Na základě těchto dat vygeneruj stručný verdikt (3-5 vět česky) o příležitosti pro cestovatelský obsah o destinaci "{destination_name}".

Trend data:
{json.dumps(trend_data, ensure_ascii=False, indent=2)}

Content gap data:
{json.dumps(content_gap_data, ensure_ascii=False, indent=2)}

Zahrň: proč to trenduje, jak velký je content gap, jaký typ obsahu by měl největší šanci uspět.
Odpověz POUZE textem verdiktu, bez JSON.""",
        }],
    )

    return response.content[0].text.strip()

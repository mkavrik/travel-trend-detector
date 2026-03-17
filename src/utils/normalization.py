from __future__ import annotations

import re
import unicodedata


def normalize_destination_name(name: str) -> str:
    """Normalize destination name for deduplication and comparison."""
    name = name.strip().lower()
    # Remove diacritics for comparison
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Remove common suffixes
    for suffix in ["dovolená", "dovolena", "cestování", "cestovani", "turistika", "zájezd", "zajezd"]:
        ascii_name = ascii_name.replace(suffix, "").strip()
    # Collapse whitespace
    ascii_name = re.sub(r"\s+", " ", ascii_name).strip()
    return ascii_name


def slugify(name: str) -> str:
    """Create URL-friendly slug from destination name."""
    name = normalize_destination_name(name)
    slug = re.sub(r"[^a-z0-9]+", "-", name)
    return slug.strip("-")

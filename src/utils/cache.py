from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Callable

from src.config import CACHE_DIR

logger = logging.getLogger(__name__)


def _cache_path(key: str) -> Path:
    safe_key = hashlib.sha256(key.encode()).hexdigest()[:16]
    return CACHE_DIR / f"{safe_key}.json"


def cached_request(key: str, fetcher: Callable[[], Any]) -> Any:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(key)

    if path.exists():
        logger.debug(f"Cache hit: {key}")
        with open(path) as f:
            return json.load(f)

    logger.debug(f"Cache miss: {key}")
    data = fetcher()

    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return data


def clear_cache() -> int:
    if not CACHE_DIR.exists():
        return 0
    files = list(CACHE_DIR.glob("*.json"))
    for f in files:
        f.unlink()
    return len(files)

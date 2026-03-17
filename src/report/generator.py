from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.analysis.opportunity import Destination
from src.config import REPORTS_DIR

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _get_jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        keep_trailing_newline=True,
    )


def generate_report(
    destinations: list[Destination],
    market_code: str,
    week: str,
    raw_data: dict | None = None,
) -> Path:
    report_dir = REPORTS_DIR / f"{week}-{market_code}"
    dest_dir = report_dir / "destinations"
    raw_dir = report_dir / "raw-data"

    report_dir.mkdir(parents=True, exist_ok=True)
    dest_dir.mkdir(exist_ok=True)
    raw_dir.mkdir(exist_ok=True)

    env = _get_jinja_env()
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # README.md — executive summary
    readme_template = env.get_template("readme.md.j2")
    readme_content = readme_template.render(
        week=week,
        market_code=market_code,
        destinations=destinations,
        top_5=destinations[:5],
        generated_at=generated_at,
    )
    (report_dir / "README.md").write_text(readme_content, encoding="utf-8")

    # Per-destination detail pages
    dest_template = env.get_template("destination.md.j2")
    for dest in destinations:
        slug = dest.name.lower().replace(" ", "-").replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u").replace("ý", "y").replace("č", "c").replace("ř", "r").replace("š", "s").replace("ž", "z").replace("ě", "e").replace("ů", "u")
        content = dest_template.render(dest=dest, week=week, market_code=market_code)
        (dest_dir / f"{slug}.md").write_text(content, encoding="utf-8")

    # methodology.md
    method_template = env.get_template("methodology.md.j2")
    method_content = method_template.render(
        week=week,
        market_code=market_code,
        generated_at=generated_at,
    )
    (report_dir / "methodology.md").write_text(method_content, encoding="utf-8")

    # Raw data
    if raw_data:
        for name, data in raw_data.items():
            (raw_dir / f"{name}.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    logger.info(f"Report generated: {report_dir}")
    return report_dir

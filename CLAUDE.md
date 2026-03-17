# Travel Trend × Content Gap Detector

## Účel projektu

Systém pro detekci cestovatelských trendů a identifikaci content gap příležitostí. Odpovídá na otázku: **"Jaké destinace aktuálně trendují na daném trhu, a které z nich ještě nemají dostatek kvalitního obsahu v lokálním jazyce?"**

## Aktuální scope (PoC — fáze 1)

- **Jeden trh:** Česká republika (CZ)
- **Výstup:** Markdown report v Git repozitáři
- **Spouštění:** Manuální z terminálu (jednorázový běh)
- **Cíl:** Ověřit kvalitu dat, scoring modelu a insightů před rozšířením

## Architektura

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Data Collectors │───▶│  Analysis Engine  │───▶│ Report Generator│
│                  │    │                  │    │                  │
│ - Google Trends  │    │ - Trend scoring  │    │ - Markdown files │
│ - Instagram      │    │ - Deseasoning    │    │ - Git commit     │
│ - Google Search  │    │ - Content gap    │    │                  │
│ - X/Twitter      │    │ - Claude AI      │    │                  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Technologie

- **Jazyk:** Python 3.11+
- **API služby:** SerpAPI (Google Trends + Google Search), Apify (Instagram), Claude API (analýza)
- **Výstup:** Markdown soubory v adresářové struktuře

## Adresářová struktura

```
travel-trend-detector/
├── CLAUDE.md                    ← Tento soubor (projektový kontext)
├── README.md                    ← Uživatelská dokumentace
├── pyproject.toml               ← Python dependencies
├── .env.example                 ← Šablona pro API klíče
├── .gitignore
├── src/
│   ├── __init__.py
│   ├── main.py                  ← CLI entry point
│   ├── config.py                ← Konfigurace trhů, seed queries, váhy
│   ├── collectors/
│   │   ├── __init__.py
│   │   ├── google_trends.py     ← SerpAPI Google Trends collector
│   │   ├── instagram.py         ← Apify Instagram hashtag collector
│   │   ├── google_search.py     ← SerpAPI Google Search (content gap)
│   │   └── twitter.py           ← X/Twitter collector (volitelný)
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── trend_scorer.py      ← Trend Score výpočet + desezónování
│   │   ├── content_gap.py       ← Content Gap Score výpočet
│   │   ├── opportunity.py       ← Opportunity Score + klasifikace
│   │   └── claude_analyzer.py   ← Claude API volání pro sémantickou analýzu
│   ├── report/
│   │   ├── __init__.py
│   │   ├── generator.py         ← Markdown report generátor
│   │   └── templates/           ← Jinja2 šablony pro MD soubory
│   │       ├── readme.md.j2
│   │       ├── destination.md.j2
│   │       └── methodology.md.j2
│   └── utils/
│       ├── __init__.py
│       ├── cache.py             ← Lokální cache pro API odpovědi
│       └── normalization.py     ← Normalizace názvů destinací
├── config/
│   └── markets/
│       └── cz.yaml              ← Konfigurace CZ trhu (seed queries, hashtags)
├── reports/                     ← Generované reporty (gitovane)
│   └── .gitkeep
└── tests/
    ├── test_collectors.py
    ├── test_scoring.py
    └── fixtures/                ← Ukázková API data pro testy
```

## Konfigurace (config/markets/cz.yaml)

```yaml
market:
  code: "CZ"
  language: "cs"
  country_name: "Česká republika"
  google_trends_geo: "CZ"
  timezone: "Europe/Prague"

seed_queries:
  general:
    - "dovolená 2026"
    - "kam na dovolenou"
    - "nejlepší destinace léto"
    - "kam na výlet zahraničí"
    - "levná dovolená"
  active:
    - "treking zahraničí"
    - "hiking evropa"
    - "cyklo dovolená zahraničí"
    - "ferraty"
    - "via ferrata"
  seasonal:
    - "lyžování alpy"
    - "letní dovolená moře"
    - "vánoční trhy evropa"
    - "podzimní výlet"
  specific_control:  # Známé trendy pro validaci
    - "dolomity"
    - "albánie dovolená"
    - "gruzie cestování"
    - "island"

instagram_hashtags:
  generic:
    - "dovolena"
    - "cestovani"
    - "vylet"
    - "cestujeme"
    - "kamnavylet"
    - "travel"
  destination_template: "{destination_cs}"  # Dynamicky doplněno

google_search_templates:
  - "{destination} dovolená průvodce"
  - "{destination} turistika blog"
  - "{destination} cestopis"
  - "{destination} tipy na výlet"

scoring:
  trend_weights:
    google_trends: 0.50
    instagram_velocity: 0.25
    twitter_velocity: 0.15
    cross_platform_bonus: 0.10
  content_gap_weights:
    search_quality: 0.40
    freshness: 0.30
    language_quality: 0.20
    social_coverage: 0.10
  time_windows:
    short_term_weeks: 4
    medium_term_months: 12
    long_term_years: 3  # Pro budoucí fázi
```

## Scoring model

### Trend Score (0–100)
- Google Trends rising score: 50 %
- Instagram hashtag velocity: 25 %
- X/Twitter mentions velocity: 15 %
- Cross-platform konfirmace bonus: 10 %

### Content Gap Score (0–100)
- Kvalita top 10 Google Search výsledků (inverzní): 40 %
- Freshness výsledků (starší = vyšší gap): 30 %
- Jazyková kvalita (nativní vs přeložené): 20 %
- Social coverage (lokální influenceři/blogeři): 10 %

### Opportunity Score
```
Opportunity = (Trend Score × Content Gap Score) / 100
```

### Trend klasifikace
- 🚀 **Breakout** — nové query, dříve neexistovalo
- 📈 **Accelerating** — existující, ale letos výrazně silnější než loni
- 🔄 **Seasonal Peak** — roste srovnatelně s minulými roky
- 📉 **Fading** — letos slabší než loni

## Konvence

- **Python:** PEP 8, type hints, docstrings
- **Názvy souborů:** snake_case
- **Git:** conventional commits (`feat:`, `fix:`, `docs:`)
- **Env vars:** prefix `TTD_` (Travel Trend Detector)
- **Logování:** `logging` modul, level INFO default
- **API volání:** vždy s retry + exponential backoff
- **Cache:** JSON soubory v `.cache/` (gitignored)

## Budoucí fáze (NEREŠIT teď)

- Fáze 2: Automatizace (weekly cron via OpenClaw)
- Fáze 3: Přidání dalších trhů (DE, UK, JP, KR, US, BR, FR)
- Fáze 4: Cross-market analýza
- Fáze 5: Automatická lokalizace a publikace obsahu

## Jak spustit

```bash
# Instalace
pip install -e .

# Konfigurace API klíčů
cp .env.example .env
# Vyplnit: TTD_SERPAPI_KEY, TTD_APIFY_TOKEN, TTD_ANTHROPIC_KEY

# Jednorázový běh pro CZ trh
python -m src.main --market cz --week 2026-W12

# Výstup v:
# reports/2026-W12-CZ/README.md
# reports/2026-W12-CZ/destinations/*.md
# reports/2026-W12-CZ/raw-data/*.json
```

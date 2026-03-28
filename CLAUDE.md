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
│   (rising+top)   │    │ - Volume filter  │    │ - 3-part README  │
│ - Instagram      │    │ - Cross-platform │    │ - Per-dest pages │
│ - Google Search  │    │ - Content gap    │    │ - Raw JSON data  │
│                  │    │ - Claude AI      │    │                  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Technologie

- **Jazyk:** Python 3.11+
- **API služby:** SerpAPI (Google Trends + Google Search), Apify (Instagram), Claude API (analýza)
- **Claude modely:** Haiku 4.5 (klasifikace destinací), Sonnet 4.6 (content gap + verdikty)
- **Model IDs:** `claude-haiku-4-5-20251001`, `claude-sonnet-4-6`
- **Výstup:** Markdown soubory v adresářové struktuře

## Adresářová struktura

```
travel-trend-detector/
├── CLAUDE.md                    ← Tento soubor (projektový kontext)
├── TECHNICAL_SPEC.md            ← Detailní technická specifikace
├── README.md                    ← Uživatelská dokumentace
├── pyproject.toml               ← Python dependencies
├── .env.example                 ← Šablona pro API klíče
├── .gitignore
├── src/
│   ├── __init__.py
│   ├── main.py                  ← CLI entry point (6-step pipeline)
│   ├── config.py                ← Konfigurace trhů, seed queries, váhy
│   ├── collectors/
│   │   ├── __init__.py
│   │   ├── google_trends.py     ← SerpAPI Google Trends (rising + top queries)
│   │   ├── instagram.py         ← Apify Instagram hashtag collector
│   │   └── google_search.py     ← SerpAPI Google Search (content gap, per-query results)
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── trend_scorer.py      ← Trend Score + volume filter + peak-based YoY
│   │   ├── content_gap.py       ← Content Gap Score + Claude assessment
│   │   ├── opportunity.py       ← Destination dataclass, scoring, timeline, categorization
│   │   └── claude_analyzer.py   ← Claude API: destination classification + verdicts
│   ├── report/
│   │   ├── __init__.py
│   │   ├── generator.py         ← Markdown report generátor
│   │   └── templates/           ← Jinja2 šablony pro MD soubory
│   │       ├── readme.md.j2     ← 3 sekce: both/rising/top
│   │       ├── destination.md.j2 ← Detailní report s sparkline + tabulkou
│   │       └── methodology.md.j2
│   └── utils/
│       ├── __init__.py
│       ├── cache.py             ← Lokální cache pro API odpovědi (.cache/)
│       └── normalization.py     ← Normalizace názvů destinací
├── config/
│   └── markets/
│       └── cz.yaml              ← Konfigurace CZ trhu (43 seed queries, 8 kategorií)
├── reports/                     ← Generované reporty (gitovane)
│   ├── 2026-W12-CZ/
│   └── 2026-W13-CZ/
└── tests/
    ├── test_collectors.py
    ├── test_scoring.py
    └── fixtures/
```

## Pipeline (6 kroků)

1. **Collect Google Trends** — 43 seed queries × 2 volání (interest_over_time + related_queries)
2. **Collect Instagram** (volitelné, `--skip-instagram`)
3. **Classify destinations** — Claude Haiku klasifikuje rising + top queries jako destinace
4. **Volume filter** — interest_over_time pro každou destinaci, filtr zero/low/insufficient
5. **Score & rank** — Trend Score + Content Gap Score + Opportunity Score
6. **Generate report** — Jinja2 šablony → Markdown soubory

## Seed queries (config/markets/cz.yaml)

8 kategorií, 43 queries celkem:
- **general** (6): dovolená, zájezd, kam na dovolenou, last minute, letenky, cestování
- **beach** (4): dovolená moře, dovolená pláž, all inclusive, ostrov dovolená
- **active** (7): ferraty, via ferrata, treking, hiking, cyklo dovolená, horská turistika, lezení
- **winter** (3): lyžování, ski resort, zimní dovolená
- **city** (3): víkend ve městě, city break, památky
- **style** (6): road trip, kemping, glamping, wellness víkend, dovolená s dětmi, romantická dovolená
- **regions** (10): chorvatsko, řecko, itálie, španělsko, turecko, egypt, thajsko, japonsko, alpy, dolomity
- **control** (4): albánie, gruzie, omán, zanzibar

## Scoring model

### Trend Score (0–100)
- Google Trends momentum: 60 % (peak-based YoY)
- Instagram hashtag velocity: 30 %
- Cross-platform bonus: 10 %
- **Filtry (aplikovány sekvenčně):**
  - `insufficient_data` (≤2 nenulové měsíce): ×0.30
  - `low_volume` (avg 4w < 10): ×0.50
  - `zero` (avg 4w = 0): vyřazení
  - Cross-platform confirmed (IG velocity > 30%): +10 bodů
  - Cross-platform unconfirmed: ×0.80

### Content Gap Score (0–100)
- Kvalita top 10 výsledků (Claude AI): 40 %
- Freshness (starší = vyšší gap): 30 %
- Jazyková kvalita (české znaky): 20 %
- Social coverage: 10 %

### Opportunity Score
```
Trending:   Opportunity = (Trend Score × Content Gap) / 100
Evergreen:  Opportunity = (Popularity Score × Content Gap) / 100
Both:       Opportunity = max(Trending, Evergreen) + 15 (bonus)
```

### Tři typy příležitostí
- 🔥 **Trending+Evergreen** (`source: both`) — v rising I top queries, +15 bonus
- 🚀 **Trending** (`source: rising`) — jen rising queries, nové trendy
- 🏔️ **Evergreen** (`source: top`) — jen top queries, stabilní zájem, řazeno dle Content Gap

### Trend klasifikace (peak-based)
- 🚀 **Breakout** — previous_4w peak < 5 AND current_4w peak > 30
- 📈 **Accelerating** — YoY peak change > 50 %
- 🔄 **Seasonal Peak** — -20 % < YoY < 50 %
- 📉 **Fading** — YoY < -20 %

## Destinační report obsahuje

1. **Metadat tabulka:** Trend Score (raw + adjusted), Volume assessment, Cross-platform, Search volume proxy, Content Gap, Opportunity, typ příležitosti, popularity score
2. **"Proč je to trend?":**
   - Rising/top query info
   - Sparkline 12 měsíců (všechna týdenní data na jednom řádku)
   - Detail posledních 8 týdnů (tabulka s bary)
   - Sezónní srovnání (current 4w vs same 4w last year, peak-based)
3. **"Jak je to pokryté obsahem?":**
   - Top 5 Google Search výsledků (title + link + datum + jazyk)
   - Pokrytí: čeština vs jiný jazyk, aktuální vs staré
   - Sub-skóre Content Gap (quality + freshness + language)
   - Content types found/missing
   - Claude AI zhodnocení
4. **"Verdikt":** 3–5 vět česky od Claude Sonnet

## Filtry a ochrana proti false positives

1. **Volume filtr** (`trend_scorer.py`): `zero` → vyřazení, `insufficient_data` (≤2 nonzero months) → ×0.30, `low_volume` (avg < 10) → ×0.50
2. **Cross-platform validace**: IG velocity > 30% = confirmed (+10), jinak unconfirmed (×0.80)
3. **Search volume proxy** (`content_gap.py`): niche (<5K) / emerging / established / mainstream
4. **Search engine URL filtr** (`google_search.py`): odstraňuje seznam.cz/google/bing/yahoo search pages

## Raw data formát (search-results.json)

```json
{
  "Destinace": {
    "total_results": 36400,
    "queries": [
      {
        "query": "destinace dovolená průvodce",
        "results": [{"position": 1, "title": "...", "link": "...", ...}]
      }
    ]
  }
}
```

## Konvence

- **Python:** PEP 8, type hints
- **Názvy souborů:** snake_case
- **Git:** conventional commits (`feat:`, `fix:`, `docs:`)
- **Env vars:** prefix `TTD_` (Travel Trend Detector)
- **Logování:** `logging` modul, level INFO default
- **API volání:** vždy s retry + exponential backoff (3 attempts, 2^n seconds)
- **Cache:** JSON soubory v `.cache/` (gitignored), SHA256 hash jako filename

## Jak spustit

```bash
# Instalace
pip install -e .

# Konfigurace API klíčů
cp .env.example .env
# Vyplnit: TTD_SERPAPI_KEY, TTD_APIFY_TOKEN, TTD_ANTHROPIC_KEY

# Jednorázový běh pro CZ trh
python -m src.main --market cz --week 2026-W13

# S přeskočením Instagramu a automatickým potvrzením
python -m src.main --market cz --week 2026-W13 --skip-instagram -y

# Dry run (jen data collection + scoring, bez reportu)
python -m src.main --market cz --dry-run -y

# Výstup v:
# reports/2026-W13-CZ/README.md          (3-sekční přehled)
# reports/2026-W13-CZ/destinations/*.md   (detailní stránky)
# reports/2026-W13-CZ/raw-data/*.json     (surová data)
```

## Odhad API volání na report

- Google Trends: ~43 seeds × 2 = 86 SerpAPI calls
- Volume checks: ~100–150 interest_over_time calls
- Google Search: ~30 destinations × 4 templates = 120 calls
- Claude API: ~800–1000 Haiku (classification) + ~60 Sonnet (gap + verdict)
- **Celkem: ~300–350 SerpAPI + ~1000 Claude calls**

## Budoucí fáze (NEREŠIT teď)

- Fáze 2: Automatizace (weekly cron)
- Fáze 3: Přidání dalších trhů (DE, UK, JP, KR, US, BR, FR)
- Fáze 4: Cross-market analýza
- Fáze 5: Automatická lokalizace a publikace obsahu

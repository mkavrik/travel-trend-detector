# Travel Trend × Content Gap Detector

## Co to je

Python CLI nástroj, který každý týden detekuje trending cestovatelské destinace na zvoleném trhu a identifikuje, kde chybí kvalitní obsah. Výstupem je Markdown report s evidence-based zdůvodněním každého trendu.

## Rychlý start

### 1. Předpoklady

- Python 3.11+
- Git
- Claude Code (viz TECHNICAL_SPEC.md sekce 2)
- API klíče (viz níže)

### 2. API účty

| Služba | Registrace | Potřebuješ |
|--------|-----------|-------------|
| SerpAPI | [serpapi.com/users/sign_up](https://serpapi.com/users/sign_up) | API Key |
| Apify | [console.apify.com/sign-up](https://console.apify.com/sign-up) | API Token |
| Anthropic | [console.anthropic.com](https://console.anthropic.com) | API Key |

### 3. Instalace

```bash
git clone <repo-url>
cd travel-trend-detector
cp .env.example .env
# Vyplň API klíče v .env
pip install -e .
```

### 4. Spuštění

```bash
# Kompletní report pro CZ trh, aktuální týden
python -m src.main --market cz

# Konkrétní týden
python -m src.main --market cz --week 2026-W12

# Dry run (jen stáhne data, nevygeneruje report)
python -m src.main --market cz --dry-run

# Bez Instagramu (rychlejší, levnější)
python -m src.main --market cz --skip-instagram
```

### 5. Výstup

```
reports/2026-W12-CZ/
├── README.md              ← Top příležitosti + executive summary
├── destinations/
│   ├── albanske-alpy.md   ← Detail + evidence + verdikt
│   ├── dolomity.md
│   └── ...
├── methodology.md
└── raw-data/
    ├── google-trends.json
    ├── instagram.json
    └── search-results.json
```

## Dokumentace

- **CLAUDE.md** — Projektový kontext (čte ho Claude Code automaticky)
- **TECHNICAL_SPEC.md** — Kompletní technická specifikace, API reference, setup guide

## Fáze projektu

- [x] Fáze 0: Specifikace a design
- [ ] **Fáze 1: PoC — jeden trh (CZ), manuální spouštění** ← AKTUÁLNĚ
- [ ] Fáze 2: Automatizace (weekly cron)
- [ ] Fáze 3: Multi-market (DE, UK, JP, KR, US, BR, FR)
- [ ] Fáze 4: Cross-market analýza
- [ ] Fáze 5: Automatická lokalizace a publikace

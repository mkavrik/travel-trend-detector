# Technická specifikace: Travel Trend × Content Gap Detector

## Obsah

1. Služby a účty — co si pořídit a kde
2. Nastavení Claude Code — krok za krokem
3. Implementační plán — co vyvinout a v jakém pořadí
4. API reference — přesné endpointy a datové struktury
5. Odhadované náklady

---

## 1. Služby a účty

### 1.1 SerpAPI — Google Trends + Google Search

**Co to je:** API služba, která poskytuje strukturovaná data z Google Trends a Google Search výsledků. Páteř celého systému.

**Proč SerpAPI a ne pytrends:** Pytrends je neoficiální Python knihovna, která scrapuje Google Trends přímo. Je zdarma, ale nestabilní — Google pravidelně mění HTML a pytrends přestane fungovat. SerpAPI je placená, ale stabilní a vrací čistý JSON. Pro PoC, kde chceme ověřit koncept a ne řešit broken scraper, je SerpAPI správná volba.

**Kde se registrovat:**
- Web: https://serpapi.com
- Registrace: https://serpapi.com/users/sign_up
- Pricing: https://serpapi.com/pricing

**Doporučený plán pro PoC:**
- **Developer plan: $75/měs.** — 5 000 searches/měsíc
- Pro PoC s jedním trhem (CZ) je to víc než dost
- Tip: SerpAPI nabízí 100 free searches po registraci — stačí na první test

**Kolik searches PoC spotřebuje (odhad na 1 týdenní report):**
- Google Trends queries: ~20 seed queries × 2 (interest over time + related queries) = 40
- Google Trends historický kontext (12 měsíců zpětně): ~20 queries
- Google Search pro content gap (top 20 destinací × 4 search templates): ~80
- **Celkem: ~140 searches na 1 report** → Developer plan stačí na ~35 reportů/měsíc

**API klíč:**
- Po registraci: Dashboard → API Key (kopírovat)
- Uložit do `.env` jako `TTD_SERPAPI_KEY`

**Klíčové endpointy, které budeme používat:**

```
# Google Trends — Interest over time
GET https://serpapi.com/search?engine=google_trends&q={query}&geo=CZ&date=today 12-m

# Google Trends — Related queries (rising)
GET https://serpapi.com/search?engine=google_trends&q={query}&geo=CZ&data_type=RELATED_QUERIES

# Google Search — Content gap analysis
GET https://serpapi.com/search?engine=google&q={query}&gl=cz&hl=cs&num=10
```

---

### 1.2 Apify — Instagram data

**Co to je:** Platforma pro web scraping s předpřipravenými "Actors" (scrapery). Použijeme Instagram Hashtag Scraper pro sběr dat o cestovatelských hashtagech.

**Kde se registrovat:**
- Web: https://apify.com
- Registrace: https://console.apify.com/sign-up
- Instagram Hashtag Scraper: https://apify.com/apify/instagram-hashtag-scraper

**Doporučený plán pro PoC:**
- **Free tier: $5 kredit/měsíc** — zdarma, stačí na ~2 000 výsledků
- Pokud nestačí: **Starter: $49/měs.** — ~12 600 výsledků za nižší sazbu

**Kolik výsledků PoC spotřebuje (odhad):**
- 15 generických CZ travel hashtagů × 50 postů = 750 výsledků
- 20 destinačních hashtagů × 30 postů = 600 výsledků
- **Celkem: ~1 350 výsledků** → Free tier stačí na 1 report

**API token:**
- Po registraci: Settings → Integrations → API token
- Uložit do `.env` jako `TTD_APIFY_TOKEN`

**Klíčový Actor:**
```
# Instagram Hashtag Scraper
Actor ID: apify/instagram-hashtag-scraper

# Spuštění přes API:
POST https://api.apify.com/v2/acts/apify~instagram-hashtag-scraper/runs
{
  "hashtags": ["dovolena", "cestovani"],
  "resultsType": "posts",
  "resultsLimit": 50
}
```

---

### 1.3 Claude API — sémantická analýza

**Co to je:** API přístup k Claude modelům pro sémantickou klasifikaci destinací a kvalitativní hodnocení content gapu.

**Jak získat přístup:**
- Ty máš Claude MAX účet — ten zahrnuje přístup přes Claude Code
- Pro API volání z Python skriptu máš dvě možnosti:
  - **Možnost A (doporučená pro PoC):** Použít Anthropic API key z Console
    - Web: https://console.anthropic.com
    - Settings → API Keys → Create Key
    - Uložit do `.env` jako `TTD_ANTHROPIC_KEY`
  - **Možnost B:** Volat Claude přes Claude Code subproces (složitější, nedoporučuji pro PoC)

**Doporučený model:**
- **Claude Haiku 4.5** pro klasifikaci destinací a jednoduché analýzy (levný, rychlý)
- **Claude Sonnet 4.6** pro kvalitativní hodnocení content gapu a generování verdiktů (kvalitnější)

**Odhadovaná spotřeba na 1 report:**
- Klasifikace 50 trending queries: ~20K input tokens, ~5K output → Haiku: ~$0.02
- Content gap analýza 20 destinací: ~100K input tokens, ~20K output → Sonnet: ~$0.90
- **Celkem: ~$1 na report**

---

### 1.4 X/Twitter — volitelný zdroj (nižší priorita)

Pro PoC doporučuji X/Twitter **vynechat** a přidat až v iteraci 2, pokud se ukáže, že Google Trends + Instagram dávají nedostatečný signál. Důvody:

- X API Basic tier stojí $100/měs. — drahé pro jeden doplňkový signál
- Alternativa přes Apify (X/Twitter Scraper) je levnější, ale méně spolehlivá
- Pro CZ trh je X méně relevantní než Instagram

**Pokud ho budeš chtít přidat později:**
- Apify Actor: https://apify.com/apidojo/tweet-scraper
- Nebo X API: https://developer.x.com (Basic: $100/měs., 10K tweets/měs.)

---

### Souhrn: Co si pořídit pro PoC

| Služba | Plán | Cena | Kde |
|--------|------|------|-----|
| **SerpAPI** | Developer | $75/měs. | serpapi.com/users/sign_up |
| **Apify** | Free | $0 (s $5 kreditem) | console.apify.com/sign-up |
| **Anthropic API** | Pay-as-you-go | ~$1/report | console.anthropic.com |
| **Claude MAX** (už máš) | MAX 5× | $100/měs. | — |
| **X/Twitter** | Přeskočit | $0 | — |

**Celkové měsíční náklady PoC: ~$76** (bez Claude MAX, který už platíš)

---

## 2. Nastavení Claude Code

Máš Claude MAX účet, takže máš na Claude Code plný přístup. Tady je krok za krokem, co udělat:

### 2.1 Instalace Claude Code

**Na macOS nebo Linux** — otevři Terminal a spusť:

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

**Na Windows** — otevři PowerShell a spusť:

```powershell
irm https://claude.ai/install.ps1 | iex
```

Důležité: Na Windows musíš mít nainstalovaný **Git for Windows** (https://git-scm.com/download/win). Bez něj instalace selže.

Po instalaci **zavři a znovu otevři terminal** (aby se načetla nová PATH).

### 2.2 Ověření instalace

```bash
claude --version
```

Mělo by to vypsat číslo verze. Pokud vidíš "command not found", zkus znovu otevřít terminal.

### 2.3 První přihlášení

```bash
claude
```

Claude Code se zeptá na přihlášení. Otevře se prohlížeč, kde se přihlásíš svým Claude MAX účtem. Po úspěšném přihlášení se vrátíš do terminálu a uvidíš Claude Code welcome screen.

### 2.4 Diagnostika (pokud něco nefunguje)

```bash
claude doctor
```

Tento příkaz zkontroluje tvou konfiguraci, autentizaci a detekuje běžné problémy.

### 2.5 Tvůj první projekt s Claude Code

```bash
# Vytvoř složku pro projekt
mkdir travel-trend-detector
cd travel-trend-detector

# Inicializuj Git repozitář
git init

# Zkopíruj CLAUDE.md do složky (z výstupu tohoto chatu)
# CLAUDE.md je klíčový — Claude Code ho automaticky přečte při startu

# Spusť Claude Code v projektu
claude
```

Když spustíš `claude` ve složce, která obsahuje `CLAUDE.md`, Claude Code si ho automaticky přečte a pochopí kontext projektu. Tohle je zásadní — díky tomu Claude Code bude vědět, co budujeme.

### 2.6 Jak Claude Code používat — základy pro uživatele Cursor

Claude Code se od Cursoru liší — nemá vizuální IDE. Komunikuješ textově v terminálu. Místo klikání píšeš příkazy a instrukce přirozeným jazykem.

**Základní workflow:**

```
> ty:     "Vytvoř základní strukturu projektu podle CLAUDE.md"
> claude: [přečte CLAUDE.md, vytvoří adresáře a soubory]

> ty:     "Implementuj Google Trends collector v src/collectors/google_trends.py"
> claude: [napíše kód, vytvoří soubor]

> ty:     "Spusť testy"
> claude: [spustí pytest, ukáže výsledky]
```

**Užitečné příkazy uvnitř Claude Code session:**

```
/plan         — Přepne do Plan Mode (Claude analyzuje a navrhne, ale nemění soubory)
/help         — Zobrazí nápovědu
/clear        — Vyčistí kontext (začne "od nuly" v aktuální session)
/cost         — Ukáže spotřebu tokenů v aktuální session
```

**Plan Mode — důležité pro začátek:**
Než necháš Claude Code něco implementovat, doporučuji nejdřív zadat `/plan` a pak popsat úkol. Claude navrhne plán bez toho, aby cokoliv měnil. Až plán schválíš, Claude ho vykoná. Je to bezpečnější a dává ti kontrolu.

**Tip:** Claude Code ukládá checkpointy — pokud se něco pokazí, můžeš se vrátit. Ale vždy je dobré mít Git commity jako zálohu.

---

## 3. Implementační plán

### Postup: 7 kroků, od kostry po hotový report

#### Krok 1: Kostra projektu (den 1, ~30 min)

**Zadání pro Claude Code:**
```
Vytvoř základní strukturu projektu podle CLAUDE.md.
Vytvoř pyproject.toml s dependencies:
- httpx (HTTP klient)
- python-dotenv (env vars)
- pyyaml (konfigurace)
- jinja2 (šablony)
- anthropic (Claude API)
- click (CLI)

Vytvoř .env.example, .gitignore, a config/markets/cz.yaml
podle specifikace v CLAUDE.md.
```

#### Krok 2: Google Trends collector (den 1, ~1-2 hod)

**Zadání pro Claude Code:**
```
Implementuj src/collectors/google_trends.py:

1. Funkce fetch_interest_over_time(query, geo, date_range):
   - Volá SerpAPI endpoint engine=google_trends
   - Parametry: q=query, geo=geo (např. "CZ"), date="today 12-m"
   - Vrací časovou řadu [{date, value}, ...]
   - Implementuj retry s exponential backoff (3 pokusy)
   - Cachuj odpovědi do .cache/ (JSON, klíč = hash parametrů)

2. Funkce fetch_related_queries(query, geo):
   - Volá SerpAPI s data_type=RELATED_QUERIES
   - Vrací {rising: [{query, value}, ...], top: [{query, value}, ...]}

3. Funkce collect_trends(market_config) -> TrendData:
   - Projde všechny seed queries z market configu
   - Pro každý query stáhne interest_over_time + related_queries
   - Extrahuje "rising" queries jako kandidáty na trending destinace
   - Vrací strukturovaný objekt se všemi daty

SerpAPI klíč čti z env var TTD_SERPAPI_KEY.
Použij httpx jako HTTP klienta.
```

#### Krok 3: Instagram collector (den 1-2, ~1-2 hod)

**Zadání pro Claude Code:**
```
Implementuj src/collectors/instagram.py:

1. Funkce fetch_hashtag_posts(hashtag, limit=50) -> list[dict]:
   - Volá Apify Actor apify/instagram-hashtag-scraper přes REST API
   - Spustí Actor run, počká na dokončení, stáhne výsledky
   - Vrací seznam postů s: caption, likes, comments_count,
     timestamp, hashtags, location

2. Funkce collect_instagram_data(hashtags: list[str]) -> InstagramData:
   - Projde seznam hashtagů
   - Pro každý stáhne posty
   - Spočítá velocity metriky:
     - posts_last_4_weeks: počet postů za posledních 28 dní
     - posts_previous_4_weeks: počet postů 29-56 dní zpět
     - velocity_change_pct: procentuální změna
   - Vrací strukturovaný objekt

Apify API token čti z env var TTD_APIFY_TOKEN.
Apify API docs: POST https://api.apify.com/v2/acts/{actorId}/runs
Výsledky: GET https://api.apify.com/v2/datasets/{datasetId}/items
```

#### Krok 4: Google Search collector + Content Gap scoring (den 2, ~2-3 hod)

**Zadání pro Claude Code:**
```
Implementuj src/collectors/google_search.py:

1. Funkce search_destination(destination, market_config) -> list[SearchResult]:
   - Pro každý template v google_search_templates (z configu):
     - Vyplní {destination} a zavolá SerpAPI engine=google
     - Parametry: gl=cz, hl=cs, num=10
   - Vrací top 10 výsledků s: title, link, snippet, date (pokud je)

Implementuj src/analysis/content_gap.py:

1. Funkce score_content_gap(search_results, destination, claude_client) -> ContentGapScore:
   - Počet relevantních výsledků v top 10 (inverzní — méně = vyšší gap)
   - Freshness: průměrné stáří výsledků, bonifikace za <6 měsíců
   - Jazyková kvalita: kolik výsledků je v češtině vs. angličtině/jiné
   - Pro kvalitativní assessment zavolej Claude API (Sonnet):
     - Vstup: top 10 search výsledků (title + snippet)
     - Prompt: "Zhodnoť kvalitu cestovatelského obsahu pro destinaci X
       v českém jazyce. Kolik z těchto výsledků je kvalitní, aktuální
       cestovatelský průvodce? Odpověz JSON: {quality_score: 0-100,
       assessment: 'text', content_types_found: [...],
       content_types_missing: [...]}"
   - Vrací ContentGapScore (0-100) + kvalitativní assessment
```

#### Krok 5: Trend scoring + klasifikace (den 2-3, ~2 hod)

**Zadání pro Claude Code:**
```
Implementuj src/analysis/trend_scorer.py:

1. Funkce calculate_trend_score(trends_data, instagram_data) -> float:
   - Aplikuj váhy z configu (google: 50%, ig: 25%, twitter: 15%, cross: 10%)
   - Twitter prozatím 0 (vynecháváme)
   - Přerozděl váhy: google: 60%, instagram: 30%, cross_platform: 10%
   - Cross-platform bonus: pokud destinace trenduje v Google Trends
     I na Instagramu současně, přidej bonus

2. Funkce classify_trend(current_4w, previous_4w, same_period_last_year):
   - Breakout: previous_4w == 0 nebo near-zero, current_4w > threshold
   - Accelerating: current_4w / same_period_last_year > 1.5
   - Seasonal Peak: 0.8 < current_4w / same_period_last_year < 1.5
   - Fading: current_4w / same_period_last_year < 0.8

Implementuj src/analysis/opportunity.py:

1. Funkce calculate_opportunity(trend_score, gap_score) -> float:
   - Opportunity = (trend_score * gap_score) / 100

2. Funkce rank_destinations(destinations: list[Destination]) -> list:
   - Seřaď podle Opportunity Score sestupně
   - Vrať top 20
```

#### Krok 6: Claude sémantická analýza (den 3, ~1-2 hod)

**Zadání pro Claude Code:**
```
Implementuj src/analysis/claude_analyzer.py:

1. Funkce classify_destination(query: str) -> DestinationInfo:
   - Vstup: raw query z Google Trends (např. "valbona theth trek")
   - Claude Haiku prompt: "Identifikuj cestovatelskou destinaci z tohoto
     search query: '{query}'. Odpověz JSON: {destination_name: str,
     destination_name_cs: str, country: str, region: str,
     activity_type: str, season: str}"
   - Vrací strukturované info o destinaci

2. Funkce generate_verdict(destination, trend_data, content_gap_data) -> str:
   - Vstup: všechna data o destinaci
   - Claude Sonnet prompt: "Na základě těchto dat vygeneruj stručný
     verdikt (3-5 vět česky) o příležitosti pro cestovatelský obsah.
     Zahrň: proč to trenduje, jak velký je content gap, jaký typ
     obsahu by měl největší šanci uspět."
   - Vrací lidsky čitelný verdikt pro report

Použij anthropic Python SDK.
API klíč čti z env var TTD_ANTHROPIC_KEY.
```

#### Krok 7: Report generátor + CLI (den 3, ~2-3 hod)

**Zadání pro Claude Code:**
```
Implementuj src/report/generator.py + Jinja2 šablony:

1. Šablona readme.md.j2 — executive summary:
   - Hlavička s týdnem a trhem
   - Top 5 příležitostí (tabulka: destinace, trend score,
     content gap, opportunity, trenduje kde)
   - Per-market highlights (pro budoucí multi-market)
   - Cross-platform signály

2. Šablona destination.md.j2 — detail pro jednu destinaci:
   - Název + Opportunity Score
   - Sekce "Proč je to trend?" s evidence:
     - Google Trends data (čísla, procenta, breakout/accelerating)
     - Instagram data (velocity, počty postů)
     - Sezónní kontext (srovnání s minulým rokem)
   - Sekce "Jak je to pokryté obsahem?":
     - Google Search top 10 analýza
     - Claude kvalitativní assessment
   - Verdikt (generovaný Claudem)

3. Šablona methodology.md.j2:
   - Popis scoring modelu
   - Použité zdroje dat
   - Váhy a prahové hodnoty
   - Datum a čas generování

Implementuj src/main.py jako CLI (click):
  python -m src.main --market cz --week 2026-W12 [--dry-run] [--skip-instagram]

Workflow:
  1. Načti market config
  2. Spusť collectors (Google Trends, Instagram, Google Search)
  3. Spusť analýzu (scoring, content gap, Claude)
  4. Generuj Markdown report do reports/{week}-{market}/
  5. Ulož raw data do reports/{week}-{market}/raw-data/
```

---

## 4. API reference

### 4.1 SerpAPI — Google Trends

**Interest over time:**
```python
import httpx

params = {
    "engine": "google_trends",
    "q": "dolomity",
    "geo": "CZ",
    "date": "today 12-m",  # posledních 12 měsíců
    "api_key": SERPAPI_KEY
}
response = httpx.get("https://serpapi.com/search", params=params)
data = response.json()

# Výstup: data["interest_over_time"]["timeline_data"]
# [{
#   "date": "Mar 10 – 16, 2025",
#   "values": [{"query": "dolomity", "value": "42", "extracted_value": 42}]
# }, ...]
```

**Related queries (rising = trending):**
```python
params = {
    "engine": "google_trends",
    "q": "dovolená 2026",
    "geo": "CZ",
    "data_type": "RELATED_QUERIES",
    "api_key": SERPAPI_KEY
}
response = httpx.get("https://serpapi.com/search", params=params)
data = response.json()

# Výstup: data["related_queries"]
# {
#   "rising": [
#     {"query": "albánie dovolená 2026", "value": 5000},  # 5000 = "Breakout"
#     {"query": "dolomity léto 2026", "value": 340}        # 340 = +340%
#   ],
#   "top": [
#     {"query": "chorvatsko", "value": 100},
#     {"query": "řecko", "value": 85}
#   ]
# }
```

**Parametr `date` — volby:**
```
"today 12-m"    → posledních 12 měsíců (primární pro PoC)
"today 3-m"     → posledních 3 měsíce
"now 7-d"       → posledních 7 dní
"2025-03-01 2026-03-01"  → custom rozsah
```

### 4.2 SerpAPI — Google Search

```python
params = {
    "engine": "google",
    "q": "dolomity turistika průvodce",
    "gl": "cz",       # country
    "hl": "cs",        # language
    "num": 10,         # výsledků
    "api_key": SERPAPI_KEY
}
response = httpx.get("https://serpapi.com/search", params=params)
data = response.json()

# Výstup: data["organic_results"]
# [{
#   "position": 1,
#   "title": "Dolomity — Kompletní průvodce | Cestuj.cz",
#   "link": "https://cestuj.cz/dolomity-pruvodce",
#   "snippet": "Kompletní průvodce po Dolomitech...",
#   "date": "Oct 15, 2024"  # pokud je dostupné
# }, ...]
```

### 4.3 Apify — Instagram Hashtag Scraper

```python
import httpx
import time

APIFY_TOKEN = "..."
ACTOR_ID = "apify~instagram-hashtag-scraper"

# 1. Spuštění Actor run
run_response = httpx.post(
    f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs",
    params={"token": APIFY_TOKEN},
    json={
        "hashtags": ["dovolena", "cestovani"],
        "resultsType": "posts",
        "resultsLimit": 50
    }
)
run_data = run_response.json()["data"]
run_id = run_data["id"]

# 2. Čekání na dokončení
while True:
    status_resp = httpx.get(
        f"https://api.apify.com/v2/actor-runs/{run_id}",
        params={"token": APIFY_TOKEN}
    )
    status = status_resp.json()["data"]["status"]
    if status in ("SUCCEEDED", "FAILED", "ABORTED"):
        break
    time.sleep(5)

# 3. Stažení výsledků
dataset_id = run_data["defaultDatasetId"]
items_resp = httpx.get(
    f"https://api.apify.com/v2/datasets/{dataset_id}/items",
    params={"token": APIFY_TOKEN, "format": "json"}
)
posts = items_resp.json()

# Každý post obsahuje:
# {
#   "caption": "Krásný výhled z Dolomit! #dolomity #hiking",
#   "likesCount": 234,
#   "commentsCount": 12,
#   "timestamp": "2026-03-10T14:22:00.000Z",
#   "hashtags": ["dolomity", "hiking", "cestovani"],
#   "locationName": "Tre Cime di Lavaredo",
#   "ownerUsername": "cestovatel_jan",
#   "url": "https://www.instagram.com/p/..."
# }
```

### 4.4 Anthropic Claude API

```python
from anthropic import Anthropic

client = Anthropic(api_key="...")

# Klasifikace destinace (Haiku — levné)
response = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=500,
    messages=[{
        "role": "user",
        "content": """Identifikuj cestovatelskou destinaci z tohoto
Google Trends search query: "valbona theth trek albánie"

Odpověz POUZE validním JSON:
{
  "destination_name": "string (anglicky)",
  "destination_name_cs": "string (česky)",
  "country": "string",
  "region": "string",
  "activity_type": "string",
  "season": "string (best season)"
}"""
    }]
)
# Parsuj JSON z response.content[0].text

# Content gap verdikt (Sonnet — kvalitnější)
response = client.messages.create(
    model="claude-sonnet-4-6-20250514",
    max_tokens=1000,
    messages=[{
        "role": "user",
        "content": f"""Analyzuj tyto Google Search výsledky pro query
"{query}" v češtině a zhodnoť kvalitu cestovatelského obsahu.

Výsledky:
{search_results_formatted}

Odpověz POUZE validním JSON:
{{
  "quality_score": 0-100,
  "assessment_cs": "stručné zhodnocení v češtině (2-3 věty)",
  "quality_articles_count": number,
  "content_types_found": ["blog", "agentura", "wiki", ...],
  "content_types_missing": ["hiking guide", "practical tips", ...],
  "freshness_assessment": "aktuální/zastaralé/smíšené",
  "language_quality": "nativní/přeložené/smíšené"
}}"""
    }]
)
```

---

## 5. Odhadované náklady

### Jednorázové (setup)
| Položka | Cena |
|---------|------|
| SerpAPI registrace | $0 (100 free searches) |
| Apify registrace | $0 ($5 free kredit) |
| Anthropic Console registrace | $0 |
| Claude MAX (už platíš) | $0 |

### Měsíční provoz (PoC)
| Služba | Cena/měs. | Poznámka |
|--------|-----------|----------|
| SerpAPI Developer | $75 | 5 000 searches, stačí na ~35 reportů |
| Apify Free | $0 | $5 kredit, stačí na ~1-2 reporty |
| Claude API (Haiku + Sonnet) | ~$1-4 | Pay-as-you-go, záleží na počtu reportů |
| **Celkem** | **~$76-79/měs.** | |

### Cena jednoho reportu
| Složka | Cena |
|--------|------|
| SerpAPI (~140 searches) | ~$2.10 |
| Apify (~1 350 výsledků) | ~$2.60 (nebo $0 z free kreditu) |
| Claude API | ~$1.00 |
| **Celkem na report** | **~$3.50-5.70** |

### Tip na úsporu pro PoC fázi
Prvních pár běhů můžeš udělat jen s **SerpAPI free tier (100 searches)** a **Apify free tier ($5)** — bez placení čehokoliv. Stačí to na 1 kompletní testovací report, abys ověřil, že data dávají smysl. Placený SerpAPI plán si poříď až když budeš chtít běžet pravidelně.

---

## Appendix: Časové okno a desezónování

### Jak funguje desezónování v praxi

Pro každou detekovanou destinaci stahujeme z Google Trends 12 měsíců dat. Z nich extrahujeme:

```
current_4w     = průměr posledních 4 týdnů
previous_4w    = průměr 4 týdnů předtím (5-8 týdnů zpět)
same_4w_ly     = průměr stejných 4 týdnů minulý rok (z 12m dat)
```

**Výpočet:**
```python
# Krátkodobý momentum
short_term_change = (current_4w - previous_4w) / max(previous_4w, 1) * 100

# Desezónovaný trend (YoY)
yoy_change = (current_4w - same_4w_ly) / max(same_4w_ly, 1) * 100

# Klasifikace
if previous_4w < 5 and current_4w > 30:
    classification = "breakout"
elif yoy_change > 50:
    classification = "accelerating"
elif -20 < yoy_change < 50:
    classification = "seasonal_peak"
else:
    classification = "fading"
```

Tohle zajistí, že "Chorvatsko" v březnu nebude false positive (roste každý rok), ale "Albánie" v březnu s 2.3× YoY nárůstem ano.

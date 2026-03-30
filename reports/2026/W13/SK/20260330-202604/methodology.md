# Metodologie — 2026-W13 / SK

> Generováno: 2026-03-30 18:30 UTC

## Scoring model

### Trend Score (0–100)

| Zdroj | Váha |
|-------|------|
| Google Trends (rising queries + interest over time) | 60 % |
| Instagram hashtag velocity | 30 % |
| Cross-platform konfirmace bonus | 10 % |

*Poznámka: Twitter/X je v PoC fázi vynechán. Váhy jsou přerozděleny.*

### Content Gap Score (0–100)

| Faktor | Váha |
|--------|------|
| Kvalita top 10 Google Search výsledků (inverzní) | 40 % |
| Freshness výsledků (starší = vyšší gap) | 30 % |
| Jazyková kvalita (nativní vs. přeložené) | 20 % |
| Social coverage | 10 % |

### Opportunity Score

```
Opportunity = (Trend Score × Content Gap Score) / 100
```

### Trend klasifikace

| Klasifikace | Podmínka |
|-------------|----------|
| 🚀 Breakout | Nové query, dříve neexistovalo |
| 📈 Accelerating | Meziroční nárůst > 50 % |
| 🔄 Seasonal Peak | Meziroční změna -20 % až +50 % |
| 📉 Fading | Meziroční pokles > 20 % |

## Zdroje dat

- **Google Trends** via SerpAPI — interest over time (12 měsíců) + related rising queries
- **Instagram** via Apify — hashtag post velocity (4 týdny vs. předchozí 4 týdny)
- **Google Search** via SerpAPI — top 10 výsledků pro content gap analýzu
- **Claude AI** — sémantická klasifikace destinací + kvalitativní hodnocení obsahu

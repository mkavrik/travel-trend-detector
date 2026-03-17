# Claude Code — Tvůj první projekt (krok za krokem)

Tento soubor tě provede od nuly k prvnímu fungujícímu reportu.
Předpokládá, že jsi dosud používal jen Cursor a s Claudem Code nemáš zkušenosti.

---

## Krok 0: Instalace Claude Code

### macOS / Linux
```bash
curl -fsSL https://claude.ai/install.sh | bash
```

### Windows
1. Nainstaluj Git for Windows: https://git-scm.com/download/win
   (výchozí nastavení, klikej "Next" u všeho)
2. Restartuj terminal
3. Otevři PowerShell a spusť:
```powershell
irm https://claude.ai/install.ps1 | iex
```

### Ověření
Zavři terminal, otevři znovu, a zadej:
```bash
claude --version
```
Vidíš číslo verze? Výborně. Pokud ne, spusť `claude doctor`.

---

## Krok 1: Přihlášení

```bash
claude
```

Otevře se prohlížeč → přihlaš se svým Claude MAX účtem → vrať se do terminálu.
Měl bys vidět uvítací obrazovku Claude Code.

Zadej `/exit` pro ukončení (ještě nejsme v projektu).

---

## Krok 2: Připrav projekt

```bash
# Vytvoř složku (nebo ji stáhni z Gitu, pokud už máš repo)
mkdir travel-trend-detector
cd travel-trend-detector
git init

# Zkopíruj všechny soubory z tohoto balíku do složky:
# - CLAUDE.md
# - TECHNICAL_SPEC.md
# - README.md
# - .env.example
# - .gitignore
```

Důležité: **CLAUDE.md musí být v kořeni projektu.** Claude Code ho při startu
automaticky přečte a pochopí, co budujeme.

---

## Krok 3: Nastav API klíče

```bash
cp .env.example .env
```

Otevři `.env` ve svém editoru a vyplň:
- `TTD_SERPAPI_KEY` — z https://serpapi.com/dashboard (po registraci)
- `TTD_APIFY_TOKEN` — z https://console.apify.com → Settings → Integrations
- `TTD_ANTHROPIC_KEY` — z https://console.anthropic.com → API Keys

Pro úplně první test stačí jen SerpAPI (100 free searches po registraci).

---

## Krok 4: Spusť Claude Code v projektu

```bash
cd travel-trend-detector
claude
```

Claude Code přečte CLAUDE.md a porozumí kontextu. Teď mu můžeš zadávat úkoly.

---

## Krok 5: Postav projekt (conversation s Claude Code)

### 5a. Začni s Plan Mode

Napiš do Claude Code:

```
/plan
```

Pak zadej:

```
Přečti CLAUDE.md a TECHNICAL_SPEC.md. Na jejich základě mi navrhni plán
implementace. Začni od kroku 1 (kostra projektu) z TECHNICAL_SPEC.md.
```

Claude ti ukáže plán — co chce vytvořit, jaké soubory, jakou strukturu.
Přečti si ho. Pokud vypadá dobře, napiš:

```
Vypadá to dobře, implementuj krok 1.
```

### 5b. Pokračuj postupně

Po dokončení kroku 1:

```
Výborně. Teď implementuj krok 2 z TECHNICAL_SPEC.md — Google Trends collector.
Přečti si API reference v sekci 4.1 specifikace.
```

Po dokončení:

```
Implementuj krok 3 — Instagram collector. API reference je v sekci 4.3.
```

A tak dále přes všech 7 kroků.

### 5c. Testuj průběžně

Po každém kroku:

```
Spusť testy pro modul, který jsi právě napsal.
```

Nebo:

```
Udělej rychlý smoke test — zavolej SerpAPI s query "dolomity" pro CZ
a ukaž mi raw odpověď.
```

---

## Krok 6: První report

Až jsou hotové všechny moduly:

```
Spusť kompletní pipeline pro CZ trh a aktuální týden.
python -m src.main --market cz
```

Výstup najdeš v `reports/` složce.

---

## Tipy pro práci s Claude Code

### Liší se od Cursoru takto:
- **Žádné vizuální IDE** — všechno je text v terminálu
- **Claude vidí celý projekt** — nepotřebuješ ručně otevírat soubory
- **Claude může spouštět příkazy** — testy, skripty, git
- **Plan Mode je tvůj nejlepší přítel** — vždy nejdřív `/plan`, pak implementuj

### Užitečné příkazy:
```
/plan          — Navrhni plán, nic neměň
/cost          — Kolik tokenů jsem spotřeboval
/clear         — Začni novou konverzaci (zachová soubory)
/help          — Nápověda
```

### Kdy commitovat:
Po každém úspěšně dokončeném kroku řekni Claudovi:

```
Commitni aktuální stav s descriptivním commit message.
```

Claude Code umí přímo `git add` + `git commit`.

### Když se něco pokazí:
```
Vrať poslední změnu a zkus jiný přístup.
```

Claude Code má checkpointy a může reverzovat. Ale Git commit je vždy
nejspolehlivější záloha.

### Kontext se ztrácí?
V dlouhé session může Claude Code "zapomenout" kontext. Řešení:

```
Přečti CLAUDE.md a připomeň si, na čem pracujeme.
Teď pokračuj s implementací kroku 5.
```

---

## Odhadovaný čas

| Krok | Čas s Claude Code |
|------|--------------------|
| 1. Kostra projektu | 30 min |
| 2. Google Trends collector | 1–2 hod |
| 3. Instagram collector | 1–2 hod |
| 4. Content gap + Google Search | 2–3 hod |
| 5. Trend scoring | 1–2 hod |
| 6. Claude analýza | 1–2 hod |
| 7. Report generátor + CLI | 2–3 hod |
| **Celkem** | **~2–3 dny** |

Toto je odhad pro člověka, který Claude Code používá poprvé.
Se zkušenostmi se čas zkrátí na ~1 den.

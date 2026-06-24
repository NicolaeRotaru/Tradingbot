# 06 — Piani & Roadmap

## Backlog esperimenti / miglioramenti (vivo)
Priorità per impatto su **profitto · efficienza · robustezza**. Aggiornalo dopo ogni review.

1. **Anti-overfitting** ✅🟢 FATTO 2026-06-24 — gate OOS obbligatorio: `Bot-Vault/01-Strategia/GATE-OOS.md`.
2. **Sicurezza segreti** 🟡 PRONTA — spostare credenziali deboli dai config (`config-ensemble.json:69`
   password "solbot123", `config.json:76-77` jwt/ws) a `.env`/`FREQTRADE__...`. In attesa del via per il branch.
3. **Stop lato exchange + whitelist prelievi** 🔴 ACCODATA (AZIONI-IN-ATTESA #1) — prereq. del live, firma Nicola.
4. **Test & CI** 🟡 — aggiungere `tests/` e una CI minima (smoke su strategie, diario, news) + gate OOS in CI.
5. **Parità paper↔live** 🔴(prereq. live) — test che confronta comportamento paper vs backtest. (qa-test)
6. **Costi backtest realistici** 🟠 — modellare fee maker/taker reali Kraken (oggi 0,10%/lato unico).
7. **Monitoring/alert** 🟡 — Telegram di sola lettura + healthcheck Docker + kill-switch documentato.
8. **Diversificazione** — solo DOPO che il gate OOS è superato oltre SOL (no overfitting multi-asset forzato).

## Dove nascono i piani
Dai briefing (`90-Memoria-AI/Briefing/`), dalle review (`cervello/ritmo.md`) e dagli audit
(`consegne/audit/`). La prima missione: eseguire `radiografia-bot.js` e prioritizzare i fix.

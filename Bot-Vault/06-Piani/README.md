# 06 — Piani & Roadmap

## Backlog esperimenti / miglioramenti (vivo)
Priorità per impatto su **profitto · efficienza · robustezza**. Aggiornalo dopo ogni review.

1. **Sicurezza segreti** 🟡 — spostare credenziali deboli dai config (`config-ensemble.json` password,
   `config.json` jwt/ws_token) a `.env`/variabili `FREQTRADE__...`. (Vedi security.)
2. **Test & CI** 🟡 — aggiungere `tests/` e una CI minima (smoke su strategie, diario, news).
3. **Anti-overfitting** 🟢 — gate OOS obbligatorio prima di promuovere qualsiasi strategia/modello.
4. **Monitoring/alert** 🟡 — abilitare notifiche (Telegram di sola lettura) + kill-switch documentato.
5. **stoploss_on_exchange** — valutare per il live (protezione se il bot cade).
6. **Diversificazione** — ridurre la concentrazione su SOL (con cautela, no overfitting multi-asset).

## Dove nascono i piani
Dai briefing (`90-Memoria-AI/Briefing/`), dalle review (`cervello/ritmo.md`) e dagli audit
(`consegne/audit/`). La prima missione: eseguire `radiografia-bot.js` e prioritizzare i fix.

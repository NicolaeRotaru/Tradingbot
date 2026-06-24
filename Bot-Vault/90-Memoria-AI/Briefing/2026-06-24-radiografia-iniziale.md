# 🩻 Briefing — Radiografia esplorativa del bot (PASSO 0)

**Data:** 2026-06-24 · **Autore:** CIO (capo desk) · **Tipo:** ricognizione iniziale (sola lettura,
nessuna modifica al codice del bot). Serve a tarare la squadra sui punti deboli reali prima di
proporre i fix con `radiografia-bot.js`.

## Cos'è il bot (com'è fatto davvero)
- **Framework:** Freqtrade in Docker (`restart: unless-stopped` → 24/7).
- **Exchange:** Kraken — spot (stake EUR, long-only, no leva) e Kraken Futures (ensemble, SOL/USD:USD, leva 1x).
- **Modalità:** **PAPER / dry-run** (wallet simulato 50 EUR spot / 500 USD futures). Live disabilitato.
- **Strategie** (`user_data/strategies/`): StarterStrategy (baseline 1h), StarterStrategyLS,
  TrendFollowStrategy, SolLongShortStrategy, e la principale **EnsembleRegimeStrategy** (15m,
  commutazione di regime: trend-long / mean-reversion; short di trend disattivato di default).
- **Motore di ricerca/backtest proprio:** `research/` (engine, indicators, strategies, ml_meta,
  walk-forward OOS) con risultati reali in `results/research/summary.json`.
- **Rischio:** stoploss + custom_stoploss (Chandelier per trend, −2% per MR) + `protections`
  (MaxDrawdown 25%, StoplossGuard, CooldownPeriod).

## Numeri reali (fonte: `results/research/summary.json`, SOL, Trend-long)
| | total | CAGR | Calmar | Sharpe | max DD | win-rate | PF |
|---|---|---|---|---|---|---|---|
| In-sample | +71% | 40% | **1,97** | 1,44 | −20% | 49,5% | 1,09 |
| **Out-of-sample** | **+11,4%** | 4,5% | **0,19** | 0,32 | −23,6% | 50,5% | 1,02 |
Il **degrado IS→OOS** è il dato più importante: l'edge è fragile fuori campione.

## 🔧 I punti deboli prioritari (da verificare e attaccare)
1. 🔒 **Segreti deboli nei config committati.** `user_data/config-ensemble.json` ha
   `api_server.password = "solbot123"` in chiaro; `user_data/config.json` ha
   `jwt_secret_key`/`ws_token`/`password` con placeholder "CAMBIAMI". → Spostare in `.env`/variabili
   `FREQTRADE__API_SERVER__...` (il `.env.example` lo prevede già). **Senior: security.** (🟡)
2. 🧪 **Nessun test, nessuna CI.** Niente `tests/`, niente `.github/workflows/` (prima di TradeDesk OS).
   Zero rete di sicurezza contro le regressioni e nessuna parità paper↔live verificata. **qa-test.** (🟡)
3. 📉 **Overfitting / mancata generalizzazione.** IS Calmar 1,97 vs OOS 0,19; la strategia **non
   generalizza** su BTC/ETH (vedi `docs/validazione-1h-multiasset.md`). → Gate OOS obbligatorio.
   **quant-strategist + backtest-engineer.** (🟢 disciplina)
4. 🛡️ **`stoploss_on_exchange = false`.** Se il bot/VPS cade, nessuno stop protettivo lato exchange.
   Rischio di coda per il live. **risk-manager + exchange-dev.** (valutare per il live)
5. 📡 **Nessun monitoraggio/alert.** Telegram disabilitato in entrambi i config; nessun alert né
   kill-switch esterno documentato. **devops-sre + builder-automazioni.** (🟡)
6. 🎯 **Concentrazione su singolo asset (SOL)** con DD ~24%, e l'ensemble usa futures/margine.
   Rischio di asset singolo. **portfolio-manager.** (con cautela, no overfitting multi-asset)
7. 📒 **Nessun giornale/metriche indipendenti** dal DB Freqtrade, né ingestion news.
   → Risolto in parte da TradeDesk OS: `cervello/diario.py` + `cervello/news.py`. **performance-analytics + news-intelligence.**

## Mosse proposte (prima missione) — da approvare
1. **Eseguire `radiografia-bot.js`** sul codice reale per verificare ogni problema con prova. (🟢 — la eseguo)
2. **Spostare i segreti dei config in `.env`** (security, in branch). (🟡 — la faccio e avviso)
3. **Abilitare alert di sola lettura + documentare il kill-switch** (builder-automazioni/devops-sre, branch). (🟡)
4. **Gate anti-overfitting OOS** come regola prima di promuovere qualsiasi strategia/modello. (🟢)

> Le mosse 🟢 le esegue il desk; quelle che toccano capitale reale/chiavi reali si accodano in
> `AZIONI-IN-ATTESA.md` e partono solo con la firma di Nicola.

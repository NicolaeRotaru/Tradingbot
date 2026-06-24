# 📊 STATO — cruscotto di TradeDesk OS

> Aggiornato dal desk (performance-analytics) a ogni giro/review. Solo numeri reali.

## Stato del bot
- **Modalità:** PAPER (dry-run). Live disabilitato. Exchange: Kraken (spot + futures).
- **Strategia principale:** `EnsembleRegimeStrategy` (15m, SOL/USD:USD, leva 1x).
- **Avvio org:** 2026-06-24 — creato TradeDesk OS (20 senior + memoria + motore).

## Numeri (placeholder — da popolare con dati reali del diario)
- **PnL periodo:** n/d (il diario PAPER è vuoto: nessun trade ancora registrato).
- **Posizioni aperte:** n/d.
- **Max drawdown:** n/d.
- **Sharpe / Sortino:** n/d.
> Esegui `python cervello/diario.py metriche` per popolare. I trade PAPER vanno registrati col diario.

## Riferimento storico (backtest reale, NON performance live) — `results/research/summary.json`
- SOL Trend-long OOS: total +11,4% · CAGR 4,5% · Calmar 0,19 · Sharpe 0,32 · DD −23,6% · win-rate 50,5%.
- SOL Trend-long In-sample: Calmar 1,97 (degrado IS→OOS = promemoria anti-overfitting n.1).

## Ultime mosse
- 2026-06-24 — Creata l'organizzazione TradeDesk OS. Radiografia esplorativa del bot in `Briefing/`.
  Prossima missione proposta: `radiografia-bot.js` + 3 mosse a maggior impatto.

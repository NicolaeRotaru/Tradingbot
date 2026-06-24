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
- **Walk-forward OOS (il numero onesto):** SOL **+42%** (Sharpe 0,49 · PF 1,03) · BTC **−3,7%** (PF 0,997) · ETH **−11%** (PF 0,995).
- **Robustezza (deflated_sharpe, n_trials=400):** SOL 0,0028 · BTC 3,4e-6 · ETH 0,00044 → edge fragile, solo SOL.
- SOL Trend-long "fixed" OOS: total +11,4% · Calmar 0,19 vs In-sample Calmar 1,97 (degrado = promemoria anti-overfitting n.1).

## Esito radiografia 2026-06-24 (`consegne/audit/2026-06-24-radiografia.md`)
- 🔴 3 bloccanti **solo per il LIVE** (stop lato exchange off, whitelist prelievi assente, no parità paper↔live).
- 🟠 4 seri (overfit solo-SOL, segreti deboli nei config, no test/CI, costi backtest semplificati).
- 🟡 4 minori. ❌ Refutato 1 falso positivo (look-ahead Bollinger). In **paper nessun rischio catastrofico**.

## Ultime mosse
- 2026-06-24 — Creata l'org TradeDesk OS + radiografia eseguita e verificata.
- 2026-06-24 — 🟢 Eseguito **gate anti-overfitting OOS** (`Bot-Vault/01-Strategia/GATE-OOS.md`).
- 2026-06-24 — 🔴 Accodata azione "stop lato exchange + whitelist prelievi" (firma Nicola, prereq. live).

---
name: backtest
description: Esegue un backtest ONESTO della strategia su dati storici reali di SOL (rendimento, max drawdown, Calmar, win rate; in-sample E fuori campione). Usala quando l'utente chiede "fai un backtest", "quanto avrebbe reso", "testa la strategia", "confronta le strategie", "15m vs 1h".
---

# Skill: backtest onesto

Questo ambiente HA i dati e le librerie per girare i backtest standalone: il `.venv`
contiene numpy/pandas/talib/matplotlib, e i dati reali sono nei CSV versionati su GitHub.
Gli exchange NON sono raggiungibili: per dati NUOVI serve `scripts/download_1h_data.py`
eseguito sul PC dell'utente (poi `git push`).

## Dati disponibili nel repo
- `user_data/data_sources/SOL_USDT-1h.csv` (2021→2026); anche `BTC_USDT-1h.csv`, `ETH_USDT-1h.csv`
- `user_data/data_sources/SOL_USDT-15m.csv` (se l'utente l'ha già pushato)
- `user_data/data_sources/solana_sol_usd_1d.csv`

## Script pronti (eseguili con `.venv/bin/python`)
- `scripts/backtest_sol_robust.py` — trend Chandelier, sweep leva→DD, **dimostrazione del lookahead**
- `scripts/backtest_sol_longshort.py` — solo-long vs long+short, walk-forward OOS (split 2024-01-01)
- `scripts/backtest_1h_multiasset.py` — SOL/BTC/ETH (la strategia NON generalizza: ottima su SOL)
- `research/run_research.py` + `research/optimize.py` — motore **ensemble** walk-forward OOS
  (l'ML meta-labeling in `research/ml_meta.py` richiede `lightgbm`: gira sul **PC dell'utente**)

## Regole d'oro (ONESTÀ — non negoziabili)
- Riporta SEMPRE: rendimento, maxDD, **Calmar**, win rate, e il numero **FUORI CAMPIONE (OOS)**, non solo in-sample.
- Niente lookahead: segnale a chiusura, posizione dalla barra dopo (già nel codice).
- Diffida dei numeri enormi in-sample: spesso sono overfitting/multiple-testing. La bussola è il **Calmar OOS**.
- Costi inclusi (fee+slippage). **Win rate alto ≠ profitto** (il mean-reversion ingenuo vince spesso ma perde soldi).

## Output all'utente
Tabella chiara + una frase di lettura onesta. Se chiede **15m vs 1h**: confronta e spiega che
per il **trend-following** 15m di solito **peggiora** (più rumore + più commissioni), mentre per
l'**ensemble mean-reversion** 15m può avere senso. Mostra i numeri, non opinioni.

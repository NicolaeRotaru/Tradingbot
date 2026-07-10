# 03 — Dati & Segnali

## Fonti dati
- **OHLCV storici**: `user_data/data_sources/*.csv` (SOL/BTC/ETH 1h, SOL 15m, SOL 1d).
- **Download/aggiornamento**: `scripts/download_1h_data.py`, `scripts/fetch_solana_data.py`.
- **News & sentiment** (orario): `cervello/news.py` → `Bot-Vault/90-Memoria-AI/news/`.

## Segnali/indicatori in uso (da `research/indicators.py` e dalle strategie)
- Tendenza: EMA50/EMA200/EMA400, ADX, Efficiency Ratio (regime).
- Momentum/mean-reversion: RSI, Bollinger Bands (20,2).
- Volatilità/stop: ATR, Chandelier trailing stop.
- Alt-data potenziali: Fear&Greed, funding/OI, flussi on-chain (da integrare, vedi data-engineer).

## Qualità dati (presidiata da data-engineer)
Controllare: gap, duplicati, **look-ahead bias**, allineamento dei timeframe. Garbage in = garbage out.

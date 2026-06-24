# 02 — Mercati & Asset

## Exchange
- **Kraken** spot (stake EUR, long-only, no leva) — config `user_data/config.json`.
- **Kraken Futures** (krakenfutures) per `EnsembleRegimeStrategy` — config `user_data/config-ensemble.json`,
  margine isolato, **leva 1x** per evitare liquidazioni.

## Coppie
- Spot: `BTC/EUR`, `ETH/EUR`, `SOL/EUR` (whitelist statica).
- Futures: `SOL/USD:USD`.

## Struttura di mercato (note)
- Crypto è **24/7**: il ritmo del desk è orario/giornaliero, non legato alle borse.
- Concentrazione attuale su **SOL**: opportunità ma anche rischio di asset singolo (DD ~24%).
- Dati storici disponibili in `user_data/data_sources/` (SOL/BTC/ETH 1h, SOL 15m, SOL 1d).

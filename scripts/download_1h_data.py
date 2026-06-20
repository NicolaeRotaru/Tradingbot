#!/usr/bin/env python3
"""
PONTE PER I DATI 1h — da eseguire SUL TUO COMPUTER (non nell'ambiente cloud).

Perche': l'ambiente cloud dell'assistente raggiunge solo PyPI e GitHub, NON gli
exchange. Questo script gira sul tuo PC (dove gli exchange funzionano), scarica
lo storico ORARIO (1h) e lo salva in CSV dentro user_data/data_sources/. Tu poi
fai `git push` e l'assistente, che raggiunge GitHub, puo' usare quei dati per il
backtest a 1h.

Uso:
    pip install ccxt pandas
    python scripts/download_1h_data.py                 # SOL, BTC, ETH dal 2021
    python scripts/download_1h_data.py --symbols SOL/USDT --since 2022-01-01

Non servono chiavi API: i dati OHLCV pubblici sono accessibili senza login.
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

try:
    import ccxt
except ImportError:  # pragma: no cover
    raise SystemExit("Manca ccxt. Installa con:  pip install ccxt pandas")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "user_data" / "data_sources"


def fetch_ohlcv(exchange, symbol: str, timeframe: str, since_ms: int) -> pd.DataFrame:
    limit = 1000
    all_rows: list[list] = []
    ms_per_candle = exchange.parse_timeframe(timeframe) * 1000
    cursor = since_ms
    now = exchange.milliseconds()
    while cursor < now:
        batch = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=cursor, limit=limit)
        if not batch:
            break
        all_rows += batch
        cursor = batch[-1][0] + ms_per_candle
        print(f"  {symbol} {timeframe}: {len(all_rows)} candele "
              f"(fino a {datetime.fromtimestamp(batch[-1][0]/1000, tz=timezone.utc).date()})",
              end="\r")
        time.sleep(exchange.rateLimit / 1000)
    print()
    df = pd.DataFrame(all_rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df = df.drop_duplicates("ts").sort_values("ts")
    df["date"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    return df[["date", "open", "high", "low", "close", "volume"]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exchange", default="binance")
    ap.add_argument("--symbols", nargs="+", default=["SOL/USDT", "BTC/USDT", "ETH/USDT"])
    ap.add_argument("--timeframe", default="1h")
    ap.add_argument("--since", default="2021-01-01")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    exchange = getattr(ccxt, args.exchange)({"enableRateLimit": True})
    since_ms = int(datetime.strptime(args.since, "%Y-%m-%d")
                   .replace(tzinfo=timezone.utc).timestamp() * 1000)

    for sym in args.symbols:
        print(f"Scarico {sym} {args.timeframe} da {args.since} su {args.exchange}...")
        df = fetch_ohlcv(exchange, sym, args.timeframe, since_ms)
        name = sym.replace("/", "_") + f"-{args.timeframe}.csv"
        path = OUT / name
        df.to_csv(path, index=False)
        print(f"  -> salvato {path.relative_to(ROOT)}  ({len(df)} candele, "
              f"{df['date'].min().date()} -> {df['date'].max().date()})")

    print("\nFatto. Ora committa e pusha questi CSV:")
    print("  git add user_data/data_sources/*-1h.csv")
    print('  git commit -m "Aggiungi storico 1h per il backtest"')
    print("  git push")
    print("Poi chiedi all'assistente di eseguire il backtest a 1h su questi dati.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

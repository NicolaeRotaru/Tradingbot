#!/usr/bin/env python3
"""
Scarica lo storico GIORNALIERO di Solana (SOL/USD) da un dataset pubblico su
GitHub (l'unica fonte raggiungibile da questo ambiente: il proxy blocca gli
exchange) e lo salva in due formati:

  1) user_data/data/solana_csv/SOL_USDT-1d.feather  -> formato Freqtrade
  2) user_data/data_sources/solana_sol_usd_1d.csv    -> copia leggibile/versionata

Periodo: 2021-01-01 -> 2024-09-29  (~1368 giorni).
Fonte:   https://github.com/NI3singh/Solana-Data-Analysis
"""
from __future__ import annotations

import io
import sys
import urllib.request
from pathlib import Path

import pandas as pd

URL = (
    "https://raw.githubusercontent.com/NI3singh/Solana-Data-Analysis/"
    "main/Solana_Price_data.csv"
)

ROOT = Path(__file__).resolve().parents[1]
# Salviamo nella cartella "binance" cosi' il file e' direttamente utilizzabile
# dal motore Freqtrade con user_data/config-backtest-binance.json --timeframe 1d
# (il dataset e' SOL/USDT derivato da Binance). La cartella data/ e' gitignored:
# si rigenera lanciando questo script.
FEATHER_DIR = ROOT / "user_data" / "data" / "binance"
CSV_DIR = ROOT / "user_data" / "data_sources"
FEATHER_PATH = FEATHER_DIR / "SOL_USDT-1d.feather"
CSV_PATH = CSV_DIR / "solana_sol_usd_1d.csv"


def download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main() -> int:
    print(f"Scarico: {URL}")
    raw = download(URL)
    df = pd.read_csv(io.BytesIO(raw))

    # Normalizza le colonne allo schema Freqtrade.
    df = df.rename(
        columns={
            "time": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df = df[["date", "open", "high", "low", "close", "volume"]]
    df = df.sort_values("date").drop_duplicates("date").reset_index(drop=True)

    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = df[c].astype(float)

    # Controlli di qualita' basilari.
    assert (df["high"] >= df["low"]).all(), "high < low: dati corrotti"
    assert df["close"].gt(0).all(), "prezzi non positivi"

    FEATHER_DIR.mkdir(parents=True, exist_ok=True)
    CSV_DIR.mkdir(parents=True, exist_ok=True)

    df.reset_index(drop=True).to_feather(FEATHER_PATH)
    df.to_csv(CSV_PATH, index=False)

    # Verifica: rileggi il feather (senza rete) per confermare il formato.
    check = pd.read_feather(FEATHER_PATH)

    print("OK.")
    print(f"  righe                : {len(df)}")
    print(f"  periodo              : {df['date'].min().date()} -> {df['date'].max().date()}")
    print(f"  prezzo iniziale (cl) : {df['close'].iloc[0]:.3f} USD")
    print(f"  prezzo finale  (cl)  : {df['close'].iloc[-1]:.3f} USD")
    print(f"  feather              : {FEATHER_PATH.relative_to(ROOT)}  ({len(check)} righe ri-lette)")
    print(f"  csv                  : {CSV_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

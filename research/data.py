#!/usr/bin/env python3
"""Caricamento dati 1h reali + calcolo indicatori (con cache su disco)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from indicators import add_indicators

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "user_data" / "data_sources"

ASSETS = {
    "SOL": DATA / "SOL_USDT-1h.csv",
    "BTC": DATA / "BTC_USDT-1h.csv",
    "ETH": DATA / "ETH_USDT-1h.csv",
}


def load(asset: str) -> pd.DataFrame:
    df = pd.read_csv(ASSETS[asset], parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    return add_indicators(df)

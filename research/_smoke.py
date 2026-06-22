#!/usr/bin/env python3
"""Smoke test: valida che il motore giri e produca numeri sensati su SOL."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
from data import load
from strategies import variant_params, generate
from engine import RiskConfig, simulate, metrics, buy_hold

df = load("SOL")
print("SOL barre:", len(df), "indicatori NaN dopo warmup:",
      int(df.iloc[400:][["ema400", "adx", "atr", "rvol", "bb_low"]].isna().sum().sum()))

rc = RiskConfig()
SPLIT = pd.Timestamp("2024-01-01", tz="UTC")

print(f"\n{'variante':<20}{'rend':>10}{'CAGR':>8}{'maxDD':>8}{'Shrp':>7}{'Calmar':>8}{'trade':>7}{'espos':>7}")
for name in ["trend_long_only", "trend_ls", "mr_only", "ensemble_long", "ensemble_full"]:
    p = variant_params(name)
    pos, mode, reg = generate(df, p)
    res = simulate(df, pos, rc)
    m = metrics(res, df)
    print(f"{name:<20}{m['total']*100:>9.0f}%{m['cagr']*100:>7.0f}%{m['dd']*100:>7.0f}%"
          f"{m['sharpe']:>7.2f}{m['calmar']:>8.2f}{m['trades']:>7}{m['expo']*100:>6.0f}%")

bh = buy_hold(df)
mbh = metrics(bh, df)
print(f"{'buy_hold':<20}{mbh['total']*100:>9.0f}%{mbh['cagr']*100:>7.0f}%{mbh['dd']*100:>7.0f}%"
      f"{mbh['sharpe']:>7.2f}{mbh['calmar']:>8.2f}")

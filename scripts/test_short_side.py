#!/usr/bin/env python3
"""
TEST SHORT-SIDE — lo specchio del V-bounce: shorta i "rip" (picchi) nei downtrend.

Il V-bounce long compra i dip in regime non-bear. Lo specchio:
  SHORT quando il prezzo ha fatto un POP (RSI alto / sopra banda alta) in regime
  NON-BULL, e ora sta GIRANDO GIÙ (candela rossa + RSI in calo).

Triple-barrier simmetrica per lo short:
  - entry = open[i+1]
  - TP (profitto short) = entry × (1 − k×ATR)   → il prezzo SCENDE
  - SL (perdita short)   = entry + k×ATR         → il prezzo SALE (stop sopra)
  - label=1 se tocca prima il TP (scende) che lo SL (sale); SL controllato per primo.

Confronta poi LONG vs SHORT vs LONG+SHORT combinati su IS/OOS.

Usage: python3 scripts/test_short_side.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "scripts"))

import backtest_vbounce as vb

DATA = ROOT / "user_data" / "data_sources" / "SOL_USDT-15m.csv"
SPLIT = pd.Timestamp("2024-01-01", tz="UTC")

TP_ATR  = 2.0
SL_ATR  = 2.0
HORIZON = 96
FEE_RT  = 0.0020
WARMUP  = 700

POP_RSI       = 60.0   # specchio di DIP_RSI=40
TREND_PUSH_RSI = 50.0


def add_short_signal(d: pd.DataFrame, min_rr: float = 1.0) -> None:
    """Specchio esatto di add_entry_v2 per lo SHORT."""
    # turning_down = candela rossa + RSI in calo (specchio di turning_up)
    turning_down = (d["close"] < d["open"]) & (d["rsi"] < d["rsi"].shift(1)) & (d["volume"] > 0)
    # just_had_pop = RSI era alto OR high sopra banda alta (specchio di just_had_dip)
    just_had_pop = (d["rsi"].shift(1) > POP_RSI) | (d["high"].shift(1) > d["bb_up"])
    # good_rr per lo short: spazio fino alla banda BASSA (specchio di bb_up per long)
    good_rr = (d["close"] - d["bb_low"]) >= min_rr * vb.CHANDELIER * d["atr"]
    not_knife = ~d["knife"]
    # htf_down: specchio di htf_ok (trend HTF al ribasso)
    htf_down = ((d["close_4h"] < d["ema200_4h"])
                | ((d["rsi_4h"] < (100 - vb.HTF_RSI_FLOOR)) & (d["ema50_up_4h"] < 0.5)))

    # dip-bounce short: pop in regime non-bull, turning down
    pop = ((d["regime"] != 1) & just_had_pop & good_rr & htf_down
           & not_knife & turning_down)
    # trend-pullback short: in regime bear, rimbalzo verso bb_mid che gira giù
    trend = ((d["regime"] == -1) & (d["close"] > d["bb_mid"])
             & (d["rsi"] > TREND_PUSH_RSI) & (d["rsi"] < (100 - vb.RSI_LO_EXIT))
             & good_rr & not_knife & turning_down)
    d["enter_short"] = (pop | trend).astype(int)


def triple_barrier_long(d, idx):
    """Label long: TP=+k×ATR sopra, SL=-k×ATR sotto."""
    o = d["open"].to_numpy(); hi = d["high"].to_numpy()
    lo = d["low"].to_numpy(); c = d["close"].to_numpy(); atr = d["atr"].to_numpy()
    n = len(d)
    rows = []
    for i in idx:
        if not np.isfinite(atr[i]) or atr[i] <= 0:
            continue
        entry = o[i + 1]
        tp = entry + TP_ATR * atr[i]
        sl = entry - SL_ATR * atr[i]
        end = min(i + 1 + HORIZON, n)
        ret = None
        for j in range(i + 1, end):
            if lo[j] <= sl:
                ret = (sl / entry - 1.0) - FEE_RT; break
            if hi[j] >= tp:
                ret = (tp / entry - 1.0) - FEE_RT; break
        if ret is None:
            ret = (c[min(end, n) - 1] / entry - 1.0) - FEE_RT
        rows.append((d["date"].iloc[i], ret))
    return rows


def triple_barrier_short(d, idx):
    """Label short: profitto se SCENDE (TP sotto), perdita se SALE (SL sopra)."""
    o = d["open"].to_numpy(); hi = d["high"].to_numpy()
    lo = d["low"].to_numpy(); c = d["close"].to_numpy(); atr = d["atr"].to_numpy()
    n = len(d)
    rows = []
    for i in idx:
        if not np.isfinite(atr[i]) or atr[i] <= 0:
            continue
        entry = o[i + 1]
        tp = entry - TP_ATR * atr[i]    # profitto short = prezzo scende
        sl = entry + SL_ATR * atr[i]    # perdita short  = prezzo sale (stop sopra)
        end = min(i + 1 + HORIZON, n)
        ret = None
        for j in range(i + 1, end):
            if hi[j] >= sl:             # stop (sale) per primo = pessimista
                ret = (entry / sl - 1.0) - FEE_RT; break
            if lo[j] <= tp:             # take-profit (scende)
                ret = (entry / tp - 1.0) - FEE_RT; break
        if ret is None:
            ret = (entry / c[min(end, n) - 1] - 1.0) - FEE_RT
        rows.append((d["date"].iloc[i], ret))
    return rows


def report(rows, name):
    if len(rows) == 0:
        print(f"  {name:<32}  NESSUN TRADE")
        return None
    df = pd.DataFrame(rows, columns=["date", "ret"])
    r = df["ret"].to_numpy()
    w = r[r > 0]; l = r[r <= 0]
    wr = len(w) / len(r) * 100
    aw = w.mean() * 100 if len(w) else 0.0
    al = l.mean() * 100 if len(l) else 0.0
    pf = w.sum() / abs(l.sum()) if len(l) and l.sum() != 0 else float("inf")
    ex = r.mean() * 100
    gate = "✅" if ex > 0 else "❌"
    print(f"  {gate} {name:<32}  n={len(r):>4}  WR={wr:>4.1f}%  "
          f"aw={aw:>+6.2f}%  al={al:>+6.2f}%  PF={pf:.2f}  exp={ex:>+6.3f}%")
    return df


def main():
    df = pd.read_csv(DATA, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    d = vb.build(df, htf_rule="1h")
    add_short_signal(d, min_rr=1.0)

    enter_long  = d["enter_v2"].to_numpy()
    enter_short = d["enter_short"].to_numpy()
    dates = pd.to_datetime(d["date"])
    n = len(d)

    long_idx  = [i for i in range(WARMUP, n - 1) if enter_long[i] == 1]
    short_idx = [i for i in range(WARMUP, n - 1) if enter_short[i] == 1]

    is_mask  = dates < SPLIT
    long_is   = [i for i in long_idx  if is_mask.iloc[i]]
    long_oos  = [i for i in long_idx  if not is_mask.iloc[i]]
    short_is  = [i for i in short_idx if is_mask.iloc[i]]
    short_oos = [i for i in short_idx if not is_mask.iloc[i]]

    print("#" * 78)
    print("# TEST SHORT-SIDE — specchio del V-bounce su SOL 15m (TP=SL=2×ATR)")
    print(f"# Segnali LONG: {len(long_idx)}   Segnali SHORT: {len(short_idx)}")
    print("#" * 78)

    print("\n=== LONG (V-bounce v2, riferimento) ===")
    report(triple_barrier_long(d, long_is),  "LONG  in-sample 2021-23")
    report(triple_barrier_long(d, long_oos), "LONG  out-of-sample 2024+")

    print("\n=== SHORT (specchio) ===")
    short_is_rows  = triple_barrier_short(d, short_is)
    short_oos_rows = triple_barrier_short(d, short_oos)
    report(short_is_rows,  "SHORT  in-sample 2021-23")
    report(short_oos_rows, "SHORT  out-of-sample 2024+")

    print("\n=== SHORT per anno (OOS robustness) ===")
    short_all = triple_barrier_short(d, short_idx)
    sdf = pd.DataFrame(short_all, columns=["date", "ret"])
    sdf["year"] = pd.to_datetime(sdf["date"]).dt.year
    for yr, g in sdf.groupby("year"):
        r = g["ret"].to_numpy()
        wr = (r > 0).mean() * 100
        gate = "✅" if r.mean() > 0 else "❌"
        print(f"  {gate} {yr}: n={len(g):>4}  WR={wr:>4.1f}%  exp={r.mean()*100:>+6.3f}%")

    print("\n=== SHORT solo in regime BEAR (dove dovrebbe brillare) ===")
    reg = d["regime"].to_numpy()
    short_bear = [i for i in short_idx if reg[i] == -1]
    short_bear_is  = [i for i in short_bear if is_mask.iloc[i]]
    short_bear_oos = [i for i in short_bear if not is_mask.iloc[i]]
    report(triple_barrier_short(d, short_bear_is),  "SHORT bear  in-sample")
    report(triple_barrier_short(d, short_bear_oos), "SHORT bear  out-of-sample")

    print("\n" + "#" * 78)
    print("# Lettura: lo SHORT ha edge se exp>0 e WR>~56% (breakeven con fee, R:R 1:1),")
    print("# robusto IS E OOS. Se è negativo come il long → il problema è l'asset/timeframe,")
    print("# non la direzione. Se è positivo → vale la pena aggiungerlo (con cautela).")
    print("#" * 78)


if __name__ == "__main__":
    main()

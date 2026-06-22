#!/usr/bin/env python3
"""
ROBUSTEZZA del vincitore: trend-following su 4h. È edge vero o parametri fortunati?

Tre test:
  A) GRIGLIA PARAMETRI — se solo 20/50 funziona è overfit; se un INTORNO funziona è reale.
  B) SENSIBILITÀ FEE — sopravvive a 0.06 / 0.10 / 0.15 %/lato?
  C) LONG/SHORT — shortare i downtrend (2022) aiuta o no?

Stesso motore long/flat di test_10_strategies, split fisso 2024-01-01.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research"))
from indicators import ema  # noqa: E402

DATA15 = ROOT / "user_data" / "data_sources" / "SOL_USDT-15m.csv"
SPLIT = pd.Timestamp("2024-01-01", tz="UTC")
WARMUP = 300
BARS_PER_YEAR_4H = 6 * 365


def resample(d, rule="4h"):
    s = d.set_index("date")
    return pd.DataFrame({
        "open": s["open"].resample(rule).first(),
        "high": s["high"].resample(rule).max(),
        "low": s["low"].resample(rule).min(),
        "close": s["close"].resample(rule).last(),
        "volume": s["volume"].resample(rule).sum(),
    }).dropna().reset_index()


def run(close, signal, fee_side, allow_short=False):
    """signal = pos desiderata a fine t (1=long, 0=flat, -1=short se allow_short)."""
    bar_ret = np.zeros(len(close))
    bar_ret[1:] = close[1:] / close[:-1] - 1.0
    eff = np.zeros(len(close))
    eff[1:] = signal[:-1]
    if not allow_short:
        eff = np.clip(eff, 0, 1)
    turn = np.zeros(len(close))
    turn[1:] = np.abs(eff[1:] - eff[:-1])
    sr = eff * bar_ret - turn * fee_side
    eq = np.cumprod(1.0 + sr)
    return eq, sr, eff


def met(close, signal, fee_side, bpy, allow_short=False):
    eq, sr, eff = run(close, signal, fee_side, allow_short)
    total = eq[-1] - 1.0
    years = len(eq) / bpy
    cagr = eq[-1] ** (1.0 / years) - 1.0 if eq[-1] > 0 else -1.0
    peak = np.maximum.accumulate(eq)
    maxdd = (eq / peak - 1.0).min()
    sd = sr.std()
    sharpe = sr.mean() / sd * np.sqrt(bpy) if sd > 0 else np.nan
    calmar = cagr / abs(maxdd) if maxdd < 0 else np.nan
    return dict(total=total, cagr=cagr, maxdd=maxdd, sharpe=sharpe, calmar=calmar)


def ema_cross_signal(close, fast, slow):
    ef = ema(pd.Series(close), fast).to_numpy()
    es = ema(pd.Series(close), slow).to_numpy()
    return (ef > es).astype(int)


def main():
    df = pd.read_csv(DATA15, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    d = resample(df, "4h").iloc[WARMUP:].reset_index(drop=True)
    close = d["close"].to_numpy()
    split = int((d["date"] < SPLIT).sum())
    n = len(d)

    def slices(sig, fee=0.0006, allow_short=False):
        full = met(close, sig, fee, BARS_PER_YEAR_4H, allow_short)
        is_  = met(close[:split], sig[:split], fee, BARS_PER_YEAR_4H, allow_short)
        oos  = met(close[split:], sig[split:], fee, BARS_PER_YEAR_4H, allow_short)
        return full, is_, oos

    bh = np.ones(n, dtype=int)
    _, _, bh_oos = slices(bh)
    print("=" * 88)
    print(" ROBUSTEZZA TREND-FOLLOWING 4h — è edge vero o fortuna?")
    print(f" Riferimento Buy&Hold OOS: Sharpe {bh_oos['sharpe']:.2f}  Calmar {bh_oos['calmar']:.2f}")
    print("=" * 88)

    # ---- A) GRIGLIA PARAMETRI ----
    print("\n A) GRIGLIA EMA cross (OOS Sharpe). Se un INTORNO è positivo → robusto.")
    fasts = [10, 15, 20, 25, 30, 40]
    slows = [40, 50, 75, 100, 150, 200]
    hdr_label = "fast/slow"
    print(f"   {hdr_label:>10}" + "".join(f"{s:>7}" for s in slows))
    pos_count, tot_count = 0, 0
    for f in fasts:
        line = f"   {f:>10}"
        for s in slows:
            if f >= s:
                line += f"{'·':>7}"
                continue
            sig = ema_cross_signal(close, f, s)
            _, _, oos = slices(sig)
            sh = oos["sharpe"]
            tot_count += 1
            if sh > bh_oos["sharpe"]:
                pos_count += 1
            line += f"{sh:>7.2f}"
        print(line)
    print(f"   → {pos_count}/{tot_count} combinazioni battono Buy&Hold OOS su Sharpe")

    # ---- B) SENSIBILITÀ FEE (su 20/50 e 30/100) ----
    print("\n B) SENSIBILITÀ FEE (Sharpe OOS / ret OOS):")
    for f, s in [(20, 50), (30, 100)]:
        sig = ema_cross_signal(close, f, s)
        print(f"   EMA {f}/{s}:")
        for fee in (0.0006, 0.0010, 0.0015, 0.0025):
            _, _, oos = slices(sig, fee=fee)
            mark = "✅" if oos["sharpe"] > bh_oos["sharpe"] and oos["total"] > 0 else "❌"
            print(f"     fee {fee*100:.2f}%/lato → Sharpe {oos['sharpe']:+.2f}  "
                  f"ret {oos['total']*100:+.0f}%  Calmar {oos['calmar']:+.2f}  {mark}")

    # ---- C) LONG/SHORT ----
    print("\n C) LONG-only vs LONG/SHORT (EMA 20/50, fee 0.06%/lato):")
    sig01 = ema_cross_signal(close, 20, 50)            # 1/0
    sig_ls = sig01 * 2 - 1                             # 1/-1 (short quando sotto)
    for name, sig, short in [("LONG/flat", sig01, False), ("LONG/SHORT", sig_ls, True)]:
        full, is_, oos = slices(sig, allow_short=short)
        print(f"   {name:<11} full: ret {full['total']*100:+.0f}%  Sharpe {full['sharpe']:.2f}  "
              f"MaxDD {full['maxdd']*100:.0f}% | OOS: Sharpe {oos['sharpe']:+.2f}  "
              f"ret {oos['total']*100:+.0f}%  Calmar {oos['calmar']:+.2f}")

    # ---- D) PER ANNO della config robusta ----
    print("\n D) EMA 30/100 long/flat — Sharpe per anno (robustezza temporale):")
    sig = ema_cross_signal(close, 30, 100)
    d2 = d.copy(); d2["year"] = pd.to_datetime(d2["date"]).dt.year
    for yr in sorted(d2["year"].unique()):
        idx = np.where(d2["year"].to_numpy() == yr)[0]
        if len(idx) < 50:
            continue
        lo, hi = idx[0], idx[-1] + 1
        m = met(close[lo:hi], sig[lo:hi], 0.0006, BARS_PER_YEAR_4H)
        bhm = met(close[lo:hi], np.ones(hi - lo, int), 0.0006, BARS_PER_YEAR_4H)
        mark = "✅" if m["sharpe"] > bhm["sharpe"] else "❌"
        print(f"   {yr}: strat Sharpe {m['sharpe']:+.2f}  ret {m['total']*100:+5.0f}%  | "
              f"B&H Sharpe {bhm['sharpe']:+.2f}  ret {bhm['total']*100:+5.0f}%  {mark}")

    print("\n" + "=" * 88)
    print(" Verdetto robusto SE: la griglia ha molti positivi (non solo 20/50), sopravvive a")
    print(" fee più alte, e batte B&H in più anni. Altrimenti è curve-fitting.")
    print("=" * 88)


if __name__ == "__main__":
    main()

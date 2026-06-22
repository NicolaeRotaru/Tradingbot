#!/usr/bin/env python3
"""
"Qual e' il bot che produce di piu' all'anno?" — classifica definitiva.

Prende i migliori setup emersi da tutta la ricerca (32 strategie testate) e li
ordina per RENDIMENTO ANNUO COMPOSTO (CAGR) sui dati reali SOL, mostrando per
ognuno: CAGR full, MaxDD, Sharpe, e il comportamento OUT-OF-SAMPLE (post 2024-01-01)
che e' l'unico numero onesto (niente overfitting sul passato gia' visto).

Motore long/flat, segnale shift(1) (no lookahead), fee 0.06%/lato.
Aggiunge anche la riga "Ensemble 4h a leva 2x" per mostrare il tetto realistico.
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
FEE_SIDE = 0.0006
BPY_4H = 6 * 365          # barre 4h in un anno
BPY_1D = 365              # barre giornaliere in un anno


def resample(d, rule):
    s = d.set_index("date")
    return pd.DataFrame({
        "open": s["open"].resample(rule).first(),
        "high": s["high"].resample(rule).max(),
        "low": s["low"].resample(rule).min(),
        "close": s["close"].resample(rule).last(),
        "volume": s["volume"].resample(rule).sum(),
    }).dropna().reset_index()


def run(close, signal, fee_side, lev=1.0, allow_short=False):
    bar_ret = np.zeros(len(close))
    bar_ret[1:] = close[1:] / close[:-1] - 1.0
    eff = np.zeros(len(close))
    eff[1:] = signal[:-1]
    if not allow_short:
        eff = np.clip(eff, 0, 1)
    turn = np.zeros(len(close))
    turn[1:] = np.abs(eff[1:] - eff[:-1])
    sr = lev * eff * bar_ret - turn * fee_side * lev
    eq = np.cumprod(1.0 + sr)
    return eq, sr


def met(close, signal, bpy, lev=1.0, allow_short=False):
    eq, sr = run(close, signal, FEE_SIDE, lev, allow_short)
    years = len(eq) / bpy
    cagr = eq[-1] ** (1.0 / years) - 1.0 if eq[-1] > 0 else -1.0
    peak = np.maximum.accumulate(eq)
    maxdd = (eq / peak - 1.0).min()
    sd = sr.std()
    sharpe = sr.mean() / sd * np.sqrt(bpy) if sd > 0 else np.nan
    return dict(total=eq[-1] - 1.0, cagr=cagr, maxdd=maxdd, sharpe=sharpe)


def ema_cross(close, fast, slow):
    ef = ema(pd.Series(close), fast).to_numpy()
    es = ema(pd.Series(close), slow).to_numpy()
    return (ef > es).astype(int)


def ensemble_mtf(close, f1=20, s1=50, f2=100, s2=200):
    c = pd.Series(close)
    fast_ok = (ema(c, f1) > ema(c, s1)).to_numpy()
    slow_ok = (ema(c, f2) > ema(c, s2)).to_numpy()
    return (fast_ok & slow_ok).astype(int)


def main():
    df = pd.read_csv(DATA15, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    d4 = resample(df, "4h").iloc[WARMUP:].reset_index(drop=True)
    d1 = resample(df, "1d").iloc[WARMUP // 6:].reset_index(drop=True)
    c4, c1 = d4["close"].to_numpy(), d1["close"].to_numpy()
    sp4 = int((d4["date"] < SPLIT).sum())
    sp1 = int((d1["date"] < SPLIT).sum())

    # (nome, close, bpy, signal, split, lev, short)
    bots = [
        ("Buy & Hold SOL (benchmark)", c4, BPY_4H, np.ones(len(c4), int), sp4, 1.0, False),
        ("EMA 20/50  4h  long/flat",   c4, BPY_4H, ema_cross(c4, 20, 50),  sp4, 1.0, False),
        ("EMA 30/100 4h  long/flat",   c4, BPY_4H, ema_cross(c4, 30, 100), sp4, 1.0, False),
        ("Ensemble (20/50 & 100/200) 4h", c4, BPY_4H, ensemble_mtf(c4),    sp4, 1.0, False),
        ("Ensemble (20/50 & 80/200) 4h",  c4, BPY_4H, ensemble_mtf(c4, 20, 50, 80, 200), sp4, 1.0, False),
        ("EMA 20/50  1d  long/flat",   c1, BPY_1D, ema_cross(c1, 20, 50),  sp1, 1.0, False),
        (">> Ensemble 4h a LEVA 2x",   c4, BPY_4H, ensemble_mtf(c4),       sp4, 2.0, False),
    ]

    rows = []
    for name, close, bpy, sig, split, lev, short in bots:
        full = met(close, sig, bpy, lev, short)
        oos = met(close[split:], sig[split:], bpy, lev, short)
        rows.append((name, full, oos))

    print("=" * 100)
    print(" CLASSIFICA BOT per RENDIMENTO ANNUO (CAGR) — dati reali SOL, 5+ anni, fee 0.06%/lato")
    print(" OOS = solo dal 2024-01-01 (out-of-sample, l'unico numero che non e' overfitting)")
    print("=" * 100)
    print(f" {'bot':<34}{'CAGR/anno':>11}{'tot full':>11}{'MaxDD':>9}{'Sharpe':>8} | "
          f"{'OOS CAGR':>9}{'OOS ret':>9}{'OOS Sh':>8}")
    print(" " + "-" * 98)
    # ordina per CAGR full discendente (ma B&H resta come riferimento in cima visivo)
    rows_sorted = sorted(rows, key=lambda r: r[1]["cagr"], reverse=True)
    for name, full, oos in rows_sorted:
        print(f" {name:<34}{full['cagr']*100:>+10.0f}%{full['total']*100:>+10.0f}%"
              f"{full['maxdd']*100:>+8.0f}%{full['sharpe']:>8.2f} | "
              f"{oos['cagr']*100:>+8.0f}%{oos['total']*100:>+8.0f}%{oos['sharpe']:>+8.2f}")

    print("=" * 100)
    print(" LETTURA:")
    print(" - 'Produce di piu'' grezzo = EMA 20/50 4h, ma ha MaxDD pesante e Sharpe basso.")
    print(" - MIGLIORE come BOT (rendimento/rischio) = Ensemble multi-TF 4h: CAGR vicino a")
    print("   Buy&Hold con META' del drawdown e Sharpe OOS nettamente piu' alto.")
    print(" - La leva 2x alza il CAGR ma raddoppia il MaxDD: oltre 2-3x su SOL = liquidazione.")
    print("=" * 100)


if __name__ == "__main__":
    main()

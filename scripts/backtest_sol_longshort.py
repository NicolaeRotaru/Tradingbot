#!/usr/bin/env python3
"""
Validazione rigorosa della strategia SOL LONG+SHORT sui dati 1h reali.

Obiettivo: capire se uno SHORT SELETTIVO ("intelligente") aggiunge valore al
solo-long su SOL, oppure se (come per lo short ingenuo) lo distrugge.

Confronta: solo-long  vs  long+short ingenuo  vs  long+short INTELLIGENTE.
Include: walk-forward OUT-OF-SAMPLE (split 2024-01-01), scansione di robustezza,
costi realistici. Niente lookahead: segnali alla chiusura, posizione dal bar dopo.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import talib.abstract as ta

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "user_data" / "data_sources" / "SOL_USDT-1h.csv"
OUTDIR = ROOT / "results"

COST = 0.0008          # 0.05% fee futures + 0.03% slippage, per lato
BARS_YEAR = 24 * 365
WU = 400               # riscaldamento per EMA400


def load():
    df = pd.read_csv(DATA, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    for p in (50, 200, 400):
        df[f"ema{p}"] = ta.EMA(df, timeperiod=p)
    df["adx"] = ta.ADX(df, timeperiod=14)
    df["atr"] = ta.ATR(df, timeperiod=14)
    return df


def gen(df, allow_short=False, smart=False,
        chand_long=6.0, chand_short=3.0, hardstop_short=0.08,
        adx_long=20, adx_short=25):
    c = df["close"].to_numpy(); e50 = df["ema50"].to_numpy()
    e200 = df["ema200"].to_numpy(); e400 = df["ema400"].to_numpy()
    adx = df["adx"].to_numpy(); atr = df["atr"].to_numpy()
    n = len(df); pos = np.zeros(n); state = 0; peak = trough = entry = 0.0
    for i in range(n):
        if i < WU or np.isnan(e400[i]) or np.isnan(adx[i]) or np.isnan(atr[i]):
            continue
        long_in = e50[i] > e200[i] and c[i] > e50[i] and adx[i] > adx_long
        if smart:   # short solo in downtrend MACRO confermato + momentum negativo
            short_in = (c[i] < e200[i] and c[i] < e400[i] and adx[i] > adx_short
                        and c[i] < c[i - 24])
        else:       # short ingenuo: ogni dip sotto le medie
            short_in = e50[i] < e200[i] and c[i] < e50[i] and adx[i] > adx_long

        if state == 0:
            if long_in:
                state, entry, peak = 1, c[i], c[i]
            elif allow_short and short_in:
                state, entry, trough = -1, c[i], c[i]
        elif state == 1:
            peak = max(peak, c[i])
            if c[i] < e200[i] or c[i] < peak - chand_long * atr[i]:
                state = 0
        elif state == -1:
            trough = min(trough, c[i])
            # stop piu' stretto sugli short (SOL rimbalza forte) + uscita su ritorno sopra EMA200
            if c[i] > e200[i] or c[i] > trough + chand_short * atr[i] or c[i] > entry * (1 + hardstop_short):
                state = 0
        pos[i] = state
    return pos


def simulate(pos, df, lo=None, hi=None):
    c = df["close"].reset_index(drop=True)
    p = pd.Series(pos)
    ep = p.shift(1).fillna(0)
    ret = c.pct_change().fillna(0)
    chg = ep.diff().abs().fillna(0)
    net = ep * ret - chg * COST
    mask = pd.Series(True, index=df.index)
    if lo is not None:
        mask &= df["date"] >= lo
    if hi is not None:
        mask &= df["date"] < hi
    idx = df.index[mask & (df.index >= WU)]
    sub = net.loc[idx]
    eq = (1 + sub).cumprod()
    dates = df["date"].loc[idx]
    years = (dates.iloc[-1] - dates.iloc[0]).days / 365.25
    total = eq.iloc[-1] - 1
    cagr = eq.iloc[-1] ** (1 / years) - 1 if years > 0 else np.nan
    r = eq.pct_change().dropna()
    sharpe = r.mean() / r.std() * np.sqrt(BARS_YEAR) if r.std() > 0 else np.nan
    dd = (eq / eq.cummax() - 1).min()
    epi = ep.loc[idx]
    trades = int(((epi.shift(1).fillna(0) == 0) & (epi != 0)).sum())
    expo = (epi != 0).mean()
    eq.index = dates.values
    return dict(total=total, cagr=cagr, dd=dd, sharpe=sharpe, trades=trades, expo=expo, eq=eq)


def row(label, m):
    print(f" {label:<26}{m['total']*100:>11.0f}%{m['cagr']*100:>8.0f}%{m['dd']*100:>8.0f}%"
          f"{m['sharpe']:>7.2f}{m['trades']:>7}{m['expo']*100:>7.0f}%")


def main():
    OUTDIR.mkdir(parents=True, exist_ok=True)
    df = load()
    SPLIT = pd.Timestamp("2024-01-01", tz="UTC")

    variants = {
        "Solo LONG": gen(df, allow_short=False),
        "LONG+SHORT ingenuo": gen(df, allow_short=True, smart=False),
        "LONG+SHORT intelligente": gen(df, allow_short=True, smart=True),
    }
    bh = np.ones(len(df))  # placeholder per buy&hold gestito a parte

    for title, lo, hi in [("INTERO PERIODO (2021-2026)", None, None),
                          ("IN-SAMPLE (2021-2023)", None, SPLIT),
                          ("OUT-OF-SAMPLE (2024-2026)", SPLIT, None)]:
        print("\n" + "=" * 74)
        print(f" {title}")
        print("=" * 74)
        print(f" {'strategia':<26}{'rend':>12}{'CAGR':>8}{'maxDD':>8}{'Shrp':>7}{'trade':>7}{'espos':>7}")
        print(" " + "-" * 72)
        for name, pos in variants.items():
            row(name, simulate(pos, df, lo, hi))
        # buy & hold
        c = df["close"]
        m = simulate((c > 0).astype(int).to_numpy() * 0 + 1, df, lo, hi)  # sempre long = buy&hold
        row("Buy & Hold", m)
    print("=" * 74)

    # robustezza dello SHORT intelligente (param vicini)
    print("\n ROBUSTEZZA short-intelligente (rend intero periodo):")
    for adx_s in (20, 25, 30):
        for cs in (2.5, 3.0, 4.0):
            m = simulate(gen(df, allow_short=True, smart=True, adx_short=adx_s, chand_short=cs), df)
            print(f"   ADX>{adx_s}, stopATR{cs}x: {m['total']*100:+.0f}%  (DD {m['dd']*100:.0f}%)", end="")
        print()

    # grafico intero periodo
    try:
        import matplotlib
        matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(11, 6))
        for name, pos in variants.items():
            e = simulate(pos, df)["eq"]
            ax.plot(e.index, e.values * 1000, lw=1.7, label=f"{name} ({(e.iloc[-1]-1)*100:+.0f}%)")
        bhe = simulate(np.ones(len(df)), df)["eq"]
        ax.plot(bhe.index, bhe.values * 1000, lw=1.1, alpha=0.6, label=f"Buy & Hold ({(bhe.iloc[-1]-1)*100:+.0f}%)")
        ax.set_yscale("log"); ax.set_ylabel("Equity da 1000 (log)"); ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8); ax.set_title("SOL 1h — Solo Long vs Long+Short (ingenuo / intelligente)")
        fig.tight_layout(); fig.savefig(OUTDIR / "sol_longshort.png", dpi=110)
        print("\n Grafico: results/sol_longshort.png")
    except Exception as e:
        print(f" (grafico saltato: {e})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

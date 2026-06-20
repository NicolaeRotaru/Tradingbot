#!/usr/bin/env python3
"""
Confronto di STRATEGIE MIGLIORATIVE sullo storico reale di Solana (daily).

Idea (coerente con docs/potenziamento-v2.md): la StarterStrategy attuale e'
troppo selettiva ed esce troppo presto (ROI stretto). Per alzare le performance
si passa al TREND-FOLLOWING: si partecipa al trend e si lasciano correre i
profitti, uscendo quando il trend si rompe.

Per NON fare overfitting si usano parametri CLASSICI (EMA 50/200, Donchian 20/10,
chandelier 3*ATR), non tarati su Solana. I risultati sono onesti, comprese le
robustezze (scansione di parametri vicini).

Modello: ogni strategia produce una posizione giornaliera 0/1 (long/flat) decisa
alla chiusura e ATTUATA il giorno dopo (niente lookahead). I costi (fee+slippage)
si pagano a ogni cambio di posizione. Niente leva, solo long.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import talib.abstract as ta

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "user_data" / "data_sources" / "solana_sol_usd_1d.csv"
OUTDIR = ROOT / "results"

FEE, SLIPPAGE = 0.0026, 0.0005
COST = FEE + SLIPPAGE
START = 1000.0
WARMUP = 200


def load():
    df = pd.read_csv(DATA, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    df["ema50"] = ta.EMA(df, timeperiod=50)
    df["ema100"] = ta.EMA(df, timeperiod=100)
    df["ema200"] = ta.EMA(df, timeperiod=200)
    df["atr"] = ta.ATR(df, timeperiod=14)
    return df


# ---------- generatori di posizione (0/1) ----------
def sig_ema_regime(df, period=200):
    return (df["close"] > df[f"ema{period}"]).to_numpy()


def sig_golden_cross(df, fast=50, slow=200):
    return (df[f"ema{fast}"] > df[f"ema{slow}"]).to_numpy()


def sig_donchian(df, entry_n=20, exit_n=10):
    close = df["close"].to_numpy()
    hh = df["high"].rolling(entry_n).max().shift(1).to_numpy()
    ll = df["low"].rolling(exit_n).min().shift(1).to_numpy()
    out = np.zeros(len(df), bool)
    state = False
    for i in range(len(df)):
        if not state and not np.isnan(hh[i]) and close[i] > hh[i]:
            state = True
        elif state and not np.isnan(ll[i]) and close[i] < ll[i]:
            state = False
        out[i] = state
    return out


def pos_voltarget_trend(df, ema=200, target_vol=0.50, lookback=20):
    """Trend EMA + VOL TARGETING: long quando close>EMA, ma con esposizione
    ridotta quando la volatilita' e' alta (Leva 2/4). Solo riduzione (max 1x,
    niente leva). Riduce il drawdown a costo di un po' di rendimento."""
    ret = df["close"].pct_change()
    realized = ret.rolling(lookback).std() * np.sqrt(365)
    scale = (target_vol / realized).clip(upper=1.0).fillna(0.0)
    trend = (df["close"] > df[f"ema{ema}"]).astype(float)
    target = (trend * scale).reset_index(drop=True)
    # Ribilanciamento SETTIMANALE (ogni 5 barre): evita di pagare costi ogni
    # giorno per micro-aggiustamenti di size.
    idx = pd.Series(np.arange(len(target)))
    held = target.where(idx % 5 == 0).ffill().fillna(0.0)
    return held.to_numpy()


def sig_chandelier(df, mult=3.0, ema=200):
    close = df["close"].to_numpy()
    high = df["high"].to_numpy()
    atr = df["atr"].to_numpy()
    emav = df[f"ema{ema}"].to_numpy()
    out = np.zeros(len(df), bool)
    state = False
    hh = 0.0
    for i in range(len(df)):
        if np.isnan(emav[i]) or np.isnan(atr[i]):
            out[i] = False
            continue
        if not state:
            if close[i] > emav[i]:
                state, hh = True, high[i]
        else:
            hh = max(hh, high[i])
            if close[i] < hh - mult * atr[i] or close[i] < emav[i]:
                state = False
        out[i] = state
    return out


# ---------- simulatore comune ----------
def simulate(in_long, df, start=WARMUP):
    close = df["close"].reset_index(drop=True)
    pos = pd.Series(np.asarray(in_long, dtype=float))
    exec_pos = pos.shift(1).fillna(0)          # decisione di oggi -> attiva domani
    ret = close.pct_change().fillna(0)
    changes = exec_pos.diff().abs().fillna(0)  # 1 a ogni cambio (entrata o uscita)
    net = exec_pos * ret - changes * COST
    net = net.iloc[start:]
    eq = (1 + net).cumprod() * START
    eq.index = df["date"].iloc[start:].values
    # n_trade = numero di "entrate" (da posizione nulla a posizione positiva)
    entries = (exec_pos.shift(1).fillna(0) <= 0) & (exec_pos > 0)
    n_trades = int(entries.iloc[start:].sum())
    exposure = (exec_pos.iloc[start:] > 0).mean()
    return eq, n_trades, exposure


def stats(eq, n_trades, exposure, label):
    years = (pd.Timestamp(eq.index[-1]) - pd.Timestamp(eq.index[0])).days / 365.25
    total = eq.iloc[-1] / eq.iloc[0] - 1
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1
    dret = eq.pct_change().dropna()
    sharpe = dret.mean() / dret.std() * np.sqrt(365) if dret.std() > 0 else np.nan
    max_dd = (eq / eq.cummax() - 1).min()
    calmar = cagr / abs(max_dd) if max_dd < 0 else np.nan
    return {
        "strategia": label,
        "rend_tot": total,
        "CAGR": cagr,
        "max_DD": max_dd,
        "Sharpe": sharpe,
        "Calmar": calmar,
        "trade": n_trades,
        "espos.": exposure,
        "_eq": eq,
    }


def main():
    OUTDIR.mkdir(parents=True, exist_ok=True)
    df = load()

    variants = {
        "TrendRegime EMA200": sig_ema_regime(df, 200),
        "GoldenCross 50/200": sig_golden_cross(df, 50, 200),
        "Donchian 20/10": sig_donchian(df, 20, 10),
        "Chandelier 3*ATR + EMA200": sig_chandelier(df, 3.0, 200),
        "TrendRegime + VolTarget 50%": pos_voltarget_trend(df, 200, 0.50, 20),
    }

    rows = []
    for name, sig in variants.items():
        eq, nt, exp = simulate(sig, df)
        rows.append(stats(eq, nt, exp, name))

    # buy & hold sullo stesso periodo
    bh_eq = (df["close"].iloc[WARMUP:] / df["close"].iloc[WARMUP]).reset_index(drop=True) * START
    bh_eq.index = df["date"].iloc[WARMUP:].values
    rows.append(stats(bh_eq, 1, 1.0, "Buy & Hold"))

    # riferimento: StarterStrategy attuale (dal backtest precedente)
    print("\n" + "=" * 92)
    print(" CONFRONTO STRATEGIE su SOLANA (SOL/USD daily, 2021-2024, solo long, niente leva)")
    print("=" * 92)
    hdr = f" {'strategia':<28}{'rend.tot':>10}{'CAGR':>9}{'maxDD':>9}{'Sharpe':>8}{'Calmar':>8}{'trade':>7}{'espos':>7}"
    print(hdr)
    print(" " + "-" * 90)
    for r in rows:
        print(f" {r['strategia']:<28}{r['rend_tot']*100:>9.0f}%{r['CAGR']*100:>8.0f}%"
              f"{r['max_DD']*100:>8.0f}%{r['Sharpe']:>8.2f}{r['Calmar']:>8.2f}"
              f"{r['trade']:>7}{r['espos.']*100:>6.0f}%")
    print(" " + "-" * 90)
    print(" (riferimento) StarterStrategy attuale: ~+22% rend, -10% DD, 9 trade, 1% esposizione")
    print("=" * 92)

    # robustezza: scansione parametri vicini per le due migliori idee
    print("\n ROBUSTEZZA (parametri vicini, per evitare l'illusione del singolo numero):")
    print("  TrendRegime EMA:", end=" ")
    for p in (100, 150, 200, 250):
        col = f"ema{p}"
        if col not in df:
            df[col] = ta.EMA(df, timeperiod=p)
        eq, _, _ = simulate((df["close"] > df[col]).to_numpy(), df)
        print(f"EMA{p}:{(eq.iloc[-1]/eq.iloc[0]-1)*100:+.0f}%", end="  ")
    print()
    print("  Chandelier mult:", end=" ")
    for m in (2.0, 2.5, 3.0, 3.5, 4.0):
        eq, _, _ = simulate(sig_chandelier(df, m, 200), df)
        print(f"{m}x:{(eq.iloc[-1]/eq.iloc[0]-1)*100:+.0f}%", end="  ")
    print()

    # grafico
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(11, 6))
        for r in rows:
            lw = 2.2 if r["strategia"] != "Buy & Hold" else 1.1
            al = 1.0 if r["strategia"] != "Buy & Hold" else 0.55
            ax.plot(r["_eq"].index, r["_eq"].values, label=f"{r['strategia']} ({r['rend_tot']*100:+.0f}%)", lw=lw, alpha=al)
        ax.set_yscale("log"); ax.set_ylabel("Equity (log)"); ax.grid(True, alpha=0.3); ax.legend(fontsize=8)
        ax.set_title("Solana (daily): strategie trend-following migliorate vs Buy & Hold")
        fig.tight_layout(); fig.savefig(OUTDIR / "solana_improved_compare.png", dpi=110)
        print("\n Grafico: results/solana_improved_compare.png")
    except Exception as e:
        print(f" (grafico saltato: {e})")

    # salva la migliore equity per riferimento
    best = max([r for r in rows if r["strategia"] != "Buy & Hold"], key=lambda r: r["Calmar"])
    best["_eq"].rename("equity").to_csv(OUTDIR / "solana_improved_best_equity.csv")
    print(f" Migliore per Calmar (rend/rischio): {best['strategia']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

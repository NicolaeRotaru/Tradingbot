#!/usr/bin/env python3
"""
Backtest LONG + SHORT della strategia sullo storico reale di Solana.

Versione bidirezionale di scripts/backtest_solana.py: oltre a COMPRARE in trend
rialzista (long), VENDE allo scoperto in trend ribassista (short). Lo short
richiede i FUTURES (margine), quindi qui usiamo leva 1x (nessuna amplificazione)
per mostrare il meccanismo nel modo meno rischioso possibile.

ATTENZIONE: lo short e' molto piu' rischioso del long. Con leva > 1 il rischio
(e il rischio di liquidazione) cresce in fretta. Questo e' un test su DATI
GIORNALIERI di una strategia pensata per l'orario: serve a far vedere il
funzionamento, non e' un consiglio operativo.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import talib.abstract as ta

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "user_data" / "data_sources" / "solana_sol_usd_1d.csv"
OUTDIR = ROOT / "results"

STOPLOSS = 0.10            # 10% contro la posizione -> stop
ROI = {0: 0.10, 360: 0.06, 720: 0.03, 1440: 0.0}
TRAIL_POSITIVE = 0.02
TRAIL_OFFSET = 0.03
EMA_TREND = 200
FEE, SLIPPAGE = 0.0026, 0.0005
COST = FEE + SLIPPAGE
START_CAPITAL = 1000.0
DAY_MIN = 1440


def roi_required(minutes: int) -> float:
    vals = [v for k, v in ROI.items() if k <= minutes]
    return min(vals) if vals else max(ROI.values())


def cross_up(s, i, lvl):
    return s[i - 1] <= lvl < s[i]


def cross_down(s, i, lvl):
    return s[i - 1] >= lvl > s[i]


def load():
    df = pd.read_csv(DATA, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    df["ema200"] = ta.EMA(df, timeperiod=EMA_TREND)
    df["rsi"] = ta.RSI(df, timeperiod=14)
    return df


def backtest(df):
    o, h, low, c = (df[x].to_numpy() for x in ["open", "high", "low", "close"])
    ema, rsi = df["ema200"].to_numpy(), df["rsi"].to_numpy()
    dates = df["date"]
    n = len(df)
    start = EMA_TREND

    eq = START_CAPITAL
    daily_eq = np.full(n, np.nan)
    in_pos = False
    side = None
    pending = None  # 'long' | 'short' | None
    entry_fill = entry_idx = eq_entry = 0.0
    peak = trough = 0.0
    days_in = 0
    trades = []

    for i in range(start, n):
        exited = False

        # --- apertura (segnale dato alla barra precedente) ---
        if (not in_pos) and pending:
            side = pending
            entry_price = o[i]
            entry_fill = entry_price * (1 - COST) if side == "short" else entry_price * (1 + COST)
            in_pos, entry_idx, eq_entry = True, i, eq
            peak = h[i]
            trough = low[i]
            pending = None

        # --- gestione posizione (uscite dal giorno dopo l'ingresso) ---
        if in_pos and i > entry_idx:
            days_in += 1
            peak = max(peak, h[i])
            trough = min(trough, low[i])
            minutes = (i - entry_idx) * DAY_MIN
            roi_req = roi_required(minutes)
            exit_price = reason = None

            if side == "long":
                sl = entry_fill * (1 - STOPLOSS)
                roi_p = entry_fill * (1 + roi_req)
                trail_on = (peak / entry_fill - 1) >= TRAIL_OFFSET
                trail_p = peak * (1 - TRAIL_POSITIVE)
                if low[i] <= sl:
                    exit_price, reason = sl, "stoploss"
                elif trail_on and low[i] <= trail_p:
                    exit_price, reason = trail_p, "trailing"
                elif h[i] >= roi_p:
                    exit_price, reason = roi_p, "roi"
                elif cross_up(rsi, i, 75):
                    exit_price, reason = c[i], "exit_signal"
                if exit_price is not None:
                    exit_fill = exit_price * (1 - COST)
                    ret = exit_fill / entry_fill - 1
            else:  # short
                sl = entry_fill * (1 + STOPLOSS)
                roi_p = entry_fill * (1 - roi_req)
                trail_on = (1 - trough / entry_fill) >= TRAIL_OFFSET
                trail_p = trough * (1 + TRAIL_POSITIVE)
                if h[i] >= sl:
                    exit_price, reason = sl, "stoploss"
                elif trail_on and h[i] >= trail_p:
                    exit_price, reason = trail_p, "trailing"
                elif low[i] <= roi_p:
                    exit_price, reason = roi_p, "roi"
                elif cross_down(rsi, i, 25):
                    exit_price, reason = c[i], "exit_signal"
                if exit_price is not None:
                    exit_fill = exit_price * (1 + COST)
                    ret = (entry_fill - exit_fill) / entry_fill

            if exit_price is not None:
                eq = eq_entry * (1 + ret)
                trades.append({
                    "side": side, "entry_date": dates[entry_idx].date(),
                    "exit_date": dates[i].date(), "bars_held": i - entry_idx,
                    "return_pct": round(ret * 100, 3), "reason": reason,
                })
                in_pos, exited = False, True
                daily_eq[i] = eq

        # mark-to-market
        if in_pos and not exited:
            if side == "long":
                daily_eq[i] = eq_entry * (c[i] / entry_fill)
            else:
                daily_eq[i] = eq_entry * (1 + (entry_fill - c[i]) / entry_fill)
        elif not in_pos and not exited:
            daily_eq[i] = eq

        # --- segnali per la prossima barra ---
        if not in_pos:
            if (c[i] > ema[i]) and cross_up(rsi, i, 35):
                pending = "long"
            elif (c[i] < ema[i]) and cross_down(rsi, i, 65):
                pending = "short"

    eqs = pd.Series(daily_eq[start:], index=dates[start:]).dropna()
    closes = pd.Series(c[start:], index=dates[start:])
    return eqs, pd.DataFrame(trades), days_in, closes


def report(eqs, trades, days_in, closes):
    years = (eqs.index[-1] - eqs.index[0]).days / 365.25
    total = eqs.iloc[-1] / eqs.iloc[0] - 1
    cagr = (eqs.iloc[-1] / eqs.iloc[0]) ** (1 / years) - 1
    dret = eqs.pct_change().dropna()
    sharpe = dret.mean() / dret.std() * np.sqrt(365) if dret.std() > 0 else np.nan
    max_dd = (eqs / eqs.cummax() - 1).min()
    n_long = int((trades.side == "long").sum()) if len(trades) else 0
    n_short = int((trades.side == "short").sum()) if len(trades) else 0
    win = (trades.return_pct > 0).mean() if len(trades) else np.nan
    bh = closes.iloc[-1] / closes.iloc[0] - 1

    rows = {
        "Periodo": f"{eqs.index[0].date()} -> {eqs.index[-1].date()} ({years:.1f} anni)",
        "Capitale finale (da 1000)": f"{eqs.iloc[-1]:.0f}",
        "Rendimento totale": f"{total*100:+.1f}%",
        "CAGR (annuo)": f"{cagr*100:+.1f}%",
        "Max drawdown": f"{max_dd*100:.1f}%",
        "Sharpe (annuo)": f"{sharpe:.2f}",
        "Trade totali": f"{len(trades)}  (long {n_long} / short {n_short})",
        "Win rate": f"{win*100:.1f}%" if not np.isnan(win) else "n/d",
        "Esposizione": f"{days_in/len(eqs)*100:.0f}% dei giorni",
        "Buy & Hold (confronto)": f"{bh*100:+.1f}%",
    }
    print("\n" + "=" * 60)
    print(" BACKTEST LONG + SHORT su SOLANA (SOL/USD, daily, leva 1x)")
    print("=" * 60)
    w = max(len(k) for k in rows)
    for k, v in rows.items():
        print(f" {k.ljust(w)} : {v}")
    print("=" * 60)
    return trades


def main():
    OUTDIR.mkdir(parents=True, exist_ok=True)
    df = load()
    eqs, trades, days_in, closes = backtest(df)
    trades = report(eqs, trades, days_in, closes)
    eqs.rename("equity").to_csv(OUTDIR / "solana_ls_equity.csv")
    trades.to_csv(OUTDIR / "solana_ls_trades.csv", index=False)
    print(" Salvati: results/solana_ls_equity.csv, results/solana_ls_trades.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

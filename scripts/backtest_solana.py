#!/usr/bin/env python3
"""
Backtest STANDALONE e FEDELE della StarterStrategy sullo storico reale di
Solana (SOL/USD, giornaliero, 2021-2024).

Perche' standalone: in questo ambiente il proxy di rete blocca gli exchange,
e il motore di Freqtrade richiede di caricare i mercati dall'exchange via rete
(quindi non puo' partire qui). Questo script riproduce la STESSA logica della
strategia (vedi user_data/strategies/StarterStrategy.py) con costi realistici,
cosi' possiamo avere numeri veri sui dati veri.

NB: i dati raggiungibili sono GIORNALIERI, mentre la strategia e' pensata per
l'orario. Il backtest gira quindi su timeframe 1d (EMA200 = filtro a 200 giorni).
E' un risultato reale ma di lungo periodo; per il vero 1h servono dati orari.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import talib.abstract as ta

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "user_data" / "data_sources" / "solana_sol_usd_1d.csv"
OUTDIR = ROOT / "results"

# --- Parametri identici a StarterStrategy ---------------------------------
STOPLOSS = -0.10
ROI = {0: 0.10, 360: 0.06, 720: 0.03, 1440: 0.0}  # chiavi in MINUTI
TRAIL_POSITIVE = 0.02   # trailing stop = 2% sotto il picco
TRAIL_OFFSET = 0.03     # si attiva dopo +3% di profitto
RSI_ENTRY = 35
RSI_EXIT = 75
EMA_TREND = 200

# --- Costi realistici (lato Kraken, conto piccolo) ------------------------
FEE = 0.0026        # 0.26% taker per lato
SLIPPAGE = 0.0005   # 0.05% per lato
COST = FEE + SLIPPAGE  # costo per lato applicato al prezzo di fill

START_CAPITAL = 1000.0
BARS_PER_DAY_MIN = 1440  # 1 candela giornaliera = 1440 minuti


def roi_required(minutes: int) -> float:
    """Soglia ROI in funzione dei minuti trascorsi (come Freqtrade)."""
    applicable = [v for k, v in ROI.items() if k <= minutes]
    return min(applicable) if applicable else max(ROI.values())


def crossed_above(series: np.ndarray, i: int, level: float) -> bool:
    return series[i - 1] <= level < series[i]


def load() -> pd.DataFrame:
    df = pd.read_csv(DATA, parse_dates=["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["ema200"] = ta.EMA(df, timeperiod=EMA_TREND)
    df["rsi"] = ta.RSI(df, timeperiod=14)
    df["atr"] = ta.ATR(df, timeperiod=14)
    return df


def backtest(df: pd.DataFrame):
    o = df["open"].to_numpy()
    h = df["high"].to_numpy()
    low = df["low"].to_numpy()
    c = df["close"].to_numpy()
    ema = df["ema200"].to_numpy()
    rsi = df["rsi"].to_numpy()
    dates = df["date"]
    n = len(df)

    start = EMA_TREND  # prime 200 barre = riscaldamento EMA200

    eq = START_CAPITAL
    daily_eq = np.full(n, np.nan)

    in_pos = False
    pending_entry = False
    entry_fill = entry_idx = eq_entry = peak = 0.0
    days_in_market = 0
    trades = []

    for i in range(start, n):
        exited_today = False

        # --- ENTRATA (segnalata alla barra precedente, eseguita all'apertura) ---
        if (not in_pos) and pending_entry:
            entry_fill = o[i] * (1 + COST)
            in_pos = True
            entry_idx = i
            eq_entry = eq
            peak = h[i]
            pending_entry = False

        # --- GESTIONE POSIZIONE APERTA ---
        # Le uscite si valutano dal giorno SUCCESSIVO all'ingresso (i > entry_idx):
        # su candele giornaliere non conosciamo l'ordine intra-giorno di high/low,
        # quindi evitiamo round-trip ottimistici nello stesso giorno d'ingresso.
        if in_pos and i > entry_idx:
            days_in_market += 1
            peak = max(peak, h[i])
            minutes = (i - entry_idx) * BARS_PER_DAY_MIN
            roi_req = roi_required(minutes)

            sl_price = entry_fill * (1 + STOPLOSS)
            roi_price = entry_fill * (1 + roi_req)
            trail_active = (peak / entry_fill - 1) >= TRAIL_OFFSET
            trail_price = peak * (1 - TRAIL_POSITIVE)

            exit_price = None
            reason = None
            # Priorita': prima il lato negativo (stop/trailing), poi ROI, poi segnale.
            if low[i] <= sl_price:
                exit_price, reason = sl_price, "stoploss"
            elif trail_active and low[i] <= trail_price:
                exit_price, reason = trail_price, "trailing"
            elif h[i] >= roi_price:
                exit_price, reason = roi_price, "roi"
            elif crossed_above(rsi, i, RSI_EXIT):
                exit_price, reason = c[i], "exit_signal"

            if exit_price is not None:
                exit_fill = exit_price * (1 - COST)
                ret = exit_fill / entry_fill - 1
                eq = eq_entry * (1 + ret)
                trades.append(
                    {
                        "entry_date": dates[entry_idx].date(),
                        "exit_date": dates[i].date(),
                        "bars_held": i - entry_idx,
                        "entry": round(entry_fill, 4),
                        "exit": round(exit_fill, 4),
                        "return_pct": round(ret * 100, 3),
                        "reason": reason,
                    }
                )
                in_pos = False
                exited_today = True
                daily_eq[i] = eq

        # mark-to-market giornaliero mentre la posizione e' aperta
        if in_pos and not exited_today:
            daily_eq[i] = eq_entry * (c[i] / entry_fill)
        elif not in_pos and not exited_today:
            daily_eq[i] = eq

        # --- SEGNALE per entrare alla prossima barra ---
        if (not in_pos) and (c[i] > ema[i]) and crossed_above(rsi, i, RSI_ENTRY):
            pending_entry = True

    eqs = pd.Series(daily_eq[start:], index=dates[start:]).dropna()
    closes = pd.Series(c[start:], index=dates[start:])
    return eqs, pd.DataFrame(trades), days_in_market, closes


def metrics(eqs: pd.Series, trades: pd.DataFrame, days_in_market: int,
            closes: pd.Series):
    c_start = closes.iloc[0]
    c_end = closes.iloc[-1]
    days = (eqs.index[-1] - eqs.index[0]).days
    years = days / 365.25
    total_ret = eqs.iloc[-1] / eqs.iloc[0] - 1
    cagr = (eqs.iloc[-1] / eqs.iloc[0]) ** (1 / years) - 1 if years > 0 else np.nan

    dret = eqs.pct_change().dropna()
    sharpe = dret.mean() / dret.std() * np.sqrt(365) if dret.std() > 0 else np.nan
    downside = dret[dret < 0].std()
    sortino = dret.mean() / downside * np.sqrt(365) if downside and downside > 0 else np.nan
    max_dd = (eqs / eqs.cummax() - 1).min()

    if len(trades):
        wins = trades[trades.return_pct > 0]
        losses = trades[trades.return_pct <= 0]
        win_rate = len(wins) / len(trades)
        gross_win = wins.return_pct.clip(lower=0).sum()
        gross_loss = abs(losses.return_pct.sum())
        pf = gross_win / gross_loss if gross_loss > 0 else np.inf
        avg_trade = trades.return_pct.mean()
        avg_hold = trades.bars_held.mean()
    else:
        win_rate = pf = avg_trade = avg_hold = np.nan

    bh_ret = c_end / c_start - 1  # buy & hold sullo stesso periodo (lordo)
    bh_curve = closes / c_start
    bh_dd = (bh_curve / bh_curve.cummax() - 1).min()
    exposure = days_in_market / len(eqs)

    return {
        "Periodo backtest": f"{eqs.index[0].date()} -> {eqs.index[-1].date()} ({years:.1f} anni)",
        "Capitale iniziale": f"{START_CAPITAL:.0f}",
        "Capitale finale": f"{eqs.iloc[-1]:.0f}",
        "Rendimento totale": f"{total_ret*100:+.1f}%",
        "CAGR (annuo)": f"{cagr*100:+.1f}%",
        "Max drawdown": f"{max_dd*100:.1f}%",
        "Sharpe (annuo)": f"{sharpe:.2f}",
        "Sortino (annuo)": f"{sortino:.2f}",
        "Numero trade": f"{len(trades)}",
        "Win rate": f"{win_rate*100:.1f}%" if not np.isnan(win_rate) else "n/d",
        "Profit factor": f"{pf:.2f}" if not np.isnan(pf) else "n/d",
        "Trade medio": f"{avg_trade:+.2f}%" if not np.isnan(avg_trade) else "n/d",
        "Durata media trade": f"{avg_hold:.1f} giorni" if not np.isnan(avg_hold) else "n/d",
        "Esposizione (in mercato)": f"{exposure*100:.0f}% dei giorni",
        "--- confronto ---": "",
        "Buy & Hold (rendimento)": f"{bh_ret*100:+.1f}%",
        "Buy & Hold (max drawdown)": f"{bh_dd*100:.1f}%",
    }


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    df = load()
    eqs, trades, dim, closes = backtest(df)
    c_start = closes.iloc[0]
    m = metrics(eqs, trades, dim, closes)

    print("\n" + "=" * 58)
    print(" BACKTEST StarterStrategy su SOLANA (SOL/USD, daily)")
    print("=" * 58)
    width = max(len(k) for k in m)
    for k, v in m.items():
        print(f" {k.ljust(width)} : {v}")
    print("=" * 58)

    eqs.rename("equity").to_csv(OUTDIR / "solana_equity.csv")
    trades.to_csv(OUTDIR / "solana_trades.csv", index=False)
    print(f" Salvati: results/solana_equity.csv, results/solana_trades.csv")

    # Grafico equity curve (se matplotlib e' disponibile).
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        bh = START_CAPITAL * (df.set_index("date")["close"].loc[eqs.index] / c_start)
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(eqs.index, eqs.values, label="StarterStrategy", lw=1.6)
        ax.plot(bh.index, bh.values, label="Buy & Hold SOL", lw=1.2, alpha=0.7)
        ax.set_yscale("log")
        ax.set_title("Backtest StarterStrategy vs Buy & Hold — Solana (daily)")
        ax.set_ylabel("Equity (scala log)")
        ax.legend()
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(OUTDIR / "solana_equity.png", dpi=110)
        print(" Grafico: results/solana_equity.png")
    except Exception as e:  # pragma: no cover
        print(f" (grafico saltato: {e})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

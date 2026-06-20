#!/usr/bin/env python3
"""
Backtest 1h MULTI-ASSET della TrendFollowStrategy — la vera validazione
fuori campione (timeframe 1h invece che daily, e BTC/ETH oltre a SOL).

Legge i CSV orari da user_data/data_sources/<SYM>_USDT-1h.csv (prodotti da
scripts/download_1h_data.py sul PC dell'utente e pushati su GitHub).

Riproduce la logica di TrendFollowStrategy (close-based, senza trailing
intrabar): long quando il trend e' confermato (EMA50>EMA200 & close>EMA50 &
ADX>20) e si esce quando il trend si rompe (close<EMA200). Costi realistici.
Confronto con buy & hold per ogni asset + portafoglio equipesato.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import talib.abstract as ta

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "user_data" / "data_sources"
OUTDIR = ROOT / "results"

SYMBOLS = ["SOL_USDT", "BTC_USDT", "ETH_USDT"]
FEE, SLIPPAGE = 0.0010, 0.0005      # 0.10% taker (Binance) + 0.05% slippage
COST = FEE + SLIPPAGE
START = 1000.0
WARMUP = 200
BARS_YEAR = 24 * 365                # candele orarie in un anno (per Sharpe)


def load(sym: str) -> pd.DataFrame | None:
    path = SRC / f"{sym}-1h.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    df["ema50"] = ta.EMA(df, timeperiod=50)
    df["ema200"] = ta.EMA(df, timeperiod=200)
    df["adx"] = ta.ADX(df, timeperiod=14)
    return df


def position(df: pd.DataFrame) -> np.ndarray:
    """State machine: long da quando il trend e' confermato fino alla rottura."""
    ema50, ema200 = df["ema50"].to_numpy(), df["ema200"].to_numpy()
    close, adx = df["close"].to_numpy(), df["adx"].to_numpy()
    enter = (ema50 > ema200) & (close > ema50) & (adx > 20)
    exit_ = close < ema200
    pos = np.zeros(len(df))
    state = False
    for i in range(len(df)):
        if np.isnan(ema200[i]) or np.isnan(adx[i]):
            pos[i] = 0.0
            continue
        if not state and enter[i]:
            state = True
        elif state and exit_[i]:
            state = False
        pos[i] = 1.0 if state else 0.0
    return pos


def simulate(pos: np.ndarray, df: pd.DataFrame):
    close = df["close"].reset_index(drop=True)
    p = pd.Series(pos)
    exec_p = p.shift(1).fillna(0)                 # decisione di ora -> attiva alla candela dopo
    ret = close.pct_change().fillna(0)
    changes = exec_p.diff().abs().fillna(0)
    net = (exec_p * ret - changes * COST).iloc[WARMUP:]
    eq = (1 + net).cumprod() * START
    eq.index = df["date"].iloc[WARMUP:].values
    entries = ((exec_p.shift(1).fillna(0) <= 0) & (exec_p > 0)).iloc[WARMUP:].sum()
    expo = (exec_p.iloc[WARMUP:] > 0).mean()
    return eq, int(entries), float(expo)


def metrics(eq: pd.Series, n_trades: int, expo: float, label: str):
    years = (pd.Timestamp(eq.index[-1]) - pd.Timestamp(eq.index[0])).days / 365.25
    total = eq.iloc[-1] / eq.iloc[0] - 1
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1 if years > 0 else np.nan
    r = eq.pct_change().dropna()
    sharpe = r.mean() / r.std() * np.sqrt(BARS_YEAR) if r.std() > 0 else np.nan
    dd = (eq / eq.cummax() - 1).min()
    calmar = cagr / abs(dd) if dd < 0 else np.nan
    return dict(label=label, total=total, cagr=cagr, dd=dd, sharpe=sharpe,
                calmar=calmar, trades=n_trades, expo=expo, eq=eq)


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    results = []
    strat_eqs = []

    print("\n" + "=" * 96)
    print(" BACKTEST 1h MULTI-ASSET — TrendFollowStrategy vs Buy & Hold (solo long, niente leva)")
    print("=" * 96)
    print(f" {'asset / strategia':<30}{'rend.tot':>11}{'CAGR':>9}{'maxDD':>9}{'Sharpe':>8}{'Calmar':>8}{'trade':>7}{'espos':>7}")
    print(" " + "-" * 94)

    for sym in SYMBOLS:
        df = load(sym)
        if df is None:
            print(f" [MANCA] {sym}-1h.csv  (esegui download_1h_data.py e fai push)")
            continue
        pos = position(df)
        eq, nt, expo = simulate(pos, df)
        m = metrics(eq, nt, expo, f"{sym}  TrendFollow")
        results.append(m)
        strat_eqs.append(eq.rename(sym))

        # buy & hold sullo stesso periodo
        c = df["close"].iloc[WARMUP:]
        bh = (c / c.iloc[0] * START)
        bh.index = df["date"].iloc[WARMUP:].values
        mb = metrics(bh, 1, 1.0, f"{sym}  Buy & Hold")

        for r in (m, mb):
            print(f" {r['label']:<30}{r['total']*100:>10.0f}%{r['cagr']*100:>8.0f}%"
                  f"{r['dd']*100:>8.0f}%{r['sharpe']:>8.2f}{r['calmar']:>8.2f}"
                  f"{r['trades']:>7}{r['expo']*100:>6.0f}%")
        print(" " + "-" * 94)

    # portafoglio equipesato delle strategie (rib. giornaliero implicito sulle equity)
    if len(strat_eqs) >= 2:
        common = pd.concat(strat_eqs, axis=1).dropna()
        rets = common.pct_change().fillna(0)
        port_eq = (1 + rets.mean(axis=1)).cumprod() * START
        mp = metrics(port_eq, sum(r["trades"] for r in results), np.nan,
                     "PORTAFOGLIO equipesato")
        print(f" {mp['label']:<30}{mp['total']*100:>10.0f}%{mp['cagr']*100:>8.0f}%"
              f"{mp['dd']*100:>8.0f}%{mp['sharpe']:>8.2f}{mp['calmar']:>8.2f}"
              f"{'':>7}{'':>7}")
        print("=" * 96)
        strat_eqs.append(port_eq.rename("PORTAFOGLIO"))

    # grafico
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(11, 6))
        for s in strat_eqs:
            ax.plot(s.index, s.values, lw=1.6, label=f"{s.name} ({s.iloc[-1]/s.iloc[0]-1:+.0%})")
        ax.set_yscale("log"); ax.set_ylabel("Equity (log)"); ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8); ax.set_title("TrendFollowStrategy 1h — SOL / BTC / ETH + portafoglio")
        fig.tight_layout(); fig.savefig(OUTDIR / "backtest_1h_multiasset.png", dpi=110)
        print(" Grafico: results/backtest_1h_multiasset.png")
    except Exception as e:
        print(f" (grafico saltato: {e})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

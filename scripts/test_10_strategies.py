#!/usr/bin/env python3
"""
10 STRATEGIE COMPLETAMENTE DIVERSE su SOL — test onesto, alpha vs beta.

SOL è passato da ~$1.5 a ~$150: QUALSIASI strategia long sembra buona per il beta.
Quindi il test vero NON è il rendimento grezzo, ma il RISCHIO-AGGIUSTATO (Sharpe,
Calmar, MaxDD) e la ROBUSTEZZA fuori campione (IS vs OOS, per anno), confrontato
SEMPRE con Buy & Hold.

Motore: long/flat (1=long, 0=fuori). Nessun lookahead: il segnale alla chiusura della
barra t determina la posizione tenuta DURANTE la barra t+1 (shift di 1). Fee 0.06%/lato
applicata a ogni cambio di posizione.

10 famiglie diverse:
  1. EMA cross 20/50           (trend veloce)
  2. EMA cross 50/200          (golden cross, trend lento)
  3. Donchian 20 breakout      (turtle corto)
  4. Donchian 55 breakout      (turtle lungo)
  5. Time-series momentum      (close > close[N])
  6. MACD (12/26/9)            (momentum oscillatore)
  7. Bollinger breakout        (volatilità: rompe banda alta)
  8. RSI mean-reversion        (oversold, diverso dal V-bounce)
  9. Trend filter EMA200       (long solo sopra la media madre)
 10. Keltner/ATR breakout      (rompe canale EMA+1.5×ATR)

+ riferimenti: BUY & HOLD.

Usage: python3 scripts/test_10_strategies.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research"))
from indicators import ema, rsi, atr, adx, bollinger  # noqa: E402

DATA15 = ROOT / "user_data" / "data_sources" / "SOL_USDT-15m.csv"
SPLIT = pd.Timestamp("2024-01-01", tz="UTC")
FEE_SIDE = 0.0006
WARMUP = 300


# ---------------------------------------------------------------------------
# SEGNALI: ciascuno ritorna un array 0/1 = posizione DESIDERATA a fine barra t
# (usando solo dati fino a t). Il backtester applica shift(1) per evitare lookahead.
# ---------------------------------------------------------------------------
def s_ema_cross(d, fast=20, slow=50):
    ef, es = ema(d["close"], fast), ema(d["close"], slow)
    return (ef > es).astype(int).to_numpy()


def s_ema_cross_slow(d, fast=50, slow=200):
    ef, es = ema(d["close"], fast), ema(d["close"], slow)
    return (ef > es).astype(int).to_numpy()


def _stateful_channel(upper_break, lower_exit):
    """Entra quando upper_break, esce quando lower_exit; mantiene in mezzo (isteresi)."""
    n = len(upper_break)
    pos = np.zeros(n, dtype=int)
    cur = 0
    for i in range(n):
        if cur == 0 and upper_break[i]:
            cur = 1
        elif cur == 1 and lower_exit[i]:
            cur = 0
        pos[i] = cur
    return pos


def s_donchian(d, entry=20, exit_=10):
    high = d["high"].to_numpy(); low = d["low"].to_numpy(); close = d["close"].to_numpy()
    hh = pd.Series(high).shift(1).rolling(entry).max().to_numpy()
    ll = pd.Series(low).shift(1).rolling(exit_).min().to_numpy()
    up = close > hh
    dn = close < ll
    up = np.where(np.isfinite(hh), up, False)
    dn = np.where(np.isfinite(ll), dn, False)
    return _stateful_channel(up, dn)


def s_donchian55(d):
    return s_donchian(d, entry=55, exit_=20)


def s_ts_momentum(d, lookback=96):
    c = d["close"].to_numpy()
    past = pd.Series(c).shift(lookback).to_numpy()
    sig = np.where(np.isfinite(past), c > past, False)
    return sig.astype(int)


def s_macd(d, fast=12, slow=26, signal=9):
    ef, es = ema(d["close"], fast), ema(d["close"], slow)
    macd = ef - es
    sig = ema(macd, signal)
    return (macd > sig).astype(int).to_numpy()


def s_bollinger_breakout(d, window=20, k=2.0):
    bl, bm, bu = bollinger(d["close"], window, k)
    close = d["close"].to_numpy()
    up = close > bu.to_numpy()       # rompe banda alta = momentum
    dn = close < bm.to_numpy()       # rientra sotto la media = esci
    up = np.where(np.isfinite(bu.to_numpy()), up, False)
    dn = np.where(np.isfinite(bm.to_numpy()), dn, False)
    return _stateful_channel(up, dn)


def s_rsi_meanrev(d, lo=30, hi=55):
    r = rsi(d["close"], 14).to_numpy()
    up = r < lo                       # oversold = entra
    dn = r > hi                       # recuperato = esci
    up = np.where(np.isfinite(r), up, False)
    dn = np.where(np.isfinite(r), dn, False)
    return _stateful_channel(up, dn)


def s_trend_filter(d):
    e200 = ema(d["close"], 200)
    return (d["close"] > e200).astype(int).to_numpy()


def s_keltner_breakout(d, window=20, mult=1.5):
    e = ema(d["close"], window)
    a = atr(d, 14)
    upper = (e + mult * a).to_numpy()
    close = d["close"].to_numpy()
    up = close > upper
    dn = close < e.to_numpy()
    up = np.where(np.isfinite(upper), up, False)
    dn = np.where(np.isfinite(e.to_numpy()), dn, False)
    return _stateful_channel(up, dn)


STRATS = [
    ("1. EMA cross 20/50",      s_ema_cross),
    ("2. EMA cross 50/200",     s_ema_cross_slow),
    ("3. Donchian 20 breakout", s_donchian),
    ("4. Donchian 55 breakout", s_donchian55),
    ("5. TS momentum (1d)",     s_ts_momentum),
    ("6. MACD 12/26/9",         s_macd),
    ("7. Bollinger breakout",   s_bollinger_breakout),
    ("8. RSI mean-reversion",   s_rsi_meanrev),
    ("9. Trend filter EMA200",  s_trend_filter),
    ("10. Keltner ATR breakout", s_keltner_breakout),
]


# ---------------------------------------------------------------------------
# MOTORE long/flat con fee e metriche rischio-aggiustate
# ---------------------------------------------------------------------------
def run(d, signal, bars_per_year):
    """d ordinato per data, con colonne close/high/low. signal = pos desiderata a fine t."""
    close = d["close"].to_numpy()
    bar_ret = np.zeros(len(close))
    bar_ret[1:] = close[1:] / close[:-1] - 1.0

    eff_pos = np.zeros(len(close))           # posizione tenuta DURANTE la barra t = signal[t-1]
    eff_pos[1:] = signal[:-1]
    # costo quando la posizione effettiva cambia
    turn = np.zeros(len(close))
    turn[1:] = np.abs(eff_pos[1:] - eff_pos[:-1])
    cost = turn * FEE_SIDE

    strat_ret = eff_pos * bar_ret - cost
    eq = np.cumprod(1.0 + strat_ret)
    n_trades = int(np.sum((eff_pos[1:] == 1) & (eff_pos[:-1] == 0)))
    return eq, strat_ret, eff_pos, n_trades


def metrics(eq, strat_ret, eff_pos, n_trades, close, bars_per_year):
    total = eq[-1] - 1.0
    years = len(eq) / bars_per_year
    cagr = eq[-1] ** (1.0 / years) - 1.0 if years > 0 and eq[-1] > 0 else -1.0
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    maxdd = dd.min()
    sd = strat_ret.std()
    sharpe = (strat_ret.mean() / sd * np.sqrt(bars_per_year)) if sd > 0 else np.nan
    calmar = (cagr / abs(maxdd)) if maxdd < 0 else np.nan
    expo = eff_pos.mean()
    bh = close[-1] / close[0] - 1.0
    return dict(total=total, cagr=cagr, maxdd=maxdd, sharpe=sharpe, calmar=calmar,
                expo=expo, n=n_trades, bh=bh)


def slice_metrics(d, signal, lo, hi, bars_per_year):
    sub = d.iloc[lo:hi].reset_index(drop=True)
    sig = signal[lo:hi]
    eq, sr, ep, nt = run(sub, sig, bars_per_year)
    return metrics(eq, sr, ep, nt, sub["close"].to_numpy(), bars_per_year)


def test_timeframe(d, tf_name, bars_per_year):
    d = d.iloc[WARMUP:].reset_index(drop=True)
    split_idx = int((d["date"] < SPLIT).sum())
    n = len(d)

    print("\n" + "#" * 92)
    print(f"# TIMEFRAME {tf_name}  ({n} candele)  —  IS=[0:{split_idx}]  OOS=[{split_idx}:{n}]  (split 2024-01-01)")
    print("#" * 92)

    # Buy & Hold reference
    bh_sig = np.ones(n, dtype=int)
    bh_full = slice_metrics(d, bh_sig, 0, n, bars_per_year)
    bh_oos  = slice_metrics(d, bh_sig, split_idx, n, bars_per_year)
    print(f"\n  BUY & HOLD   full: ret {bh_full['total']*100:+.0f}%  CAGR {bh_full['cagr']*100:+.0f}%  "
          f"Sharpe {bh_full['sharpe']:.2f}  MaxDD {bh_full['maxdd']*100:.0f}%  Calmar {bh_full['calmar']:.2f}")
    print(f"  BUY & HOLD    OOS: ret {bh_oos['total']*100:+.0f}%  CAGR {bh_oos['cagr']*100:+.0f}%  "
          f"Sharpe {bh_oos['sharpe']:.2f}  MaxDD {bh_oos['maxdd']*100:.0f}%  Calmar {bh_oos['calmar']:.2f}")

    hdr = (f"\n  {'strategia':<26} {'ret%':>7} {'CAGR%':>7} {'Shrp':>5} {'MaxDD%':>7} "
           f"{'Calm':>5} {'expo':>5} {'#tr':>5} | {'OOS Shrp':>8} {'OOS Calm':>8} {'OOS ret%':>8} {'verdetto'}")
    print(hdr)
    print("  " + "-" * 118)

    results = []
    for name, fn in STRATS:
        sig = fn(d)
        full = slice_metrics(d, sig, 0, n, bars_per_year)
        is_  = slice_metrics(d, sig, 0, split_idx, bars_per_year)
        oos  = slice_metrics(d, sig, split_idx, n, bars_per_year)
        # verdetto: batte B&H OOS su Calmar/Sharpe E positivo IS E OOS
        beats_bh = (oos["sharpe"] > bh_oos["sharpe"]) and (oos["calmar"] > bh_oos["calmar"])
        robust = (is_["sharpe"] > 0) and (oos["sharpe"] > 0)
        if beats_bh and robust:
            verdict = "✅ batte B&H robusto"
        elif robust and oos["total"] > 0:
            verdict = "~ positivo no-alpha"
        else:
            verdict = "❌"
        print(f"  {name:<26} {full['total']*100:>+7.0f} {full['cagr']*100:>+7.0f} "
              f"{full['sharpe']:>5.2f} {full['maxdd']*100:>7.0f} {full['calmar']:>5.2f} "
              f"{full['expo']:>5.2f} {full['n']:>5} | {oos['sharpe']:>8.2f} {oos['calmar']:>8.2f} "
              f"{oos['total']*100:>+8.0f} {verdict}")
        results.append((name, full, is_, oos))

    return results, bh_oos


def per_year(d, tf_name, bars_per_year, top_names):
    """Robustezza per anno delle strategie migliori."""
    d = d.iloc[WARMUP:].reset_index(drop=True)
    d2 = d.copy()
    d2["year"] = pd.to_datetime(d2["date"]).dt.year
    print(f"\n  --- {tf_name}: Sharpe per anno (strategie selezionate) ---")
    for name, fn in STRATS:
        if name not in top_names:
            continue
        sig = fn(d)
        line = f"  {name:<26} "
        for yr in sorted(d2["year"].unique()):
            idx = np.where(d2["year"].to_numpy() == yr)[0]
            if len(idx) < 50:
                continue
            lo, hi = idx[0], idx[-1] + 1
            m = slice_metrics(d, sig, lo, hi, bars_per_year)
            mark = "+" if (m["sharpe"] and m["sharpe"] > 0) else "-"
            line += f"{yr}:{m['sharpe']:>5.1f}{mark} "
        print(line)


def resample(d, rule):
    s = d.set_index("date")
    out = pd.DataFrame({
        "open": s["open"].resample(rule).first(),
        "high": s["high"].resample(rule).max(),
        "low": s["low"].resample(rule).min(),
        "close": s["close"].resample(rule).last(),
        "volume": s["volume"].resample(rule).sum(),
    }).dropna().reset_index()
    return out


def main():
    df = pd.read_csv(DATA15, parse_dates=["date"]).sort_values("date").reset_index(drop=True)

    print("=" * 92)
    print(" 10 STRATEGIE DIVERSE su SOL — alpha vs beta (rischio-aggiustato, IS/OOS)")
    print(" Regola: 'batte B&H robusto' = Sharpe E Calmar OOS > Buy&Hold, E Sharpe>0 sia IS che OOS")
    print("=" * 92)

    # 15m nativo: 96 barre/giorno
    res15, bh15 = test_timeframe(df, "15m", bars_per_year=96 * 365)

    # 4h resampled: 6 barre/giorno
    d4 = resample(df, "4h")
    res4, bh4 = test_timeframe(d4, "4h", bars_per_year=6 * 365)

    # 1d resampled: 1 barra/giorno
    d1 = resample(df, "1D")
    res1, bh1 = test_timeframe(d1, "1d", bars_per_year=365)

    # Robustezza per anno: top per Sharpe OOS su ogni timeframe
    def top3(res):
        return [n for n, _, _, o in sorted(res, key=lambda x: -(x[3]["sharpe"] if np.isfinite(x[3]["sharpe"]) else -9))[:3]]
    per_year(df, "15m", 96 * 365, top3(res15))
    per_year(d4, "4h", 6 * 365, top3(res4))
    per_year(d1, "1d", 365, top3(res1))

    print("\n" + "=" * 92)
    print(" Lettura: '✅ batte B&H robusto' è l'unico esito che giustifica il trading attivo.")
    print(" Un alto rendimento con Sharpe < Buy&Hold = stai solo cavalcando il beta di SOL")
    print(" (e pagando fee). Se NESSUNA batte B&H OOS → su SOL conviene comprare e tenere.")
    print("=" * 92)


if __name__ == "__main__":
    main()

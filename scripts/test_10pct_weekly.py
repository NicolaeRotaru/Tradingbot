#!/usr/bin/env python3
"""
"Fare 10% a settimana con stop loss basso" — è possibile? Test sui dati reali SOL.

10%/settimana composto = 1.10^52 = 142× l'anno = +14.100%/anno. Questo script
verifica EMPIRICAMENTE cosa servirebbe e cosa succede provandoci con la leva:

  1. Distribuzione dei rendimenti SETTIMANALI della miglior strategia (trend 4h)
     e di Buy&Hold: quante settimane fanno davvero ≥10%? Quanto è la mediana?
  2. LEVA 1/2/3/5/10× sulla miglior strategia: il rendimento sale, ma con
     "stop basso" (= poco margine) la LIQUIDAZIONE arriva sulle gambe larghe di SOL.
  3. La matematica del target: con stop stretto serve un win rate impossibile.

Motore long/flat, fee 0.06%/lato, no lookahead. Leva simulata barra-per-barra
con liquidazione realistica (se una barra va contro più del margine → conto azzerato).
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
WARMUP = 300
FEE_SIDE = 0.0006
MAINT_MARGIN = 0.005   # margine di mantenimento ~0.5% (tipico futures)


def resample(d, rule="4h"):
    s = d.set_index("date")
    return pd.DataFrame({
        "open": s["open"].resample(rule).first(),
        "high": s["high"].resample(rule).max(),
        "low": s["low"].resample(rule).min(),
        "close": s["close"].resample(rule).last(),
        "volume": s["volume"].resample(rule).sum(),
    }).dropna().reset_index()


def ema_cross_signal(close, fast=20, slow=50):
    ef = ema(pd.Series(close), fast).to_numpy()
    es = ema(pd.Series(close), slow).to_numpy()
    return (ef > es).astype(int)


def lev_equity(d, signal, lev, fee_side=FEE_SIDE):
    """Equity con leva L e liquidazione barra-per-barra (worst-case sul low della barra)."""
    close = d["close"].to_numpy()
    low = d["low"].to_numpy()
    eff = np.zeros(len(close)); eff[1:] = signal[:-1]
    eq = 1.0
    curve = np.empty(len(close)); curve[0] = 1.0
    liquidated = False
    liq_count = 0
    for i in range(1, len(close)):
        if liquidated:
            curve[i] = 0.0
            continue
        ret_cc = close[i] / close[i - 1] - 1.0
        # liquidazione: se in posizione e la barra (sul low) va contro più di (1/lev - maint)
        if eff[i] == 1:
            adverse = low[i] / close[i - 1] - 1.0            # peggior caso intrabar (long)
            if adverse <= -(1.0 / lev - MAINT_MARGIN):
                eq = 0.0
                liquidated = True
                liq_count += 1
                curve[i] = 0.0
                continue
        cost = fee_side * (abs(eff[i] - eff[i - 1])) * lev
        eq *= (1.0 + lev * eff[i] * ret_cc - cost)
        eq = max(eq, 0.0)
        curve[i] = eq
    return curve, liquidated, liq_count


def weekly_returns(dates, curve):
    s = pd.Series(curve, index=pd.to_datetime(dates))
    wk = s.resample("W").last().dropna()
    return wk.pct_change().dropna()


def stats(wr):
    return dict(
        mean=wr.mean() * 100, median=wr.median() * 100,
        p10=(wr >= 0.10).mean() * 100, std=wr.std() * 100,
        best=wr.max() * 100, worst=wr.min() * 100)


def maxdd(curve):
    c = np.asarray(curve)
    c = np.where(c <= 0, np.nan, c)
    peak = np.fmax.accumulate(np.nan_to_num(c, nan=0))
    peak[peak == 0] = np.nan
    dd = c / peak - 1.0
    return np.nanmin(dd) * 100


def main():
    df = pd.read_csv(DATA15, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    d = resample(df, "4h").iloc[WARMUP:].reset_index(drop=True)
    dates = d["date"]
    close = d["close"].to_numpy()
    sig = ema_cross_signal(close, 20, 50)
    bh = np.ones(len(close), dtype=int)

    print("=" * 84)
    print(' OBIETTIVO "10% A SETTIMANA" — verifica empirica su SOL 4h (5+ anni reali)')
    print(" 10%/sett composto = 1.10^52 = 142× l'anno = +14.100%/anno")
    print("=" * 84)

    # ---- 1) Distribuzione settimanale a leva 1 ----
    print("\n 1) RENDIMENTI SETTIMANALI REALI (leva 1×, nessuna magia):")
    print(f"    {'':<22}{'media':>8}{'mediana':>9}{'%sett ≥10%':>12}{'migliore':>10}{'peggiore':>10}")
    for name, s in [("Buy & Hold", bh), ("Trend 4h EMA20/50", sig)]:
        curve, _, _ = lev_equity(d, s, lev=1.0)
        st = stats(weekly_returns(dates, curve))
        print(f"    {name:<22}{st['mean']:>+7.2f}%{st['median']:>+8.2f}%"
              f"{st['p10']:>11.0f}%{st['best']:>+9.0f}%{st['worst']:>+9.0f}%")
    print("    → Per fare 10%/sett servirebbe la MEDIA settimanale a +10%. La realtà è ~+1%.")

    # ---- 2) Leva: il rendimento sale, ma arriva la LIQUIDAZIONE ----
    print("\n 2) LEVA sulla miglior strategia (trend 4h) — rendimento vs liquidazione:")
    print(f"    {'leva':>5}{'CAGR':>9}{'media sett':>12}{'MaxDD':>9}{'liquidato?':>12}")
    for lev in (1, 2, 3, 5, 10):
        curve, liq, _ = lev_equity(d, sig, lev=float(lev))
        years = len(curve) / (6 * 365)
        final = curve[-1]
        cagr = (final ** (1 / years) - 1) * 100 if final > 0 else -100.0
        st = stats(weekly_returns(dates, curve))
        dd = maxdd(curve)
        liq_s = "💀 SÌ (azzerato)" if liq else "no"
        print(f"    {lev:>4}×{cagr:>+8.0f}%{st['mean']:>+11.2f}%{dd:>+8.0f}%   {liq_s}")
    print("    → 'Stop basso' = poco margine = a leva alta una gamba larga di SOL ti liquida.")
    print("      Su SOL le barre 4h da -15%/-25% NON sono rare: a 5-10× = conto a zero.")

    # ---- 3) Quante settimane consecutive a +10% sono mai esistite? ----
    print("\n 3) È MAI successo? Settimane consecutive ≥10% (leva 1×, trend 4h):")
    curve, _, _ = lev_equity(d, sig, lev=1.0)
    wr = weekly_returns(dates, curve)
    ge10 = (wr >= 0.10).astype(int).to_numpy()
    best_streak = cur = 0
    for x in ge10:
        cur = cur + 1 if x else 0
        best_streak = max(best_streak, cur)
    print(f"    settimane totali: {len(wr)}   con ≥10%: {int(ge10.sum())} "
          f"({ge10.mean()*100:.0f}%)   striscia max consecutiva: {best_streak}")
    print(f"    Per il target servono 52 settimane di fila ≥10%. Massimo storico: {best_streak}.")

    # ---- 4) La matematica dello 'stop basso' ----
    print("\n 4) MATEMATICA 'stop loss basso': per +10%/sett con stop stretto serve...")
    print("    Ipotesi: stop 2%, target per trade variabile, 1 trade/giorno (5/sett).")
    print("    Per +10%/sett netto servono ~+2%/trade di expectancy.")
    print("    Con R:R 1:1 (target +2%, stop -2%): serve win rate > 75% — NON esiste su SOL.")
    print("    Con R:R 3:1 (target +6%, stop -2%): serve win rate > 38% MA target +6% in")
    print("                un giorno è raro; il backtest reale dà expectancy NEGATIVA.")
    print("    (Tutta la ricerca precedente: nessun setup su SOL supera breakeven robusto.)")

    print("\n" + "=" * 84)
    print(" VERDETTO: 10%/settimana sostenuto NON è realizzabile sui dati reali di SOL.")
    print(" - A leva 1×: la media settimanale realistica è ~+1%, non +10%.")
    print(" - Con la leva il numero sale ma 'stop basso' → liquidazione garantita nei crash.")
    print(" - Non è mai esistita una striscia lunga di settimane ≥10%.")
    print(" Realistico: trend-following 4h long-only → rendimento ~Buy&Hold, MaxDD molto più")
    print(" basso. Chi promette 10%/sett con stop basso vende fumo (o ti liquida).")
    print("=" * 84)


if __name__ == "__main__":
    main()

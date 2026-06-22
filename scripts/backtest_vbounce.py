#!/usr/bin/env python3
"""
Backtest FEDELE della strategia V-Bounce (EnsembleRegimeStrategy) su dati SOL reali.

Scopo: dare NUMERI VERI invece di giudicare "a occhio" sul grafico — la raccomandazione
#1 emersa dalla ricerca (evitare il curve-fitting / data-snooping).

Dati: user_data/data_sources/SOL_USDT-1h.csv (5.5 anni, 2021-2026).
ATTENZIONE: i dati cache sono a 1h, il bot live gira a 15m. Questo NON è una replica
esatta del live, ma una VALIDAZIONE DELLA LOGICA su dati reali e su molti regimi
(bull 2021, bear 2022, range 2023, 2024-26). I parametri sono in CANDELE, identici al
live; su 1h ogni candela vale 4× il tempo del 15m (caveat dichiarato).

Nessun lookahead: segnale alla chiusura della candela i, ingresso all'OPEN della i+1.
In ogni candela lo stop viene controllato PRIMA del take-profit (ipotesi pessimista).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research"))
from indicators import ema, rsi, atr, adx, bollinger, efficiency_ratio  # noqa: E402

DATA = ROOT / "user_data" / "data_sources" / "SOL_USDT-1h.csv"

# ===== parametri IDENTICI alla strategia live =====
ADX_TREND = 15.0
ER_TREND = 0.20
ER_WINDOW = 96
CHANDELIER = 3.0          # stop = max_rate - 3*ATR
DIP_RSI = 40.0
TREND_PULL_RSI = 50.0
RSI_LO_EXIT = 35.0
RSI_HI = 65.0
ENOUGH_ROOM = 0.008
BB_TOL = 0.995
COOLDOWN = 12
ROI_BARS = 2             # 120 min su 1h = 2 candele
ROI_PROFIT = 0.005
BULL_RSI_EXIT = 78.0


def build(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["ema50"] = ema(d["close"], 50)
    d["ema200"] = ema(d["close"], 200)
    d["rsi"] = rsi(d["close"], 14)
    d["atr"] = atr(d, 14)
    d["adx"] = adx(d, 14)
    d["er"] = efficiency_ratio(d["close"], ER_WINDOW)
    d["bb_low"], d["bb_mid"], d["bb_up"] = bollinger(d["close"], 20, 2.0)

    is_trend = (d["adx"] > ADX_TREND) & (d["er"] > ER_TREND)
    d["regime"] = 0
    d.loc[is_trend & (d["ema50"] > d["ema200"]) & (d["close"] > d["ema200"]), "regime"] = 1
    d.loc[is_trend & (d["ema50"] < d["ema200"]) & (d["close"] < d["ema200"]), "regime"] = -1

    turning_up = (d["close"] > d["open"]) & (d["rsi"] > d["rsi"].shift(1)) & (d["volume"] > 0)
    just_had_dip = (d["rsi"].shift(1) < DIP_RSI) | (d["low"].shift(1) < d["bb_low"])
    enough_room = (d["bb_up"] - d["close"]) / d["close"] > ENOUGH_ROOM
    bb_not_falling = d["bb_mid"] >= d["bb_mid"].shift(5) * BB_TOL

    dip_bounce = (d["regime"] != -1) & just_had_dip & enough_room & bb_not_falling & turning_up
    trend_pullback = ((d["regime"] == 1) & (d["close"] < d["bb_mid"])
                      & (d["rsi"] < TREND_PULL_RSI) & (d["rsi"] > RSI_LO_EXIT)
                      & enough_room & turning_up)
    d["enter"] = (dip_bounce | trend_pullback).astype(int)
    d["enter_tag"] = np.where(trend_pullback & ~dip_bounce, "trend_pull", "dip_bounce")
    return d


def backtest(d: pd.DataFrame, fee_side: float, bull_trail_atr: float, label: str,
             stop_mult: float = CHANDELIER, use_roi: bool = True, range_tp_min: float = 0.003,
             allowed_regimes=(-1, 0, 1), er_max: float = 1.0):
    """Simula 1 posizione alla volta, long-only. fee_side = costo per lato (fee+slippage).
    stop_mult: ampiezza stop (×ATR). use_roi: attiva il take-profit fisso veloce.
    range_tp_min: profitto minimo per uscire alla banda in range.
    allowed_regimes/er_max: filtra in quali regimi/volatilità si può entrare."""
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    trades = []
    i = 1
    n = len(d)
    cooldown_until = 0

    while i < n - 1:
        row = d.iloc[i]
        if (row["enter"] != 1 or i < cooldown_until or not np.isfinite(row["atr"]) or row["atr"] <= 0
                or int(row["regime"]) not in allowed_regimes or row["er"] > er_max):
            i += 1
            continue
        # ingresso all'OPEN della candela successiva (no lookahead)
        entry = d.iloc[i + 1]["open"]
        entry *= (1 + fee_side)                       # costo d'ingresso
        max_rate = entry
        bars = 0
        exit_price = None
        reason = None
        j = i + 1
        while j < n:
            c = d.iloc[j]
            atr_j = c["atr"] if np.isfinite(c["atr"]) and c["atr"] > 0 else 0.0
            max_rate = max(max_rate, c["high"])
            bars += 1
            stop_price = max_rate - stop_mult * atr_j
            # 1) STOP per primo (pessimista)
            if atr_j > 0 and c["low"] <= stop_price:
                exit_price = stop_price
                reason = "stop"
                break
            prof_high = (c["high"] - entry) / entry
            # 2) TAKE-PROFIT adattivo
            if c["regime"] == 1:
                trail = max_rate - bull_trail_atr * atr_j
                if prof_high >= 0.010 and c["low"] <= trail and atr_j > 0:
                    exit_price = trail
                    reason = "trail_bull"
                    break
                if c["rsi"] > BULL_RSI_EXIT:
                    exit_price = c["close"]
                    reason = "rsi_bull"
                    break
            else:
                if c["high"] >= c["bb_up"] and (c["bb_up"] - entry) / entry >= range_tp_min:
                    exit_price = c["bb_up"]
                    reason = "tp_band"
                    break
                if c["rsi"] > RSI_HI and (c["close"] - entry) / entry >= range_tp_min:
                    exit_price = c["close"]
                    reason = "tp_rsi"
                    break
            # 3) ROI fallback (opzionale)
            if use_roi and bars >= ROI_BARS and (c["close"] - entry) / entry >= ROI_PROFIT:
                exit_price = c["close"]
                reason = "roi"
                break
            # 4) uscita a segnale (regime -1) solo se in profitto (exit_profit_only)
            if c["regime"] == -1 and (c["close"] - entry) / entry > 0:
                exit_price = c["close"]
                reason = "signal_bear"
                break
            j += 1
        if exit_price is None:                        # trade ancora aperto a fine dati
            break
        exit_price *= (1 - fee_side)                  # costo d'uscita
        ret = (exit_price - entry) / entry
        equity *= (1 + ret)
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1)
        trades.append({"ret": ret, "bars": bars, "reason": reason,
                       "tag": row["enter_tag"], "regime": int(row["regime"]),
                       "date": row["date"]})
        cooldown_until = j + COOLDOWN
        i = j + 1

    t = pd.DataFrame(trades)
    if len(t) == 0:
        return {"label": label, "n": 0, "pf": float("nan"), "exp": float("nan"),
                "ret": float("nan"), "dd": float("nan"), "wr": float("nan")}
    wins = t[t["ret"] > 0]
    losses = t[t["ret"] <= 0]
    pf = wins["ret"].sum() / abs(losses["ret"].sum()) if len(losses) and losses["ret"].sum() != 0 else float("inf")
    bh = d.iloc[-1]["close"] / d.iloc[1]["open"] - 1
    m = {"label": label, "n": len(t), "wr": len(wins) / len(t) * 100,
         "avgw": wins["ret"].mean() * 100, "avgl": losses["ret"].mean() * 100 if len(losses) else 0.0,
         "pf": pf, "exp": t["ret"].mean() * 100, "ret": (equity - 1) * 100,
         "dd": max_dd * 100, "bh": bh * 100, "reasons": dict(t["reason"].value_counts())}
    return m


def show(m):
    if m["n"] == 0:
        print(f"  {m['label']:42}  NESSUN TRADE")
        return
    print(f"\n========== {m['label']} ==========")
    print(f"  Trade: {m['n']:4d}   Win rate: {m['wr']:5.1f}%   "
          f"Avg win {m['avgw']:+.2f}% / Avg loss {m['avgl']:+.2f}%")
    print(f"  Profit factor: {m['pf']:.2f}   Expectancy: {m['exp']:+.2f}%/trade   "
          f"Rendimento: {m['ret']:+.1f}%   MaxDD: {m['dd']:.1f}%   B&H: {m['bh']:+.1f}%")
    print(f"  Uscite: {m['reasons']}")


def main():
    df = pd.read_csv(DATA, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    d = build(df)
    d = d.iloc[700:].reset_index(drop=True)           # startup_candle_count
    split = pd.Timestamp("2024-06-01", tz="UTC")
    ins = d[d["date"] < split].reset_index(drop=True)
    oos = d[d["date"] >= split].reset_index(drop=True)
    FEE = 0.0006                                       # 0.06%/lato (fee+slippage realistico)

    print("#" * 70)
    print("# BACKTEST V-BOUNCE su SOL 1h reale (2021-2026, 47k candele)")
    print("# Caveat: dati 1h (live=15m). Valida la LOGICA su molti regimi, non il live.")
    print("#" * 70)

    print("\n### 1) CONFIGURAZIONE ATTUALE (stop 3xATR, ROI rapido, TP 1%)")
    show(backtest(d,   FEE, 3.0, "ATTUALE  tutto 2021-2026"))
    show(backtest(oos, FEE, 3.0, "ATTUALE  out-of-sample 2024-26"))

    print("\n" + "=" * 70)
    print("### 2) IPOTESI: lo stop è troppo largo? Sweep stop ×ATR (IS vs OOS)")
    print(f"{'stop×ATR':>9} | {'IS pf':>6} {'IS exp':>7} | {'OOS pf':>6} {'OOS exp':>7} {'OOS ret':>8}")
    for sm in (1.0, 1.5, 2.0, 2.5, 3.0):
        a = backtest(ins, FEE, 3.0, "", stop_mult=sm)
        b = backtest(oos, FEE, 3.0, "", stop_mult=sm)
        print(f"{sm:9.1f} | {a['pf']:6.2f} {a['exp']:+6.2f}% | {b['pf']:6.2f} {b['exp']:+6.2f}% {b['ret']:+7.1f}%")

    print("\n" + "=" * 70)
    print("### 3) IPOTESI: lasciar CORRERE i vincitori (no ROI rapido)  [stop 2xATR]")
    print(f"{'variante':>22} | {'IS pf':>6} {'IS exp':>7} | {'OOS pf':>6} {'OOS exp':>7} {'OOS ret':>8}")
    for name, roi, sm in [("con ROI rapido", True, 2.0), ("SENZA ROI (lascia correre)", False, 2.0)]:
        a = backtest(ins, FEE, 3.0, "", stop_mult=sm, use_roi=roi)
        b = backtest(oos, FEE, 3.0, "", stop_mult=sm, use_roi=roi)
        print(f"{name:>22} | {a['pf']:6.2f} {a['exp']:+6.2f}% | {b['pf']:6.2f} {b['exp']:+6.2f}% {b['ret']:+7.1f}%")

    print("\n" + "=" * 70)
    print("### 4) IPOTESI-CHIAVE (ricerca): la MR funziona solo in RANGE, muore nei trend?")
    print(f"{'filtro ingressi':>26} | {'IS pf':>6} {'IS exp':>7} | {'OOS pf':>6} {'OOS exp':>7} {'OOS ret':>8}")
    tests = [
        ("tutti i regimi", dict()),
        ("solo RANGE (regime 0)", dict(allowed_regimes=(0,))),
        ("RANGE + ER basso <0.30", dict(allowed_regimes=(0,), er_max=0.30)),
        ("RANGE + ER molto basso <0.20", dict(allowed_regimes=(0,), er_max=0.20)),
    ]
    for name, kw in tests:
        a = backtest(ins, FEE, 3.0, "", **kw)
        b = backtest(oos, FEE, 3.0, "", **kw)
        print(f"{name:>26} | {a['pf']:6.2f} {a['exp']:+6.2f}% | {b['pf']:6.2f} {b['exp']:+6.2f}% {b['ret']:+7.1f}%")

    print("\nNB: nessun parametro è stato 'ottimizzato per vincere'. Una variante che è")
    print("    positiva IN-SAMPLE ma NEGATIVA out-of-sample = fortuna/overfit, non edge.")


if __name__ == "__main__":
    main()

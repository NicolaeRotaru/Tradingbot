#!/usr/bin/env python3
"""
Strategie a COMMUTAZIONE DI REGIME (il cuore del potenziamento).

Idea (esattamente cio' che chiede l'obiettivo):
  - Mercato che SALE con forza  -> modulo TREND-LONG (cavalca, tiene fino in fondo)
  - Mercato che SCENDE con forza -> modulo TREND-SHORT
  - Mercato PIATTO / laterale    -> modulo MEAN-REVERSION long+short (compra basso, vende alto)

Un classificatore di regime (ADX + Efficiency Ratio + EMA) decide quale modulo e'
attivo. Una sola posizione per asset alla volta (realistico per un conto singolo).

Convenzione anti-lookahead: il segnale alla barra i usa SOLO dati fino a i; la
posizione viene poi tenuta nella barra i+1 (lo shift lo applica il motore).

Ritorna, per ogni barra:
  pos   : posizione base in {-1, 0, +1}
  mode  : 0=flat, 1=trend, 2=mean-reversion   (per attribuzione del PnL)
  regime: -1=trend-down, 0=range, +1=trend-up  (per i grafici)
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

WU = 400  # warmup (EMA400)


@dataclass
class Params:
    # --- regime detection ---
    adx_trend: float = 22.0       # ADX sopra il quale e' "trend"
    er_trend: float = 0.30        # Efficiency Ratio sopra il quale e' "trend"
    use_macro: bool = False       # se True, long solo se close>EMA400, short se close<EMA400
    # --- modulo TREND ---
    chand_long: float = 5.0       # Chandelier exit long = peak - chand_long*ATR
    chand_short: float = 3.5      # Chandelier exit short = trough + chand_short*ATR
    # --- modulo MEAN-REVERSION (range) ---
    mr_rsi_lo: float = 32.0       # entra long se RSI < soglia (ipervenduto)
    mr_rsi_hi: float = 68.0       # entra short se RSI > soglia (ipercomprato)
    mr_exit_lo: float = 45.0      # esci dallo short quando RSI rientra sotto
    mr_exit_hi: float = 55.0      # esci dal long quando RSI rientra sopra
    mr_stop: float = 0.06         # hard stop del trade mean-reversion (frazione)
    mr_trend_filter: bool = True  # MR-long solo sopra EMA200, MR-short solo sotto (dip-buy/rip-sell)
    short_macro: bool = True      # TREND-short solo se anche close<EMA400 (downtrend confermato)
    # --- abilitazioni ---
    allow_short: bool = True
    allow_mr: bool = True
    allow_trend: bool = True


def classify_regime(df: pd.DataFrame, p: Params) -> np.ndarray:
    """Regime per barra: +1 trend-up, -1 trend-down, 0 range."""
    adx = df["adx"].to_numpy()
    er = df["er"].to_numpy()
    e50 = df["ema50"].to_numpy()
    e200 = df["ema200"].to_numpy()
    c = df["close"].to_numpy()
    n = len(df)
    reg = np.zeros(n, dtype=int)
    is_trend = (adx > p.adx_trend) & (er > p.er_trend)
    up = is_trend & (e50 > e200) & (c > e200)
    dn = is_trend & (e50 < e200) & (c < e200)
    reg[up] = 1
    reg[dn] = -1
    return reg


def generate(df: pd.DataFrame, p: Params):
    """Macchina a stati: una posizione per volta, modulo scelto dal regime."""
    c = df["close"].to_numpy()
    e200 = df["ema200"].to_numpy()
    e400 = df["ema400"].to_numpy()
    atr = df["atr"].to_numpy()
    rsi = df["rsi"].to_numpy()
    bb_low = df["bb_low"].to_numpy()
    bb_mid = df["bb_mid"].to_numpy()
    bb_up = df["bb_up"].to_numpy()
    reg = classify_regime(df, p)
    n = len(df)

    pos = np.zeros(n)
    mode = np.zeros(n, dtype=int)   # 1=trend, 2=mr
    state = 0                       # -1/0/+1
    cur_mode = 0
    peak = trough = entry = 0.0

    for i in range(n):
        if i < WU or np.isnan(e400[i]) or np.isnan(atr[i]) or np.isnan(bb_low[i]):
            continue

        macro_long_ok = (not p.use_macro) or (c[i] > e400[i])
        macro_short_ok = (not p.use_macro) or (c[i] < e400[i])

        # filtri di trend per la mean-reversion: compra i ribassi SOPRA EMA200,
        # vendi i rialzi SOTTO EMA200 (molto piu' robusto del contro-trend puro)
        mr_long_ok = (not p.mr_trend_filter) or (c[i] > e200[i])
        mr_short_ok = (not p.mr_trend_filter) or (c[i] < e200[i])
        # short di trend solo in downtrend MACRO confermato (close<EMA400)
        short_trend_ok = (not p.short_macro) or (c[i] < e400[i])

        if state == 0:
            # --- apertura: priorita' al TREND, poi MEAN-REVERSION ---
            if p.allow_trend and reg[i] == 1 and macro_long_ok:
                state, cur_mode, peak = 1, 1, c[i]
            elif p.allow_trend and p.allow_short and reg[i] == -1 and macro_short_ok and short_trend_ok:
                state, cur_mode, trough = -1, 1, c[i]
            elif p.allow_mr and reg[i] == 0:
                if c[i] < bb_low[i] and rsi[i] < p.mr_rsi_lo and macro_long_ok and mr_long_ok:
                    state, cur_mode, entry = 1, 2, c[i]
                elif (p.allow_short and c[i] > bb_up[i] and rsi[i] > p.mr_rsi_hi
                      and macro_short_ok and mr_short_ok):
                    state, cur_mode, entry = -1, 2, c[i]

        elif state == 1 and cur_mode == 1:        # TREND LONG
            peak = max(peak, c[i])
            if c[i] < e200[i] or c[i] < peak - p.chand_long * atr[i]:
                state, cur_mode = 0, 0

        elif state == -1 and cur_mode == 1:       # TREND SHORT
            trough = min(trough, c[i])
            if c[i] > e200[i] or c[i] > trough + p.chand_short * atr[i]:
                state, cur_mode = 0, 0

        elif state == 1 and cur_mode == 2:        # MEAN-REVERSION LONG
            if (c[i] >= bb_mid[i] or rsi[i] > p.mr_exit_hi
                    or c[i] < entry * (1 - p.mr_stop) or reg[i] == -1):
                state, cur_mode = 0, 0

        elif state == -1 and cur_mode == 2:       # MEAN-REVERSION SHORT
            if (c[i] <= bb_mid[i] or rsi[i] < p.mr_exit_lo
                    or c[i] > entry * (1 + p.mr_stop) or reg[i] == 1):
                state, cur_mode = 0, 0

        pos[i] = state
        mode[i] = cur_mode

    return pos, mode, reg


# ---- varianti pronte per il confronto ----
def variant_params(name: str) -> Params:
    if name == "trend_long_only":
        return Params(allow_short=False, allow_mr=False)
    if name == "trend_ls":
        return Params(allow_short=True, allow_mr=False)
    if name == "mr_only":
        return Params(allow_trend=False, allow_mr=True, allow_short=True)
    if name == "ensemble_long":
        return Params(allow_short=False, allow_mr=True, allow_trend=True)
    if name == "ensemble_full":
        return Params(allow_short=True, allow_mr=True, allow_trend=True)
    raise ValueError(name)

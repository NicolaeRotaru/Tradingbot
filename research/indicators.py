#!/usr/bin/env python3
"""
Indicatori tecnici in pandas/numpy PURO (nessuna dipendenza da TA-Lib).

Usati da tutto il motore di ricerca `research/`. Implementazioni standard:
- EMA: smoothing esponenziale (alpha = 2/(n+1))
- RSI / ATR / ADX: smoothing di Wilder (alpha = 1/n) come da definizione classica
- Bollinger / Donchian: bande per il modulo mean-reversion
- realized_vol: volatilita' realizzata annualizzata (per il vol-targeting)
- efficiency_ratio (Kaufman): "trendiness" 0..1 per la regime detection

Nessun lookahead: ogni indicatore alla barra i usa solo dati fino a i.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

BARS_YEAR = 24 * 365  # candele orarie in un anno (per annualizzare)


def ema(series: pd.Series, n: int) -> pd.Series:
    return series.ewm(span=n, adjust=False).mean()


def sma(series: pd.Series, n: int) -> pd.Series:
    return series.rolling(n).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    """RSI con smoothing di Wilder."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1.0 / n, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / n, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - 100.0 / (1.0 + rs)
    return out.fillna(100.0)  # loss=0 -> RSI 100


def true_range(df: pd.DataFrame) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """Average True Range (Wilder)."""
    return true_range(df).ewm(alpha=1.0 / n, adjust=False).mean()


def adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """Average Directional Index (Wilder). Misura la FORZA del trend (non la direzione)."""
    high, low = df["high"], df["low"]
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    plus_dm = pd.Series(plus_dm, index=df.index)
    minus_dm = pd.Series(minus_dm, index=df.index)

    tr = true_range(df)
    atr_w = tr.ewm(alpha=1.0 / n, adjust=False).mean()
    plus_di = 100.0 * plus_dm.ewm(alpha=1.0 / n, adjust=False).mean() / atr_w.replace(0.0, np.nan)
    minus_di = 100.0 * minus_dm.ewm(alpha=1.0 / n, adjust=False).mean() / atr_w.replace(0.0, np.nan)
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    return dx.ewm(alpha=1.0 / n, adjust=False).mean().fillna(0.0)


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0):
    mid = close.rolling(n).mean()
    std = close.rolling(n).std(ddof=0)
    return mid - k * std, mid, mid + k * std


def donchian(df: pd.DataFrame, n: int = 20):
    lower = df["low"].rolling(n).min()
    upper = df["high"].rolling(n).max()
    mid = (upper + lower) / 2.0
    return lower, mid, upper


def realized_vol(close: pd.Series, n: int = 72) -> pd.Series:
    """Volatilita' realizzata ANNUALIZZATA su finestra n (default 3 giorni di candele 1h)."""
    logret = np.log(close / close.shift(1))
    return logret.rolling(n).std(ddof=0) * np.sqrt(BARS_YEAR)


def efficiency_ratio(close: pd.Series, n: int = 24) -> pd.Series:
    """Kaufman Efficiency Ratio: |variazione netta| / somma |variazioni|.
    ~1 = trend pulito, ~0 = mercato choppy/laterale. Ottimo per la regime detection."""
    change = (close - close.shift(n)).abs()
    volatility = close.diff().abs().rolling(n).sum()
    return (change / volatility.replace(0.0, np.nan)).fillna(0.0)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Aggiunge l'intero set di indicatori usato dalle strategie. Idempotente."""
    out = df.copy()
    for p in (50, 200, 400):
        out[f"ema{p}"] = ema(out["close"], p)
    out["rsi"] = rsi(out["close"], 14)
    out["atr"] = atr(out, 14)
    out["adx"] = adx(out, 14)
    out["er"] = efficiency_ratio(out["close"], 24)
    out["bb_low"], out["bb_mid"], out["bb_up"] = bollinger(out["close"], 20, 2.0)
    out["rvol"] = realized_vol(out["close"], 72)
    out["mom24"] = out["close"] - out["close"].shift(24)
    return out

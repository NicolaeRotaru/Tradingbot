#!/usr/bin/env python3
"""
Motore di backtest onesto + overlay di RISCHIO (le "leve gratis" della v2).

Pipeline:
  posizione base {-1,0,+1}  ->  peso target (vol-targeting * Kelly * confidenza ML)
                            ->  equity con drawdown-throttle (path-dependent)
                            ->  metriche corrette per il rischio

Costi realistici applicati a ogni variazione di peso (fee + slippage).
Niente lookahead: il peso deciso alla barra i agisce sul rendimento i->i+1
(shift gestito internamente); il throttle legge solo l'equity passata.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

BARS_YEAR = 24 * 365


@dataclass
class RiskConfig:
    target_vol: float = 0.60      # vol annua bersaglio del portafoglio (crypto e' volatile)
    max_leverage: float = 1.0     # 1.0 = nessuna leva (spot). >1 solo su futures.
    kelly_frac: float = 1.0       # frazione di Kelly globale (1.0 = peso pieno)
    dd_throttle: float = 0.25     # a questo drawdown il peso e' azzerato (linearmente)
    cost: float = 0.0010          # 0.06% fee + 0.04% slippage per lato (futures realistico)
    vol_floor: float = 0.20       # vol minima per evitare size esplosive in mercati calmi


def vol_target_weight(rvol: np.ndarray, base: np.ndarray, rc: RiskConfig) -> np.ndarray:
    """Peso target = direzione * (vol_bersaglio / vol_realizzata), limitato dalla leva max."""
    rv = np.where(np.isnan(rvol) | (rvol < rc.vol_floor), rc.vol_floor, rvol)
    size = rc.target_vol / rv
    size = np.clip(size, 0.0, rc.max_leverage) * rc.kelly_frac
    return base * size


def simulate(df: pd.DataFrame, base_pos: np.ndarray, rc: RiskConfig,
             conf: np.ndarray | None = None, start: int = 400):
    """Esegue la simulazione con sizing + drawdown-throttle. Ritorna dict di risultati."""
    c = df["close"].to_numpy()
    rvol = df["rvol"].to_numpy()
    n = len(df)

    w_target = vol_target_weight(rvol, base_pos, rc)
    if conf is not None:                       # confidenza ML (0..1) come moltiplicatore di size
        w_target = w_target * conf

    equity = np.ones(n)
    peak = 1.0
    ep_prev = 0.0
    ret_step = np.zeros(n)
    w_eff = np.zeros(n)

    for i in range(1, n):
        if i <= start:
            equity[i] = 1.0
            continue
        dd = equity[i - 1] / peak - 1.0
        throttle = np.clip(1.0 + dd / rc.dd_throttle, 0.0, 1.0)  # dd=0 ->1 ; dd=-throttle ->0
        ep = w_target[i - 1] * throttle                         # peso tenuto nella barra i
        ret_i = c[i] / c[i - 1] - 1.0
        turn = abs(ep - ep_prev)
        step = ep * ret_i - turn * rc.cost
        equity[i] = equity[i - 1] * (1.0 + step)
        peak = max(peak, equity[i])
        ret_step[i] = step
        w_eff[i] = ep
        ep_prev = ep

    eq = pd.Series(equity, index=df["date"].values)
    return dict(equity=eq, ret_step=ret_step, w_eff=w_eff, start=start)


# --------------------------- METRICHE ---------------------------
def metrics(res: dict, df: pd.DataFrame, lo=None, hi=None, idx=None) -> dict:
    start = res["start"]
    if idx is None:
        dates = pd.to_datetime(df["date"]).dt.tz_localize(None).to_numpy()
        mask = np.ones(len(df), dtype=bool)
        mask[:start + 1] = False
        if lo is not None:
            mask &= dates >= np.datetime64(pd.Timestamp(lo).tz_localize(None))
        if hi is not None:
            mask &= dates < np.datetime64(pd.Timestamp(hi).tz_localize(None))
        idx = np.where(mask)[0]
    else:
        idx = np.asarray(idx)
        idx = idx[idx > start]
    if len(idx) < 10:
        return dict(total=np.nan, cagr=np.nan, dd=np.nan, sharpe=np.nan, sortino=np.nan,
                    calmar=np.nan, trades=0, expo=0.0, winrate=np.nan, pf=np.nan, turnover=np.nan)

    step = pd.Series(res["ret_step"][idx])
    eq = (1.0 + step).cumprod()
    d = pd.to_datetime(df["date"].to_numpy()[idx])
    years = (d[-1] - d[0]).days / 365.25
    total = eq.iloc[-1] - 1.0
    cagr = eq.iloc[-1] ** (1.0 / years) - 1.0 if years > 0 else np.nan

    mu, sd = step.mean(), step.std(ddof=0)
    sharpe = mu / sd * np.sqrt(BARS_YEAR) if sd > 0 else np.nan
    downside = step[step < 0].std(ddof=0)
    sortino = mu / downside * np.sqrt(BARS_YEAR) if downside > 0 else np.nan
    dd_curve = eq / eq.cummax() - 1.0
    maxdd = dd_curve.min()
    calmar = cagr / abs(maxdd) if maxdd < 0 else np.nan

    w = res["w_eff"][idx]
    w_prev = np.concatenate([[0.0], w[:-1]])
    entries = int(((w_prev == 0) & (w != 0)).sum())
    expo = float((w != 0).mean())
    turnover = float(np.abs(np.diff(w, prepend=0.0)).sum())

    # win-rate / profit-factor a livello di barra esposta (proxy robusto)
    exposed = step[w != 0]
    wins = exposed[exposed > 0].sum()
    losses = -exposed[exposed < 0].sum()
    pf = wins / losses if losses > 0 else np.nan
    winrate = float((exposed > 0).mean()) if len(exposed) else np.nan
    time_in_dd = float((dd_curve < -0.05).mean())

    return dict(total=total, cagr=cagr, dd=maxdd, sharpe=sharpe, sortino=sortino,
                calmar=calmar, trades=entries, expo=expo, winrate=winrate, pf=pf,
                turnover=turnover, time_in_dd=time_in_dd, eq=pd.Series(eq.to_numpy(), index=d))


def buy_hold(df: pd.DataFrame, start: int = 400):
    """Equity buy&hold (sempre long, peso 1, nessun costo di rotazione)."""
    c = df["close"].to_numpy()
    n = len(df)
    ret = np.zeros(n)
    ret[start + 1:] = c[start + 1:] / c[start:-1] - 1.0
    return dict(equity=pd.Series((1 + pd.Series(ret)).cumprod().to_numpy(), index=df["date"].values),
                ret_step=ret, w_eff=np.ones(n), start=start)


# --------------------------- WALK-FORWARD ---------------------------
def walk_forward_splits(df: pd.DataFrame, n_folds: int = 5, embargo: int = 168, start: int = 400):
    """Genera (train_idx, test_idx) walk-forward ancorato, con embargo anti-leakage."""
    n = len(df)
    usable = np.arange(start, n)
    fold_size = len(usable) // (n_folds + 1)
    splits = []
    for k in range(1, n_folds + 1):
        train_end = start + fold_size * k
        test_start = train_end + embargo
        test_end = min(start + fold_size * (k + 1), n)
        if test_start >= test_end:
            continue
        splits.append((np.arange(start, train_end), np.arange(test_start, test_end)))
    return splits


# --------------------------- MONTE CARLO ---------------------------
def monte_carlo(ret_step: np.ndarray, n_paths: int = 1000, block: int = 24, seed: int = 7):
    """Block-bootstrap dei rendimenti per stimare la distribuzione del drawdown/equity finale."""
    rng = np.random.default_rng(seed)
    r = ret_step[ret_step != 0.0]
    if len(r) < block * 4:
        return None
    n = len(r)
    finals, dds = [], []
    n_blocks = n // block
    for _ in range(n_paths):
        starts = rng.integers(0, n - block, size=n_blocks)
        path = np.concatenate([r[s:s + block] for s in starts])
        eq = np.cumprod(1.0 + path)
        finals.append(eq[-1] - 1.0)
        dds.append((eq / np.maximum.accumulate(eq) - 1.0).min())
    finals, dds = np.array(finals), np.array(dds)
    return dict(
        final_p5=np.percentile(finals, 5), final_p50=np.percentile(finals, 50),
        final_p95=np.percentile(finals, 95),
        dd_p50=np.percentile(dds, 50),
        dd_worst5=np.percentile(dds, 5),   # coda peggiore (5% dei casi piu' brutti)
        prob_profit=float((finals > 0).mean()),
    )


# --------------------------- PROBABILISTIC SHARPE ---------------------------
def probabilistic_sharpe(sharpe_ann: float, n_obs: int,
                         skew: float = 0.0, kurt: float = 3.0, sr0_ann: float = 0.0) -> float:
    """PSR (Bailey & Lopez de Prado): probabilita' che lo Sharpe VERO sia > sr0.
    Tiene conto di numerosita' campionaria, asimmetria e code grasse dei rendimenti.
    Input in unita' ANNUALIZZATE; convertito internamente a per-osservazione."""
    from math import erf, sqrt
    if n_obs < 10 or not np.isfinite(sharpe_ann):
        return np.nan
    sr = sharpe_ann / sqrt(BARS_YEAR)        # de-annualizza
    sr0 = sr0_ann / sqrt(BARS_YEAR)
    denom = sqrt(max(1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr * sr, 1e-9))
    z = (sr - sr0) * sqrt(n_obs - 1) / denom
    return 0.5 * (1.0 + erf(z / sqrt(2)))

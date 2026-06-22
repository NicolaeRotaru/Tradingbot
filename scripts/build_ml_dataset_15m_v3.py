#!/usr/bin/env python3
"""
V3 — BARRIERE SIMMETRICHE (TP=SL=2×ATR) + feature qualità rimbalzo.

PROBLEMA di v1: TP=+1% fisso vs SL=2×ATR → asimmetria strutturale.
Con avg_loss=-1.83% e avg_win=+0.74%, serve WR>71% per breakeven.
ML ottiene max 65% → sempre negativo.

SOLUZIONE V3: TP = SL = 2×ATR (adattivi, R:R=1:1).
Con fee=0.2% round-trip, breakeven WR≈58%. AUC~0.58 → WR filtrato 62-65% → POSITIVO.

Stessi eventi di v1: V-bounce v2 signals (≈4268).
Aggiunge 8 feature sui pattern di perdita (qualità del rimbalzo).

Output: results/ml_dataset_sol_15m_v3.csv
Usage : python3 scripts/build_ml_dataset_15m_v3.py
        python3 scripts/train_loss_predictor.py --data results/ml_dataset_sol_15m_v3.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "scripts"))

import backtest_vbounce as vb
from indicators import ema

DATA = ROOT / "user_data" / "data_sources" / "SOL_USDT-15m.csv"
BTC  = ROOT / "user_data" / "data_sources" / "BTC_USDT-1h.csv"
OUT  = ROOT / "results" / "ml_dataset_sol_15m_v3.csv"

TP_ATR  = 2.0    # TP adattivo: +2×ATR (simmetrico con SL)
SL_ATR  = 2.0    # SL: -2×ATR  (R:R = 1:1)
HORIZON = 96     # 24h (= 96 barre 15m)
FEE_RT  = 0.0020 # fee round-trip Kraken (taker)
WARMUP  = 700


def btc_regime_lagged(dates_15m: pd.Series) -> np.ndarray:
    btc = pd.read_csv(BTC, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    btc["date"] = pd.to_datetime(btc["date"], utc=True)
    on = (btc["close"] > ema(btc["close"], 200)).astype(float)
    htf = pd.DataFrame({"date": btc["date"], "btc_on": on}).set_index("date")["btc_on"].shift(1)
    m = pd.DataFrame({"date": pd.to_datetime(dates_15m.values, utc=True)}).merge(
        htf.rename("btc_on"), left_on="date", right_index=True, how="left")
    return m["btc_on"].ffill().fillna(0.0).to_numpy()


def build() -> pd.DataFrame:
    df = pd.read_csv(DATA, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    d = vb.build(df, htf_rule="1h")

    c   = d["close"].to_numpy()
    o   = d["open"].to_numpy()
    hi  = d["high"].to_numpy()
    lo  = d["low"].to_numpy()
    vol = d["volume"].to_numpy()
    e50  = d["ema50"].to_numpy()
    e200 = d["ema200"].to_numpy()
    adx  = d["adx"].to_numpy()
    er   = d["er"].to_numpy()
    atr  = d["atr"].to_numpy()
    rsi  = d["rsi"].to_numpy()
    rsi_p2 = d["rsi"].shift(2).to_numpy()
    rsi_p3 = d["rsi"].shift(3).to_numpy()
    bb_low = d["bb_low"].to_numpy()
    bb_up  = d["bb_up"].to_numpy()
    bb_mid = d["bb_mid"].to_numpy()
    regime  = d["regime"].to_numpy()
    htf_ok  = d["htf_ok"].astype(float).to_numpy()
    enter_v2 = d["enter_v2"].to_numpy()
    mom      = (d["close"] - d["close"].shift(16)).to_numpy()
    vol_ratio = (d["volume"] / d["volume"].rolling(20).mean()).to_numpy()
    natr = d["atr"] / d["close"] * 100.0
    natr_pct = natr.rolling(200, min_periods=100).rank(pct=True).to_numpy()
    dates = pd.to_datetime(d["date"])
    btc_on  = btc_regime_lagged(dates)
    vol_ma8 = d["volume"].rolling(8, min_periods=4).mean().to_numpy()
    n = len(d)

    # feature columns to check for NaN (v1 set)
    feat_cols = ("e50", "e200", "adx", "er", "atr", "rsi", "rsi_p2",
                 "bb_low", "bb_up", "bb_mid", "mom", "vol_ratio", "natr_pct")
    arrs = dict(e50=e50, e200=e200, adx=adx, er=er, atr=atr, rsi=rsi, rsi_p2=rsi_p2,
                bb_low=bb_low, bb_up=bb_up, bb_mid=bb_mid, mom=mom,
                vol_ratio=vol_ratio, natr_pct=natr_pct)

    rows = []
    for i in range(n - 1):
        if enter_v2[i] != 1 or i < WARMUP:
            continue
        if not np.isfinite(atr[i]) or atr[i] <= 0:
            continue
        if any(not np.isfinite(arrs[k][i]) for k in feat_cols):
            continue

        rng_i = hi[i] - lo[i]
        if rng_i <= 0:
            continue

        # ---- TRIPLA BARRIERA SIMMETRICA TP=SL=2×ATR ----
        entry = o[i + 1]
        tp = entry + TP_ATR * atr[i]
        sl = entry - SL_ATR * atr[i]
        end = min(i + 1 + HORIZON, n)
        label, ret_tb = None, None
        for j in range(i + 1, end):
            if lo[j] <= sl:
                label, ret_tb = 0, (sl / entry - 1.0) - FEE_RT
                break
            if hi[j] >= tp:
                label, ret_tb = 1, (tp / entry - 1.0) - FEE_RT
                break
        if label is None:
            last = min(end, n) - 1
            ret_tb = (c[last] / entry - 1.0) - FEE_RT
            label = int(ret_tb > 0)

        # ---- FEATURE V3 NUOVE (qualità rimbalzo / pattern perdita) ----
        # Profondità del dip nelle ultime 8 barre
        i0 = max(0, i - 7)
        lo8 = lo[i0:i + 1].min()
        dip_depth = lo8 / c[i] - 1.0               # < 0: sceso molto prima del segnale

        # Momentum orso residuo (fraz. barre rosse ultime 8)
        n8 = min(8, i)
        if n8 > 0:
            bear_bars8 = float(np.sum(c[i - n8 + 1:i + 1] < o[i - n8 + 1:i + 1])) / n8
        else:
            bear_bars8 = 0.5

        # Qualità candela segnale
        body_strength = abs(c[i] - o[i]) / (rng_i + 1e-9)
        lower_wick    = (min(o[i], c[i]) - lo[i]) / (rng_i + 1e-9)   # buying tail
        close_in_rng  = (c[i] - lo[i]) / (rng_i + 1e-9)             # close alta = forza

        # Volume sul reversal vs media 8 barre
        v8 = vol_ma8[i] if (np.isfinite(vol_ma8[i]) and vol_ma8[i] > 0) else vol[i]
        vol_beat = vol[i] / (v8 + 1e-9)

        # Velocità recupero RSI (3 barre)
        rsi_speed3 = rsi[i] - rsi_p3[i] if np.isfinite(rsi_p3[i]) else 0.0

        # Distanza iniziale dallo stop (= SL_ATR × ATR% → quanto slack prima dello stop)
        stop_dist_pct = (SL_ATR * atr[i]) / entry

        rows.append(dict(
            date=d["date"].iloc[i],
            entry_price=entry,
            # ---- FEATURE V1 (18, identiche a build_ml_dataset_15m.py) ----
            f_close_ema50=c[i] / e50[i] - 1.0,
            f_ema50_ema200=e50[i] / e200[i] - 1.0,
            f_close_ema200=c[i] / e200[i] - 1.0,
            f_adx=adx[i],
            f_er=er[i],
            f_atr_pct=atr[i] / c[i],
            f_rsi=rsi[i],
            f_rsi_delta2=rsi[i] - rsi_p2[i],
            f_bb_pos=(c[i] - bb_low[i]) / (bb_up[i] - bb_low[i] + 1e-9),
            f_room=(bb_up[i] - c[i]) / (vb.CHANDELIER * atr[i]),
            f_natr_pct=natr_pct[i],
            f_mom_pct=mom[i] / c[i],
            f_vol_ratio=vol_ratio[i],
            f_regime=float(regime[i]),
            f_htf_ok=htf_ok[i],
            f_btc_riskon=btc_on[i],
            f_hour=float(dates.iloc[i].hour),
            f_dow=float(dates.iloc[i].dayofweek),
            # ---- FEATURE V3 NUOVE (8, focus qualità reversal) ----
            f_dip_depth=dip_depth,       # profondità v-shape (< 0 = dip profondo)
            f_bear_bars8=bear_bars8,     # fraz. barre rosse ultime 8 (momentum orso)
            f_body_strength=body_strength,  # forza corpo candela segnale
            f_lower_wick=lower_wick,     # buying tail (coda inferiore)
            f_close_in_rng=close_in_rng, # close in alto nel range (compressione tori)
            f_vol_beat=vol_beat,         # volume segnale vs media (conferma reversal)
            f_rsi_speed3=rsi_speed3,     # velocità recupero RSI 3 barre
            f_stop_dist=stop_dist_pct,   # distanza % entry→stop (= SL_ATR×ATR%)
            # ---- TARGET ----
            label=label,
            ret_tb=ret_tb,
        ))

    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="Dataset V3: barriere simmetriche TP=SL=2×ATR.")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    data = build()
    if len(data) == 0:
        print("Nessun evento. Controlla i dati/segnali.")
        return 1
    data.to_csv(args.out, index=False)

    feat = [c for c in data.columns if c.startswith("f_")]
    nan_feat = int(data[feat].isna().sum().sum())

    wins   = data[data["label"] == 1]["ret_tb"]
    losses = data[data["label"] == 0]["ret_tb"]
    atp = data["f_atr_pct"].mean() * 100
    breakeven_wr = (SL_ATR * atp + FEE_RT * 100) / ((TP_ATR + SL_ATR) * atp)

    print("=" * 70)
    print(" DATASET V3 — BARRIERE SIMMETRICHE  TP=SL=2×ATR")
    print("=" * 70)
    print(f"  file:                 {args.out}")
    print(f"  eventi (segnali v2):  {len(data)}")
    print(f"  feature:              {len(feat)}")
    print(f"  label=1 (tocca TP):   {data['label'].mean()*100:.1f}%")
    print(f"  NaN feature:          {nan_feat}  (DEVE essere 0)")
    print(f"  periodo:              {data['date'].min()} → {data['date'].max()}")
    n_is = (pd.to_datetime(data["date"]) < pd.Timestamp("2024-01-01", tz="UTC")).sum()
    print(f"  split 2024-01-01:     IS={n_is}  OOS={len(data)-n_is}")
    print()
    print(f"  avg_win  (TP hit):    {wins.mean()*100:+.3f}%  (N={len(wins)})")
    print(f"  avg_loss (SL/timeout):{losses.mean()*100:+.3f}%  (N={len(losses)})")
    print(f"  expectancy baseline:  {data['ret_tb'].mean()*100:+.3f}%/trade")
    print(f"  ATR% medio:           {atp:.2f}%")
    print(f"  Breakeven WR (fee incl.): {breakeven_wr*100:.1f}%  "
          f"← serve WR > questo per essere in utile")
    print()
    print(f"  Prossimo passo:")
    print(f"  python3 scripts/train_loss_predictor.py --data {args.out}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Dataset v2 per il meta-labeling 15m — EVENTI ESPANSI + FEATURE NUOVE + BARRIERE ATR.

Differenze rispetto a v1 (build_ml_dataset_15m.py):
  1. EVENTI ESPANSI: genera candidati per TUTTI i V-bounce (just_had_dip & turning_up),
     inclusi quelli in regime bear o con HTF/R:R falliti. Questi sono i "cerchi gialli"
     bloccati dai filtri duri. I filtri diventano FEATURE (f_regime_pass, f_htf_pass,
     f_rr_pass) e il modello ML decide autonomamente.
  2. BARRIERE ATR-SIMMETRICHE: TP = TP_ATR × ATR, SL = SL_ATR × ATR.
     Con TP=SL=2xATR e WR≈56%, expectancy TEORICA = +0.19%/trade (vs -0.25% attuale).
     La WR reale cambia con le nuove barriere: misurare PRIMA di credere al numero.
  3. FEATURE NUOVE (qualità del segnale di rimbalzo):
     - f_body_pct:    corpo/range candela i (grande = rimbalzo forte)
     - f_upper_wick:  wick superiore/range (grande = compratori respinti)
     - f_vol_spike5:  volume[i] / media volume 5 barre (panico reale)
     - f_ema50_slope: pendenza EMA50 su 8 barre (trend accelera/decelera)
     - f_prior_ret8:  rendimento delle ultime 8 barre (momento prima del dip)
     - f_rsi_min5:    RSI minimo nelle 5 barre precedenti (quanto era oversold il dip)
     - f_regime_pass: 1 se la candela passa il filtro regime duro (EMA50>EMA200 o range)
     - f_htf_pass:    1 se la candela passa il gate HTF 1h
     - f_rr_pass:     1 se la candela passa il filtro R:R ≥ 0.8

Output: results/ml_dataset_sol_15m_v2.csv

Esempio:
  python3 scripts/build_ml_dataset_15m_v2.py
  python3 scripts/train_meta_label.py --data results/ml_dataset_sol_15m_v2.csv --embargo 24
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "scripts"))

import backtest_vbounce as vb
from indicators import ema

DATA_15M = ROOT / "user_data" / "data_sources" / "SOL_USDT-15m.csv"
BTC_1H   = ROOT / "user_data" / "data_sources" / "BTC_USDT-1h.csv"
OUT      = ROOT / "results" / "ml_dataset_sol_15m_v2.csv"

# Barriere ATR-simmetriche: TP = TP_ATR×ATR, SL = SL_ATR×ATR
TP_ATR = 2.0   # TP = 2×ATR
SL_ATR = 2.0   # SL = 2×ATR  → ratio 1:1, expectancy >0 se WR>50%
HORIZON = 96   # 24h a 15m
FEE_RT  = 0.0020
WARMUP  = 700
MIN_RR  = 0.8  # soglia R:R per il filtro "duro" (usata come FEATURE, non come gate)


def btc_regime_lagged_15m(dates_15m: pd.Series) -> np.ndarray:
    btc = pd.read_csv(BTC_1H, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    btc["date"] = pd.to_datetime(btc["date"], utc=True)
    on = (btc["close"] > ema(btc["close"], 200)).astype(float)
    htf = pd.DataFrame({"date": btc["date"], "btc_on": on}).set_index("date")["btc_on"].shift(1)
    m = pd.DataFrame({"date": pd.to_datetime(dates_15m.values, utc=True)}).merge(
        htf.rename("btc_on"), left_on="date", right_index=True, how="left")
    return m["btc_on"].ffill().fillna(0.0).to_numpy()


def build() -> pd.DataFrame:
    df_raw = pd.read_csv(DATA_15M, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    # Costruisce tutti gli indicatori live (incluso HTF 1h, knife, enter_v2)
    d = vb.build(df_raw, htf_rule="1h")

    # === array numpy per velocità ===
    c      = d["close"].to_numpy()
    o      = d["open"].to_numpy()
    high   = d["high"].to_numpy()
    low    = d["low"].to_numpy()
    vol    = d["volume"].to_numpy()
    e50    = d["ema50"].to_numpy()
    e200   = d["ema200"].to_numpy()
    atr_a  = d["atr"].to_numpy()
    adx_a  = d["adx"].to_numpy()
    er_a   = d["er"].to_numpy()
    rsi_a  = d["rsi"].to_numpy()
    bb_low = d["bb_low"].to_numpy()
    bb_up  = d["bb_up"].to_numpy()
    bb_mid = d["bb_mid"].to_numpy()
    regime = d["regime"].to_numpy()
    htf_ok = d["htf_ok"].astype(float).to_numpy()
    enter_v2 = d["enter_v2"].to_numpy()
    just_had_dip = d["just_had_dip"].to_numpy()
    turning_up   = d["turning_up"].to_numpy()

    # Feature derivate (rolling, servono come pandas)
    natr       = d["atr"] / d["close"] * 100.0
    natr_pct   = natr.rolling(200, min_periods=100).rank(pct=True).to_numpy()
    mom        = (d["close"] - d["close"].shift(16)).to_numpy()
    vol_ma20   = d["volume"].rolling(20).mean().to_numpy()
    vol_ma5    = d["volume"].rolling(5).mean().to_numpy()
    rsi_prev2  = d["rsi"].shift(2).to_numpy()
    rsi_min5   = d["rsi"].rolling(5).min().to_numpy()   # quanto era oversold il minimo
    ema50_prev8 = d["ema50"].shift(8).to_numpy()        # per pendenza EMA50
    prior_ret8  = (d["close"] / d["close"].shift(8) - 1).to_numpy()  # momentum pre-dip

    dates = pd.to_datetime(d["date"])
    btc_on = btc_regime_lagged_15m(dates)
    n = len(d)

    rows = []
    for i in range(1, n - 1):
        if i < WARMUP:
            continue
        if not (just_had_dip[i] and turning_up[i]):  # TUTTI i V-bounce, nessun filtro duro
            continue
        if not np.isfinite(atr_a[i]) or atr_a[i] <= 0:
            continue
        # skip se mancano le feature base
        if any(not np.isfinite(x) for x in (
            e50[i], e200[i], adx_a[i], er_a[i], rsi_a[i], bb_low[i], bb_up[i],
            natr_pct[i], mom[i], vol_ma20[i], vol_ma5[i], rsi_prev2[i],
            rsi_min5[i], ema50_prev8[i], prior_ret8[i]
        )):
            continue

        entry = o[i + 1]  # ingresso all'OPEN della candela successiva (no lookahead)
        a = atr_a[i]
        tp = entry + TP_ATR * a     # barriera alta: +2xATR
        sl = entry - SL_ATR * a     # barriera bassa: -2xATR (stessa distanza)

        # === TRIPLA BARRIERA (futuro = solo per label/ret_tb, mai come feature) ===
        end = min(i + 1 + HORIZON, n)
        label, ret_tb = None, None
        for j in range(i + 1, end):
            if low[j] <= sl:
                label, ret_tb = 0, (sl / entry - 1.0) - FEE_RT; break
            if high[j] >= tp:
                label, ret_tb = 1, (tp / entry - 1.0) - FEE_RT; break
        if label is None:
            last = min(end, n) - 1
            ret_tb = (c[last] / entry - 1.0) - FEE_RT
            label = int(ret_tb > 0)

        # === FEATURE QUALITÀ CANDELA (note alla chiusura della barra i) ===
        rng = high[i] - low[i] + 1e-9
        body      = abs(c[i] - o[i])
        upper_wick = high[i] - max(c[i], o[i])
        lower_wick = min(c[i], o[i]) - low[i]

        # R:R disponibile (identico alla feature f_room del v1)
        room = (bb_up[i] - c[i]) / (vb.CHANDELIER * a)

        rows.append(dict(
            date=d["date"].iloc[i],
            entry_price=entry,
            # --- FEATURE EREDITATE DA v1 ---
            f_close_ema50   = c[i] / e50[i] - 1.0,
            f_ema50_ema200  = e50[i] / e200[i] - 1.0,
            f_close_ema200  = c[i] / e200[i] - 1.0,
            f_adx           = adx_a[i],
            f_er            = er_a[i],
            f_atr_pct       = a / c[i],
            f_rsi           = rsi_a[i],
            f_rsi_delta2    = rsi_a[i] - rsi_prev2[i],
            f_bb_pos        = (c[i] - bb_low[i]) / (bb_up[i] - bb_low[i] + 1e-9),
            f_room          = room,
            f_natr_pct      = natr_pct[i],
            f_mom_pct       = mom[i] / c[i],
            f_vol_ratio     = vol[i] / (vol_ma20[i] + 1e-9),
            f_regime        = float(regime[i]),
            f_htf_ok        = htf_ok[i],
            f_btc_riskon    = btc_on[i],
            f_hour          = float(dates.iloc[i].hour),
            f_dow           = float(dates.iloc[i].dayofweek),
            # --- FEATURE NUOVE v2 ---
            f_body_pct      = body / rng,              # corpo/range: grande = rimbalzo forte
            f_upper_wick    = upper_wick / rng,        # wick sopra: grande = compratori respinti
            f_lower_wick    = lower_wick / rng,        # wick sotto: grande = buying pressure
            f_vol_spike5    = vol[i] / (vol_ma5[i] + 1e-9),   # picco volume su 5 barre
            f_ema50_slope   = (e50[i] - ema50_prev8[i]) / (ema50_prev8[i] + 1e-9), # EMA50 accelera/decelera
            f_prior_ret8    = prior_ret8[i],           # rendimento 2h precedenti (forza del dip)
            f_rsi_min5      = rsi_min5[i],             # quanto era oversold il minimo delle ultime 5 barre
            # Flag: il segnale avrebbe passato i filtri DURI? (regime/HTF/R:R)
            f_regime_pass   = float(regime[i] != -1),
            f_htf_pass      = htf_ok[i],
            f_rr_pass       = float(room >= MIN_RR),
            # label + valore economico
            label=label,
            ret_tb=ret_tb,
        ))
    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)

    print("Costruzione dataset v2 (eventi espansi + nuove feature + barriere ATR)...")
    data = build()
    if len(data) == 0:
        print("Nessun evento trovato."); return 1
    data.to_csv(args.out, index=False)

    feat = [c for c in data.columns if c.startswith("f_")]
    nan_f = int(data[feat].isna().sum().sum())
    split_ts = pd.Timestamp("2024-01-01", tz="UTC")
    n_is  = (pd.to_datetime(data["date"]) < split_ts).sum()
    n_oos = len(data) - n_is

    print(f"\n{'='*65}")
    print(f" DATASET v2 — barriere ATR-simmetriche + eventi espansi")
    print(f"{'='*65}")
    print(f"  file:          {args.out}")
    print(f"  eventi totali: {len(data)}  (vs 4268 v1 = solo segnali v2 approvati)")
    print(f"  feature:       {len(feat)}  (vs 18 v1)")
    print(f"  NaN feature:   {nan_f}  (DEVE essere 0)")
    print(f"  label=1 (tocca +{TP_ATR:.0f}xATR prima di -{SL_ATR:.0f}xATR): "
          f"{data['label'].mean()*100:.1f}%")
    print(f"  ret_tb netto medio: {data['ret_tb'].mean()*100:+.3f}%/trade")
    print(f"  split 2024-01-01:  IS={n_is}  OOS={n_oos}")
    # breakdown per filtro duro
    print(f"\n  [Composizione eventi espansi]")
    v2_orig = data[(data["f_regime_pass"]==1) & (data["f_htf_pass"]==1) & (data["f_rr_pass"]==1)]
    v2_reg  = data[data["f_regime_pass"]==0]
    v2_htf  = data[(data["f_regime_pass"]==1) & (data["f_htf_pass"]==0)]
    v2_rr   = data[(data["f_regime_pass"]==1) & (data["f_htf_pass"]==1) & (data["f_rr_pass"]==0)]
    for name, s in [("Tutti i filtri OK (=v1 allargato)", v2_orig),
                    ("REGIME BEAR (cerchi gialli bloccati)", v2_reg),
                    ("HTF gate fallito", v2_htf),
                    ("Solo R:R basso", v2_rr)]:
        if len(s) == 0: continue
        print(f"    {name:<38}: {len(s):5d} trade | "
              f"WR {s['label'].mean()*100:.0f}% | ret {s['ret_tb'].mean()*100:+.3f}%")
    print(f"\n  Prossimo passo:")
    print(f"    python3 scripts/train_meta_label.py --data {args.out} --embargo 24")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

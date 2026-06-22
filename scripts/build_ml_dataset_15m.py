#!/usr/bin/env python3
"""
Costruisce il DATASET di META-LABELING per i "3 cerchi" sul 15m — GIRA NEL CLOUD.

Niente librerie ML qui: solo numpy/pandas + gli indicatori puri di research/indicators.py
(nessun TA-Lib, nessun lightgbm). Il training/validazione gira poi sul TUO PC con
scripts/train_meta_label.py (che ha lightgbm/scikit-learn).

COSA fa, in linea con la mentalità del repo (docs/mentalita-esperti.md):
  - EVENTI CANDIDATI = gli STESSI segnali d'ingresso del bot live (V-Bounce v2:
    R:R + HTF(1h) + veto-coltello), riusando scripts/backtest_vbounce.build(). Così
    l'ML non reinventa il segnale: fa META-LABELING (López de Prado) — decide SE
    fidarsi del cerchio verde che la strategia ha già trovato.
  - LABEL = tripla-barriera allineata al "cerchio blu" (+1% = take-profit del ciclo):
      · barriera ALTA  = +1.0% (TP, il cerchio blu)
      · barriera BASSA = entry − SL_ATR×ATR (rischio adattivo alla volatilità)
      · barriera TEMPO = HORIZON candele (24h su 15m)
    label=1 se tocca prima il +1% che lo stop/tempo; 0 altrimenti. Lo stop è
    controllato PRIMA del TP (ipotesi pessimista, identica a backtest_vbounce).
  - FEATURE note SOLO alla candela del segnale (nessun lookahead). Il futuro serve
    solo come bersaglio (label/ret_tb), mai come input.
  - ret_tb = rendimento realizzato NETTO (fee round-trip Kraken) per misurare il
    VALORE ECONOMICO, non solo l'accuratezza.

Output: results/ml_dataset_sol_15m.csv  (schema compatibile con train_meta_label.py:
        colonne f_*, label, ret_tb, date).

Esempio:
  python3 scripts/build_ml_dataset_15m.py
  # poi, sul TUO PC:
  python scripts/train_meta_label.py --data results/ml_dataset_sol_15m.csv --embargo 24
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

import backtest_vbounce as vb  # noqa: E402  (logica d'ingresso live: build/add_entry_v2/CHANDELIER)
from indicators import ema     # noqa: E402  (per il regime BTC laggato)

DATA = ROOT / "user_data" / "data_sources" / "SOL_USDT-15m.csv"
BTC = ROOT / "user_data" / "data_sources" / "BTC_USDT-1h.csv"
OUT = ROOT / "results" / "ml_dataset_sol_15m.csv"

# ===== parametri tripla-barriera (allineati ai "3 cerchi") =====
TP_PCT = 0.010      # barriera ALTA = +1.0% lordo (il "cerchio blu" = take-profit del ciclo)
SL_ATR = 2.0        # barriera BASSA = entry − 2×ATR (rischio adattivo)
HORIZON = 96        # barriera TEMPO = 96 candele 15m = 24h
FEE_RT = 0.0020     # fee round-trip realistica (Kraken; per il ret_tb NETTO, non per la label)
WARMUP = 700        # = startup_candle_count del live (scarta le prime candele non affidabili)


def btc_regime_lagged_15m(dates_15m: pd.Series) -> np.ndarray:
    """Regime BTC (close>EMA200) dal frame 1h, LAGGATO di 1 barra 1h e mergiato sulla
    griglia 15m con ffill. shift(1) sul 1h = usa solo la barra GIÀ CHIUSA (no lookahead)."""
    btc = pd.read_csv(BTC, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    btc["date"] = pd.to_datetime(btc["date"], utc=True)   # allinea il tz a SOL 15m (UTC-aware)
    on = (btc["close"] > ema(btc["close"], 200)).astype(float)
    htf = pd.DataFrame({"date": btc["date"], "btc_on": on}).set_index("date")["btc_on"].shift(1)
    m = pd.DataFrame({"date": pd.to_datetime(dates_15m.values, utc=True)}).merge(
        htf.rename("btc_on"), left_on="date", right_index=True, how="left")
    return m["btc_on"].ffill().fillna(0.0).to_numpy()


def build() -> pd.DataFrame:
    df = pd.read_csv(DATA, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    # Riusa la PIPELINE LIVE: indicatori + regime + HTF(1h) + knife + segnale v2.
    d = vb.build(df, htf_rule="1h")

    # array per velocità (191k candele)
    c = d["close"].to_numpy(); o = d["open"].to_numpy()
    high = d["high"].to_numpy(); low = d["low"].to_numpy(); vol = d["volume"].to_numpy()
    e50 = d["ema50"].to_numpy(); e200 = d["ema200"].to_numpy()
    adx = d["adx"].to_numpy(); er = d["er"].to_numpy(); atr = d["atr"].to_numpy()
    rsi = d["rsi"].to_numpy(); rsi_prev2 = d["rsi"].shift(2).to_numpy()
    bb_low = d["bb_low"].to_numpy(); bb_up = d["bb_up"].to_numpy(); bb_mid = d["bb_mid"].to_numpy()
    regime = d["regime"].to_numpy(); htf_ok = d["htf_ok"].astype(float).to_numpy()
    enter_v2 = d["enter_v2"].to_numpy()
    mom = (d["close"] - d["close"].shift(16)).to_numpy()              # momentum 4h (16×15m)
    vol_ratio = (d["volume"] / d["volume"].rolling(20).mean()).to_numpy()
    natr = (d["atr"] / d["close"] * 100.0)
    natr_pct = natr.rolling(200, min_periods=100).rank(pct=True).to_numpy()
    dates = pd.to_datetime(d["date"])
    btc_on = btc_regime_lagged_15m(dates)
    n = len(d)

    rows = []
    feat_cols = ("e50", "e200", "adx", "er", "atr", "rsi", "rsi_prev2", "bb_low",
                 "bb_up", "bb_mid", "mom", "vol_ratio", "natr_pct")
    arrs = dict(e50=e50, e200=e200, adx=adx, er=er, atr=atr, rsi=rsi, rsi_prev2=rsi_prev2,
                bb_low=bb_low, bb_up=bb_up, bb_mid=bb_mid, mom=mom,
                vol_ratio=vol_ratio, natr_pct=natr_pct)

    for i in range(n - 1):
        if enter_v2[i] != 1 or i < WARMUP:
            continue
        if not np.isfinite(atr[i]) or atr[i] <= 0:
            continue
        if any(not np.isfinite(arrs[k][i]) for k in feat_cols):
            continue

        # ---- TRIPLA BARRIERA (solo per LABEL/ret_tb: usa il FUTURO come bersaglio) ----
        entry = o[i + 1]                         # ingresso all'OPEN della candela dopo (no lookahead)
        tp = entry * (1 + TP_PCT)                # cerchio blu: +1%
        sl = entry - SL_ATR * atr[i]             # stop adattivo dall'ATR del segnale
        end = min(i + 1 + HORIZON, n)
        label, ret_tb = None, None
        for j in range(i + 1, end):
            if low[j] <= sl:                     # stop PRIMA del TP (pessimista)
                label, ret_tb = 0, (sl / entry - 1.0) - FEE_RT
                break
            if high[j] >= tp:
                label, ret_tb = 1, (tp / entry - 1.0) - FEE_RT
                break
        if label is None:                        # barriera temporale (timeout)
            last = min(end, n) - 1
            ret_tb = (c[last] / entry - 1.0) - FEE_RT
            label = int(ret_tb > 0)

        rows.append(dict(
            date=d["date"].iloc[i],
            entry_price=entry,
            # --- FEATURE (note alla barra i; causa economica nel docstring/tabella) ---
            f_close_ema50=c[i] / e50[i] - 1.0,           # distanza dal trend breve
            f_ema50_ema200=e50[i] / e200[i] - 1.0,       # regime long-term (pendenza)
            f_close_ema200=c[i] / e200[i] - 1.0,         # quanto sopra/sotto la linea madre
            f_adx=adx[i],                                # forza del trend
            f_er=er[i],                                  # efficienza (range vs trend)
            f_atr_pct=atr[i] / c[i],                     # regime di volatilità
            f_rsi=rsi[i],                                # oversold
            f_rsi_delta2=rsi[i] - rsi_prev2[i],          # RSI in recupero (momentum del rimbalzo)
            f_bb_pos=(c[i] - bb_low[i]) / (bb_up[i] - bb_low[i] + 1e-9),  # posizione nelle bande
            f_room=(bb_up[i] - c[i]) / (vb.CHANDELIER * atr[i]),          # R:R disponibile al +1%
            f_natr_pct=natr_pct[i],                      # percentile volatilità (knife detector)
            f_mom_pct=mom[i] / c[i],                     # momentum 4h
            f_vol_ratio=vol_ratio[i],                    # volume al dip vs media (panico retail)
            f_regime=float(regime[i]),                   # regime corrente (-1/0/1)
            f_htf_ok=htf_ok[i],                          # gate trend 1h
            f_btc_riskon=btc_on[i],                      # regime BTC laggato (macro)
            f_hour=float(dates.iloc[i].hour),            # stagionalità intraday
            f_dow=float(dates.iloc[i].dayofweek),        # stagionalità settimanale
            # --- LABEL + rendimento realizzato netto (valore economico) ---
            label=label,
            ret_tb=ret_tb,
        ))
    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="Dataset meta-labeling 15m (3 cerchi). Gira nel cloud.")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    data = build()
    if len(data) == 0:
        print("Nessun evento candidato. Controlla i dati/segnali.")
        return 1
    data.to_csv(args.out, index=False)

    feat = [c for c in data.columns if c.startswith("f_")]
    nan_feat = int(data[feat].isna().sum().sum())
    print("=" * 70)
    print(" DATASET META-LABELING 15m (cerchi: BUY=evento, +1%=cerchio blu)")
    print("=" * 70)
    print(f"  file:                 {args.out}")
    print(f"  eventi (segnali v2):  {len(data)}")
    print(f"  feature:              {len(feat)}")
    print(f"  label=1 (tocca +1% prima dello stop): {data['label'].mean()*100:.1f}%")
    print(f"  ret_tb medio (netto): {data['ret_tb'].mean()*100:+.3f}%/trade   "
          f"somma {data['ret_tb'].sum()*100:+.0f}%")
    print(f"  NaN nelle feature:    {nan_feat}  (DEVE essere 0)")
    print(f"  periodo:              {data['date'].min()}  ->  {data['date'].max()}")
    n_is = (pd.to_datetime(data['date']) < pd.Timestamp('2024-01-01', tz='UTC')).sum()
    print(f"  split fisso 2024-01-01:  IS={n_is}  OOS={len(data)-n_is}")
    print("\n Feature:", feat)
    print("\n Prossimo passo (sul TUO PC, con lightgbm installato):")
    print("   pip install lightgbm scikit-learn")
    print(f"   python scripts/train_meta_label.py --data {args.out} --embargo 24")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

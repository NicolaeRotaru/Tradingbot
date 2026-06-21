#!/usr/bin/env python3
"""
Costruisce il DATASET per il meta-labeling ML (gira QUI, senza librerie ML).

Per ogni segnale di INGRESSO LONG della strategia genera:
  - una riga di FEATURE note alla barra del segnale (NESSUN lookahead);
  - una LABEL "tripla-barriera" (López de Prado): 1 se il trade avrebbe colpito
    prima la barriera di profitto (+k*ATR) che quella di perdita (-k*ATR) entro un
    orizzonte massimo, 0 altrimenti.

Output: results/ml_dataset_sol.csv  ->  da addestrare poi con scripts/train_meta_label.py
sul TUO PC (dove ci sono lightgbm/scikit-learn).

Regola d'oro: le feature usano solo dati fino alla candela del segnale; la label usa
il futuro SOLO come bersaglio da predire (e' lecito), mai come input.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import talib.abstract as ta

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import backtest_sol_longshort as bt   # noqa: E402

WU = bt.WU
OUT = ROOT / "results" / "ml_dataset_sol.csv"

# parametri tripla-barriera
TP_MULT = 2.0      # barriera di profitto = entry + 2*ATR
SL_MULT = 2.0      # barriera di perdita  = entry - 2*ATR
HORIZON = 168      # barriera temporale = 1 settimana (168 ore)


def btc_regime_lagged(dates: pd.Series) -> np.ndarray:
    """Regime BTC (close>EMA200) allineato e LAGGATO di 1 candela (anti-lookahead)."""
    p = ROOT / "user_data" / "data_sources" / "BTC_USDT-1h.csv"
    btc = pd.read_csv(p, parse_dates=["date"]).sort_values("date")
    btc["e200"] = ta.EMA(btc, timeperiod=200)
    btc["on"] = (btc["close"] > btc["e200"]).astype(float)
    m = pd.DataFrame({"date": dates}).merge(btc[["date", "on"]], on="date", how="left")
    on = m["on"].ffill().fillna(0.0).to_numpy()
    return np.concatenate([[0.0], on[:-1]])   # noto alla barra precedente


def build() -> pd.DataFrame:
    df = bt.load()
    df["rsi"] = ta.RSI(df, timeperiod=14)
    df["vol72"] = df["close"].pct_change().rolling(72).std()   # vol realizzata (3 giorni)
    dates = pd.to_datetime(df["date"])
    btc_on = btc_regime_lagged(dates)

    c = df["close"].to_numpy(); high = df["high"].to_numpy(); low = df["low"].to_numpy()
    e50 = df["ema50"].to_numpy(); e200 = df["ema200"].to_numpy(); e400 = df["ema400"].to_numpy()
    adx = df["adx"].to_numpy(); atr = df["atr"].to_numpy()
    rsi = df["rsi"].to_numpy(); vol72 = df["vol72"].to_numpy()
    mom24 = (df["close"] - df["close"].shift(24)).to_numpy()

    # eventi di ingresso long = transizioni 0 -> 1 della posizione strategica
    pos = bt.gen(df, allow_short=False)
    entries = np.where((pos == 1) & (np.concatenate([[0], pos[:-1]]) == 0))[0]

    rows = []
    n = len(df)
    for i in entries:
        if i < WU or i + 1 >= n:
            continue
        if any(np.isnan(x[i]) for x in (e400, adx, atr, rsi, vol72, mom24)):
            continue
        entry = c[i]
        a = atr[i]
        up = entry + TP_MULT * a
        dn = entry - SL_MULT * a
        # scansione in avanti (solo per LABEL e rendimento realizzato, non per le feature)
        label = None
        ret_tb = None
        end = min(i + HORIZON, n - 1)
        for j in range(i + 1, end + 1):
            if high[j] >= up:
                label, ret_tb = 1, up / entry - 1.0
                break
            if low[j] <= dn:
                label, ret_tb = 0, dn / entry - 1.0
                break
        if label is None:                       # barriera temporale
            ret_tb = c[end] / entry - 1.0
            label = int(ret_tb > 0)

        rows.append(dict(
            date=df["date"].iloc[i],
            entry_price=entry,
            # --- FEATURE (note alla barra i) ---
            f_close_ema50=c[i] / e50[i] - 1.0,
            f_ema50_ema200=e50[i] / e200[i] - 1.0,
            f_close_ema200=c[i] / e200[i] - 1.0,
            f_ema200_ema400=e200[i] / e400[i] - 1.0,
            f_adx=adx[i],
            f_atr_pct=a / entry,
            f_rsi=rsi[i],
            f_mom24_pct=mom24[i] / entry,
            f_vol72=vol72[i],
            f_btc_riskon=btc_on[i],
            f_hour=float(dates.iloc[i].hour),
            f_dow=float(dates.iloc[i].dayofweek),
            # --- LABEL + rendimento realizzato del trade (per valutare il valore economico) ---
            label=label,
            ret_tb=ret_tb,
        ))
    return pd.DataFrame(rows)


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    data = build()
    data.to_csv(OUT, index=False)
    feat = [c for c in data.columns if c.startswith("f_")]
    print(f"Dataset scritto: {OUT}")
    print(f"  righe (trade long): {len(data)}")
    print(f"  feature: {len(feat)}  -> {feat}")
    print(f"  label=1 (trade buono): {data['label'].mean()*100:.1f}%  "
          f"(bilanciamento plausibile)")
    print(f"  NaN nelle feature: {int(data[feat].isna().sum().sum())} (deve essere 0)")
    print(f"  periodo: {data['date'].min()}  ->  {data['date'].max()}")
    print("\nProssimo passo (sul TUO PC, con lightgbm installato):")
    print("  pip install lightgbm scikit-learn")
    print("  python scripts/train_meta_label.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

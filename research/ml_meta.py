#!/usr/bin/env python3
"""
META-LABELING ML (López de Prado) integrato col motore di ricerca.

Idea: la strategia primaria (ensemble long) decide la DIREZIONE; un modello
secondario (LightGBM) decide SE FIDARSI del trade e QUANTO scommettere. Questo
alza la precision (meno falsi ingressi) e fornisce la confidenza per il sizing.

Disciplina anti-overfitting:
  - feature note SOLO alla barra di ingresso (niente lookahead);
  - label tripla-barriera (TP/SL = ±k*ATR, orizzonte temporale);
  - WALK-FORWARD PURGED con EMBARGO di 168h (niente leakage tra train e test);
  - il modello viene ADOTTATO solo se migliora le metriche OUT-OF-SAMPLE; in caso
    contrario si tiene la strategia semplice (il modello non e' un dogma).

Output: results/research/ml_meta.png + stampa del verdetto (adottare o no).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from data import load
from indicators import realized_vol
from strategies import Params, generate, WU
from engine import RiskConfig, simulate, metrics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.metrics import roc_auc_score
import lightgbm as lgb

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "research"
TP_MULT = SL_MULT = 2.0
HORIZON = 168
EMBARGO = 168


def btc_regime_lagged(dates):
    btc = load("BTC")
    on = (btc["close"] > btc["ema200"]).astype(float)
    m = pd.DataFrame({"date": dates.values}).merge(
        pd.DataFrame({"date": btc["date"].values, "on": on.values}), on="date", how="left")
    on = m["on"].ffill().fillna(0.0).to_numpy()
    return np.concatenate([[0.0], on[:-1]])


def build_dataset(asset="SOL"):
    df = load(asset)
    p = Params(allow_short=False, allow_mr=True)
    pos, mode, reg = generate(df, p)
    entries = np.where((pos == 1) & (np.concatenate([[0], pos[:-1]]) == 0))[0]

    c = df["close"].to_numpy(); high = df["high"].to_numpy(); low = df["low"].to_numpy()
    e50 = df["ema50"].to_numpy(); e200 = df["ema200"].to_numpy(); e400 = df["ema400"].to_numpy()
    adx = df["adx"].to_numpy(); atr = df["atr"].to_numpy(); rsi = df["rsi"].to_numpy()
    er = df["er"].to_numpy(); rvol = df["rvol"].to_numpy()
    bb_low = df["bb_low"].to_numpy(); bb_up = df["bb_up"].to_numpy()
    mom24 = (df["close"] - df["close"].shift(24)).to_numpy()
    dates = pd.to_datetime(df["date"])
    btc_on = btc_regime_lagged(dates)
    n = len(df)

    rows = []
    for i in entries:
        if i < WU or i + 1 >= n:
            continue
        if any(np.isnan(x[i]) for x in (e400, adx, atr, rsi, er, rvol, mom24, bb_low)):
            continue
        entry = c[i]; a = atr[i]
        up = entry + TP_MULT * a; dn = entry - SL_MULT * a
        label = None; ret_tb = None
        end = min(i + HORIZON, n - 1)
        for j in range(i + 1, end + 1):
            if high[j] >= up:
                label, ret_tb = 1, up / entry - 1.0; break
            if low[j] <= dn:
                label, ret_tb = 0, dn / entry - 1.0; break
        if label is None:
            ret_tb = c[end] / entry - 1.0; label = int(ret_tb > 0)
        rows.append(dict(
            bar=i, date=df["date"].iloc[i],
            f_close_ema50=c[i] / e50[i] - 1.0, f_ema50_ema200=e50[i] / e200[i] - 1.0,
            f_close_ema200=c[i] / e200[i] - 1.0, f_ema200_ema400=e200[i] / e400[i] - 1.0,
            f_adx=adx[i], f_er=er[i], f_atr_pct=a / entry, f_rsi=rsi[i],
            f_mom24_pct=mom24[i] / entry, f_rvol=rvol[i],
            f_bb_pos=(c[i] - bb_low[i]) / (bb_up[i] - bb_low[i] + 1e-9),
            f_regime=float(reg[i]), f_btc_riskon=btc_on[i],
            f_hour=float(dates.iloc[i].hour), f_dow=float(dates.iloc[i].dayofweek),
            label=label, ret_tb=ret_tb,
        ))
    return df, pos, pd.DataFrame(rows)


def purged_walk_forward(data, n_folds=5):
    feats = [c for c in data.columns if c.startswith("f_")]
    X = data[feats].to_numpy(); y = data["label"].to_numpy()
    bars = data["bar"].to_numpy()
    order = np.argsort(bars)
    data = data.iloc[order].reset_index(drop=True)
    X, y, bars = X[order], y[order], bars[order]
    n = len(data)
    fold_size = n // (n_folds + 1)

    proba = np.full(n, np.nan)
    aucs = []
    importances = np.zeros(len(feats))
    for k in range(1, n_folds + 1):
        tr_end = fold_size * k
        # purge: togli dal train i campioni la cui barra cade entro EMBARGO dal test
        te_start_bar = bars[tr_end]
        tr_mask = np.arange(n) < tr_end
        tr_mask &= bars < (te_start_bar - EMBARGO)
        te_mask = (np.arange(n) >= tr_end) & (np.arange(n) < fold_size * (k + 1))
        if te_mask.sum() < 10 or tr_mask.sum() < 50:
            continue
        clf = lgb.LGBMClassifier(
            n_estimators=300, learning_rate=0.03, num_leaves=16,
            max_depth=4, subsample=0.8, colsample_bytree=0.8,
            min_child_samples=30, reg_lambda=1.0, random_state=7, verbose=-1)
        clf.fit(X[tr_mask], y[tr_mask])
        pr = clf.predict_proba(X[te_mask])[:, 1]
        proba[te_mask] = pr
        if len(np.unique(y[te_mask])) > 1:
            aucs.append(roc_auc_score(y[te_mask], pr))
        importances += clf.feature_importances_
    data["proba"] = proba
    return data, feats, aucs, importances


def main():
    df, pos, data = build_dataset("SOL")
    print(f"Dataset: {len(data)} trade long | label=1 (buoni): {data['label'].mean()*100:.1f}%")
    data, feats, aucs, importances = purged_walk_forward(data)
    tested = data.dropna(subset=["proba"])
    print(f"Walk-forward purged: {len(tested)} trade OOS | AUC medio: "
          f"{np.mean(aucs):.3f} (0.5=caso)")

    # --- valore economico: filtrare i trade peggiori migliora il rendimento medio? ---
    thr = np.median(tested["proba"])
    keep = tested[tested["proba"] >= thr]
    print("\n VALORE ECONOMICO (rendimento tripla-barriera per trade, OOS):")
    print(f"   tutti i trade   : n={len(tested):4d}  ret medio {tested['ret_tb'].mean()*100:+.2f}%  "
          f"hit {tested['label'].mean()*100:.0f}%  somma {tested['ret_tb'].sum()*100:+.0f}%")
    print(f"   filtro ML (top%) : n={len(keep):4d}  ret medio {keep['ret_tb'].mean()*100:+.2f}%  "
          f"hit {keep['label'].mean()*100:.0f}%  somma {keep['ret_tb'].sum()*100:+.0f}%")

    improve = keep["ret_tb"].mean() > tested["ret_tb"].mean() and keep["label"].mean() > tested["label"].mean()
    verdict = ("ADOTTARE come filtro/sizing: migliora ret medio E hit-rate OOS."
               if improve else
               "NON adottare: non migliora in modo robusto OOS -> si tiene la strategia semplice.")
    print(f"\n VERDETTO ML: {verdict}")

    # --- grafico: feature importance + curva pnl cumulata con/senza filtro ---
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))
    imp = pd.Series(importances, index=feats).sort_values()
    ax1.barh(imp.index, imp.values, color="#2ca02c")
    ax1.set_title("Importanza feature (LightGBM, somma sui fold)")
    ax1.grid(True, axis="x", alpha=0.3)

    t = tested.sort_values("date")
    ax2.plot(t["date"].values, (1 + t["ret_tb"]).cumprod().values, label="tutti i trade (no ML)", color="black")
    kk = t[t["proba"] >= thr]
    ax2.plot(kk["date"].values, (1 + kk["ret_tb"]).cumprod().values, label="con filtro ML", color="#2ca02c", lw=1.8)
    ax2.set_yscale("log"); ax2.set_title("PnL cumulato per-trade OOS (proxy tripla-barriera)")
    ax2.grid(True, which="both", alpha=0.3); ax2.legend(fontsize=9)
    fig.tight_layout(); fig.savefig(OUT / "ml_meta.png", dpi=115); plt.close(fig)
    print(f" Grafico: {OUT/'ml_meta.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

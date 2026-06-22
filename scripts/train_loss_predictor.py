#!/usr/bin/env python3
"""
LOSS PREDICTOR — allena il modello a PREVEDERE LE PERDITE e a evitarle.

Diversamente da train_meta_label.py (prevede WIN), questo modello prevede PERDITE:
  label_loss = 1 → trade perderà (SL o timeout negativo)
  label_loss = 0 → trade vincerà

Filtro applicato: se P(perdita) ≥ soglia → NON ENTRARE.

scale_pos_weight = n_wins/n_losses → penalizza le perdite mancate
(falso negativo su perdita = entriamo e perdiamo → il costo più alto).

Gate: prima soglia con expectancy OOS POSITIVA E ≥ 20% dei trade mantenuti.

Usage:
  python3 scripts/train_loss_predictor.py --data results/ml_dataset_sol_15m_v3.csv
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
N_FOLDS = 5

try:
    import lightgbm as lgb
    from sklearn.metrics import roc_auc_score
except ImportError:
    raise SystemExit(
        "Mancano lightgbm/scikit-learn.\n"
        "pip install lightgbm scikit-learn"
    )


def econ(returns: np.ndarray) -> dict:
    if len(returns) == 0:
        return dict(n=0, total=0.0, win=np.nan, sharpe=np.nan, expect=np.nan)
    eq = np.cumprod(1.0 + returns)
    sh = (returns.mean() / returns.std() * np.sqrt(len(returns))
          if returns.std() > 0 else np.nan)
    return dict(n=len(returns), total=eq[-1] - 1.0,
                win=(returns > 0).mean(), sharpe=sh, expect=returns.mean())


def main() -> int:
    ap = argparse.ArgumentParser(description="Loss predictor: evita le posizioni in perdita.")
    ap.add_argument("--data", default=str(ROOT / "results" / "ml_dataset_sol_15m_v3.csv"))
    ap.add_argument("--embargo", type=float, default=24.0,
                    help="embargo in ore (default 24 = 96 barre 15m)")
    args = ap.parse_args()

    df = pd.read_csv(args.data, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    feats  = [c for c in df.columns if c.startswith("f_")]
    X      = df[feats].to_numpy()
    y_win  = df["label"].to_numpy()           # 1=win, 0=loss (originale)
    y_loss = (1 - y_win).astype(float)        # 1=loss, 0=win (invertita per il predictor)
    ret    = df["ret_tb"].to_numpy()
    t      = df["date"]

    n_wins   = int(y_win.sum())
    n_losses = int((1 - y_win).sum())
    spw      = n_wins / max(1, n_losses)

    print("=" * 72)
    print(" LOSS PREDICTOR  —  prevede perdite + evita di entrare")
    print("=" * 72)
    print(f"  Dataset:           {args.data}")
    print(f"  Trade:             {len(df)}  (vincite={n_wins}, perdite={n_losses})")
    print(f"  WR baseline:       {n_wins/len(df)*100:.1f}%")
    print(f"  Expectancy base:   {ret.mean()*100:+.3f}%/trade")
    print(f"  scale_pos_weight:  {spw:.2f}  (penalizza perdite mancate)")
    print(f"  feature:           {len(feats)}")
    print()

    # ---- WALK-FORWARD PURGED (embargo=24h) ----
    bounds      = np.linspace(0, len(df), N_FOLDS + 1, dtype=int)
    oos_p_loss  = np.full(len(df), np.nan)
    aucs        = []
    last_model  = None

    for k in range(1, N_FOLDS):
        lo, hi = bounds[k], bounds[k + 1]
        test_idx   = np.arange(lo, hi)
        test_start = t.iloc[lo]
        embargo    = pd.Timedelta(hours=args.embargo)
        train_idx  = np.where(t < (test_start - embargo))[0]
        if len(train_idx) < 30:
            continue

        model = lgb.LGBMClassifier(
            n_estimators=400,
            learning_rate=0.03,
            num_leaves=20,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_samples=15,
            scale_pos_weight=spw,   # penalizza perdite mancate
            random_state=42, n_jobs=-1, verbose=-1)
        model.fit(X[train_idx], y_loss[train_idx])
        p = model.predict_proba(X[test_idx])[:, 1]   # P(questo trade perderà)
        oos_p_loss[test_idx] = p
        last_model = model
        if len(np.unique(y_loss[test_idx])) > 1:
            aucs.append(roc_auc_score(y_loss[test_idx], p))

    mask       = ~np.isnan(oos_p_loss)
    ret_oos    = ret[mask]
    p_loss_oos = oos_p_loss[mask]
    n_oos      = mask.sum()

    print(f"  AUC OOS loss-predictor: {np.mean(aucs):.3f}   (>0.55 = utile)")
    print(f"  Trade OOS con predizione: {n_oos}")
    print()

    # ---- SWEEP SOGLIE P(perdita) ----
    print(f"  Filtro: SKIP il trade se P(perdita) ≥ soglia")
    print()
    hdr = f"  {'Soglia P(loss)':>15}  {'n trade':>8}  {'WR%':>6}  "
    hdr += f"{'expect/trade':>13}  {'totale':>9}  {'Sharpe':>7}  {'gate'}"
    print(hdr)
    print("  " + "-" * 72)

    base = econ(ret_oos)
    print(f"  {'TUTTI (baseline)':>15}  {base['n']:>8}  {base['win']*100:>5.1f}%  "
          f"{base['expect']*100:>12.3f}%  {base['total']*100:>8.0f}%  "
          f"{base['sharpe']:>7.2f}  —")

    best_thr = None
    for thr in np.arange(0.30, 0.71, 0.05):
        take = p_loss_oos < thr
        r    = ret_oos[take]
        m    = econ(r)
        if m["n"] == 0:
            continue
        kept_pct = m["n"] / max(1, base["n"])
        gate = "✅" if (m["expect"] > 0 and kept_pct >= 0.20) else "❌"
        if gate == "✅" and best_thr is None:
            best_thr = thr
        print(f"  P(loss)<{thr:.2f}       {m['n']:>8}  {m['win']*100:>5.1f}%  "
              f"{m['expect']*100:>12.3f}%  {m['total']*100:>8.0f}%  "
              f"{m['sharpe']:>7.2f}  {gate}  ({kept_pct*100:.0f}% mantenuti)")

    print("  " + "-" * 72)
    print()

    if best_thr is not None:
        take = p_loss_oos < best_thr
        m    = econ(ret_oos[take])
        print(f"  ✅ GATE POSITIVO a soglia P(loss) < {best_thr:.2f}")
        print(f"     → Expectancy OOS: {m['expect']*100:+.3f}%/trade")
        print(f"     → WR OOS: {m['win']*100:.1f}%  |  n={m['n']} ({m['n']/base['n']*100:.0f}% dei trade)")
        print(f"     → NON ENTRARE quando P(perdita) ≥ {best_thr:.2f}")
    else:
        print("  ❌ GATE NON SUPERATO — nessuna soglia con expectancy OOS positiva.")
        print()
        print("  Diagnosi:")
        print(f"    avg_win  = {ret_oos[ret_oos > 0].mean()*100:+.3f}%"
              f"  avg_loss = {ret_oos[ret_oos <= 0].mean()*100:+.3f}%")
        r_tp = (TP_ATR_guess := 2.0)
        print(f"    Per essere positivi con R:R 1:1 serve WR > ~58% (con fee=0.2%).")
        print(f"    WR massimo raggiunto con filtro: "
              f"{max((ret_oos[p_loss_oos < t] > 0).mean() for t in np.arange(0.30, 0.71, 0.05) if (p_loss_oos < t).sum() > 10)*100:.1f}%")

    print()

    # ---- FEATURE IMPORTANCES ----
    if last_model is not None:
        imp = pd.Series(last_model.feature_importances_,
                        index=feats).sort_values(ascending=False)
        print("  Feature più importanti per PREVEDERE LE PERDITE (ultimo fold):")
        for name, v in imp.head(12).items():
            print(f"    {name:<25}  {v:>6.0f}")

    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Meta-labeling ML sui trade long di SOL — DA ESEGUIRE SUL TUO PC.

Richiede (non presenti nell'ambiente cloud):
    pip install lightgbm scikit-learn

Cosa fa, con disciplina ANTI-OVERFITTING:
  1. Carica results/ml_dataset_sol.csv (creato da scripts/build_ml_dataset.py).
  2. PURGED WALK-FORWARD: addestra solo sul passato, testa sul futuro, con EMBARGO
     (scarta i trade di train il cui esito si sovrappone al blocco di test) — cosi'
     niente fuga di informazione tra train e test.
  3. Genera predizioni FUORI CAMPIONE e confronta:
        - "prendi tutti i trade"  vs  "prendi solo i trade predetti buoni".
  4. GATE RIGOROSO: il filtro ML si adotta SOLO se migliora il risultato economico
     FUORI CAMPIONE (rendimento composto e Sharpe per-trade). Altrimenti si SCARTA.

Regola d'oro (docs/mentalita-esperti.md): mai fidarsi del solo in-sample. Se il
filtro non batte il baseline OOS, NON va messo in produzione.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "results" / "ml_dataset_sol.csv"
EMBARGO_HOURS = 168          # = orizzonte tripla-barriera (1 settimana)
N_FOLDS = 5
THRESHOLD = 0.50             # soglia di probabilita' per "prendere" il trade

try:
    import lightgbm as lgb
    from sklearn.metrics import roc_auc_score
except ImportError:
    raise SystemExit(
        "Mancano le librerie ML. Sul TUO PC esegui:\n"
        "  pip install lightgbm scikit-learn\n"
        "poi rilancia: python scripts/train_meta_label.py"
    )


def econ(returns: np.ndarray) -> dict:
    """Metriche economiche per-trade (compounding e Sharpe per-trade)."""
    if len(returns) == 0:
        return dict(n=0, total=0.0, win=np.nan, sharpe=np.nan)
    eq = np.cumprod(1.0 + returns)
    sharpe = returns.mean() / returns.std() * np.sqrt(len(returns)) if returns.std() > 0 else np.nan
    return dict(n=len(returns), total=eq[-1] - 1.0, win=(returns > 0).mean(), sharpe=sharpe)


def main() -> int:
    if not DATA.exists():
        raise SystemExit(f"Manca {DATA}. Esegui prima: python scripts/build_ml_dataset.py")
    df = pd.read_csv(DATA, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    feats = [c for c in df.columns if c.startswith("f_")]
    X = df[feats].to_numpy()
    y = df["label"].to_numpy()
    ret = df["ret_tb"].to_numpy()
    t = df["date"]

    # blocchi di test sequenziali (walk-forward)
    bounds = np.linspace(0, len(df), N_FOLDS + 1, dtype=int)
    oos_prob = np.full(len(df), np.nan)
    aucs = []
    for k in range(1, N_FOLDS):                 # il primo blocco fa solo da train iniziale
        lo, hi = bounds[k], bounds[k + 1]
        test_idx = np.arange(lo, hi)
        test_start = t.iloc[lo]
        # PURGE + EMBARGO: train solo su trade conclusi prima del test (con margine)
        embargo = pd.Timedelta(hours=EMBARGO_HOURS)
        train_idx = np.where(t < (test_start - embargo))[0]
        if len(train_idx) < 30:
            continue
        model = lgb.LGBMClassifier(
            n_estimators=300, learning_rate=0.03, num_leaves=15,
            subsample=0.8, colsample_bytree=0.8, min_child_samples=20,
            random_state=42, n_jobs=-1, verbose=-1)
        model.fit(X[train_idx], y[train_idx])
        p = model.predict_proba(X[test_idx])[:, 1]
        oos_prob[test_idx] = p
        if len(np.unique(y[test_idx])) > 1:
            aucs.append(roc_auc_score(y[test_idx], p))

    mask = ~np.isnan(oos_prob)
    take_all = ret[mask]
    take_flt = ret[mask & (oos_prob >= THRESHOLD)]

    a = econ(take_all)
    f = econ(take_flt)
    print("=" * 70)
    print(" META-LABELING — valutazione FUORI CAMPIONE (purged walk-forward)")
    print("=" * 70)
    print(f" AUC media OOS: {np.mean(aucs):.3f}   (0.50 = inutile, >0.55 = forse utile)")
    print(f" {'scenario':<22}{'n trade':>9}{'rend comp.':>12}{'win%':>8}{'Sharpe/tr':>11}")
    print(" " + "-" * 60)
    print(f" {'prendi TUTTI':<22}{a['n']:>9}{a['total']*100:>11.0f}%{a['win']*100:>7.0f}%{a['sharpe']:>11.2f}")
    print(f" {'solo predetti buoni':<22}{f['n']:>9}{f['total']*100:>11.0f}%{f['win']*100:>7.0f}%{f['sharpe']:>11.2f}")
    print(" " + "-" * 60)

    better = (f["total"] > a["total"]) and (np.nan_to_num(f["sharpe"]) >= np.nan_to_num(a["sharpe"]))
    if better and f["n"] >= 0.3 * a["n"]:
        print(" GATE OOS: ✅ SUPERATO — il filtro ML migliora rendimento E Sharpe fuori")
        print("           campione. Si puo' integrare come filtro d'ingresso (con cautela).")
    else:
        print(" GATE OOS: ❌ NON superato — il filtro NON aggiunge valore robusto.")
        print("           NON metterlo in produzione: tieni la strategia semplice.")
    print("=" * 70)

    # importanza feature (ultimo modello) come indizio, non come verita'
    try:
        imp = pd.Series(model.feature_importances_, index=feats).sort_values(ascending=False)
        print("\n Importanza feature (ultimo fold, indicativa):")
        for name, v in imp.items():
            print(f"   {name:<18}{v:>6.0f}")
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

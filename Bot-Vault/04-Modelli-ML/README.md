# 04 — Modelli ML

## Cosa c'è
- **Meta-labeling LightGBM** (ramo "AI"): un filtro che prova a scartare i trade peggiori.
  Codice: `research/ml_meta.py`; dataset: `scripts/build_ml_dataset.py` → `results/ml_dataset_sol.csv`;
  training: `scripts/train_meta_label.py`. Vedi `docs/ricerca-ml-meta-labeling.md`.

## Le regole anti-illusione (presidiate da ml-engineer + backtest-engineer)
- **Purged walk-forward** e **gate out-of-sample**: si adotta un modello SOLO se batte la versione
  semplice fuori campione.
- Niente **look-ahead**: feature calcolate solo con dati disponibili al tempo t.
- Un modello che brilla in-sample e crolla OOS è un nemico, non un edge.

## Stato
Ramo di ricerca. Nessun modello in produzione live. Esperimenti e validazioni vanno documentati qui.

# Ricerca ML — Meta-labeling sui trade di SOL

Questo è il **ramo di ricerca AI** del progetto: un filtro di *machine learning* che
prova a dire "questo segnale d'ingresso è buono o no?", per scartare i trade peggiori
e migliorare il rapporto rendimento/rischio (Calmar).

> ⚠️ È **ricerca, non una promessa**. Si mette in produzione **solo se** supera un
> gate rigoroso *fuori campione*. Se non batte la strategia semplice, si butta.

## Cos'è il "meta-labeling"

Idea di Marcos López de Prado: la strategia base genera i segnali (qui: l'ingresso
long trend-following); un **secondo modello** decide se *agire* o no su ciascun
segnale. Non inventa nuovi trade — **filtra** quelli esistenti. È più robusto che
chiedere a un modello di prevedere il prezzo da zero.

## Perché due script separati (cloud vs tuo PC)

Nell'ambiente cloud mancano `scikit-learn` e `lightgbm` (verificato). Quindi:

| Passo | Script | Dove gira | Cosa fa |
|------|--------|-----------|---------|
| 1 | `scripts/build_ml_dataset.py` | **qui (cloud)** | crea il dataset feature+label |
| 2 | `scripts/train_meta_label.py` | **tuo PC** | addestra e valida il modello |

## Passo 1 — Creare il dataset (già eseguibile qui)

```bash
.venv/bin/python scripts/build_ml_dataset.py
# -> results/ml_dataset_sol.csv  (285 trade, 12 feature, label bilanciate ~52%)
```

- **Feature** (note alla candela del segnale, *nessun lookahead*): distanze tra EMA,
  ADX, ATR%, RSI, momentum, volatilità realizzata, **regime BTC laggato di 1 candela**,
  ora/giorno.
- **Label** (tripla-barriera): `1` se entro 1 settimana il trade tocca prima `+2·ATR`
  che `−2·ATR`, altrimenti `0`. Salvato anche `ret_tb` (rendimento realizzato) per
  valutare il **valore economico**, non solo l'accuratezza.

## Passo 2 — Addestrare e validare (sul tuo PC)

```bash
pip install lightgbm scikit-learn
python scripts/train_meta_label.py
```

Cosa fa, con disciplina anti-overfitting:

1. **Purged walk-forward**: addestra solo sul passato, testa sul futuro, con **embargo**
   (scarta i trade di train il cui esito si sovrappone al test) → niente fuga di info.
2. Genera predizioni **fuori campione** e confronta:
   - *prendi tutti i trade* **vs** *prendi solo i predetti buoni*.
3. **Gate OOS**: il filtro si adotta **solo se** migliora rendimento composto **e**
   Sharpe per-trade fuori campione, mantenendo abbastanza trade.

Output tipico:

```
 AUC media OOS: 0.5xx   (0.50 = inutile, >0.55 = forse utile)
 scenario               n trade   rend comp.   win%   Sharpe/tr
 prendi TUTTI               ...       ...%      ..%       ....
 solo predetti buoni        ...       ...%      ..%       ....
 GATE OOS: ✅/❌ ...
```

## Come interpretare (regola d'oro)

- **AUC ≈ 0.50** → il modello non sa niente: **scarta**. Tieni la strategia semplice.
- **GATE ❌** → il filtro non aggiunge valore robusto: **non metterlo in produzione**.
- **GATE ✅** → c'è un segnale; integralo come filtro d'ingresso **con cautela** (es.
  richiama il modello in `custom_entry`/`confirm_trade_entry` di Freqtrade) e ri-valida
  in dry-run prima del live.

> Un filtro ML che brilla solo in-sample è un altro modo di ingannarsi (vedi
> `docs/realta-rendimenti-e-rischio.md`). Il gate fuori campione esiste apposta.

## Estensioni possibili (solo se il gate passa)

- Più feature *con causa economica* (funding, basis perpetuo, dominanza BTC, breadth).
- Calibrazione della **size** in base alla probabilità (Kelly frazionato) invece del
  filtro on/off.
- FreqAI (modulo ML integrato di Freqtrade) per inferenza live — richiede
  `pip install` delle dipendenze ML sulla tua macchina.

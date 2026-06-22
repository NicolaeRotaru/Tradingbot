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

---

# Esperimento 15m — i "3 cerchi" del bot live (RISULTATI REALI)

> Aggiornamento: l'ambiente cloud ORA **ha** `scikit-learn` (1.9) e `lightgbm` (4.6),
> quindi la validazione è stata eseguita davvero qui — i numeri sotto **non sono
> stimati, sono misurati**. La separazione cloud(dataset)/PC(training) resta valida
> come buona pratica, ma il training gira anche nel cloud.

## Setup

- **Dati**: `user_data/data_sources/SOL_USDT-15m.csv` (191.813 candele, 2021–2026) —
  il timeframe **reale** del bot live, non il proxy 1h.
- **Eventi candidati**: gli **stessi** segnali d'ingresso del bot live (V-Bounce v2:
  R:R + HTF(1h) + veto-coltello), riusando `scripts/backtest_vbounce.build()`. L'ML fa
  **meta-labeling**: decide se fidarsi del "cerchio verde" che la strategia ha già trovato.
- **Label (tripla-barriera, allineata al "cerchio blu" +1%)**: `1` se tocca prima
  `+1.0%` che `−2×ATR`, entro 96 candele (24h); altrimenti `0`. `ret_tb` = rendimento
  **netto** (fee round-trip) per il valore economico.
- **Script**: `scripts/build_ml_dataset_15m.py` (cloud) → `results/ml_dataset_sol_15m.csv`
  → `scripts/train_meta_label.py --data results/ml_dataset_sol_15m.csv --embargo 24`.

```bash
python3 scripts/build_ml_dataset_15m.py
python3 scripts/train_meta_label.py --data results/ml_dataset_sol_15m.csv --embargo 24
```

## Dataset

| Voce | Valore |
|---|---|
| Eventi (segnali v2) | 4.268 |
| Feature (0 NaN, no lookahead) | 18 |
| Label=1 (tocca +1% prima dello stop) | 56,1% (bilanciata) |
| Split fisso 2024-01-01 | IS = 2.296 · OOS = 1.972 |
| **ret_tb netto medio** | **−0,25%/trade** (il segnale base perde già qui) |

## Risultato fuori campione (purged walk-forward, embargo 24h)

- **AUC OOS = 0,587** → segnale **reale ma modesto** (>0,55: il modello ordina i
  segnali meglio del caso, ma di poco).
- Il filtro alza il **win rate** dal 52% al 65% (soglia 0,70).
- **Ma l'expectancy netta resta NEGATIVA a OGNI soglia**:

| Soglia prob. | n trade OOS | win% | ret netto/trade | giudizio |
|---|---:|---:|---:|---|
| tutti (no ML) | 3.415 | 52% | **−0,275%** | baseline |
| ≥ 0,50 | 1.775 | 59% | −0,221% | ancora negativa |
| ≥ 0,60 | 1.158 | 62% | −0,219% | ancora negativa |
| ≥ 0,70 | 713 | 65% | **−0,203%** | ancora negativa |

## Verdetto onesto: **NON ADOTTARE (da solo)**

Il gate "ingenuo" di `train_meta_label.py` segna ✅ perché confronta due opzioni
**entrambe in perdita** (il filtro perde *meno*). Ma il test economico vero —
*esiste una soglia con expectancy POSITIVA fuori campione?* — **fallisce a ogni soglia**.

La causa **non è la selezione del segnale** (l'ML un po' funziona, AUC 0,587): è
l'**asimmetria uscita**. Con TP `+1%` e SL `−2×ATR`, la perdita media è ~2,4× la
vincita; anche al 65% di win rate il conto resta negativo (`0,65×1% − 0,35×2,4% < 0`).

**La leva vera è il rapporto TP/SL, non un filtro ML.** Prossimo passo di RICERCA
(offline, niente live): tenere fisso il dataset e testare barriere meno asimmetriche
(TP legato all'ATR invece di +1% fisso, oppure SL più stretto) e ri-misurare
l'expectancy OOS. Solo se la strategia base diventa ~breakeven, l'ML come *sizing*
(probabilità → frazione di Kelly) ha senso di esistere.

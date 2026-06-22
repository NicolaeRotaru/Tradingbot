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

---

# Ricerca V2 — analisi esaustiva TP/SL, loss predictor, segmentazione (RISULTATI DEFINITIVI)

> Fase di ricerca completata. Tutti gli approcci ML (v1–v4, loss predictor, sweep parametri,
> segmentazione) sono stati testati con disciplina anti-overfitting (purged walk-forward,
> embargo 24h, split fisso 2024-01-01). I risultati seguenti sono **misurati**, non stimati.

## Esperimenti aggiuntivi eseguiti

### V3 — barriere simmetriche (TP=SL=2×ATR)
`scripts/build_ml_dataset_15m_v3.py` + `scripts/train_loss_predictor.py`

Ipotesi: con R:R=1:1 il breakeven scende a ~58% (vs 71% con TP=1%/SL=2×ATR). Risultato:

- Dataset: 4.268 eventi, label=1 (hit TP) = 47%, breakeven WR = 56,2%
- AUC OOS loss predictor = **0,539** (peggiora rispetto a v1: la label simmetrica è più rumorosa)
- WR massimo filtrato: **53,4%** — ancora sotto il breakeven 56,2%
- Gate OOS: ❌ a ogni soglia

### Loss predictor (`train_loss_predictor.py`)
Modello con label invertita (1=perdita) e `scale_pos_weight` per penalizzare perdite mancate.
Paradosso osservato: filtrando con alta fiducia, WR migliora leggermente ma **avg_loss peggiora**
(il filtro seleziona trade che o vincono subito o perdono profondamente — rimuove le perdite veloci).

### Sweep TP/SL (v4, v5)
Testati: TP=+1.5%, +2%, +2.5%, +3%; SL=1×ATR, 1.5×ATR, 2×ATR (sia full-sample che OOS).

| TP | SL | WR | avg_win | avg_loss | expect OOS |
|---|---|---|---|---|---|
| +1.0% | 2×ATR | 49,5% | +0,800% | -1,315% | **-0,268%** |
| +1.5% | 2×ATR | 40,7% | +1,291% | -1,341% | -0,269% |
| +2.0% | 2×ATR | 33,5% | +1,758% | -1,343% | -0,305% |
| +3.0% | 2×ATR | 26,0% | +2,570% | -1,356% | -0,334% |
| +1.0% | 1.5×ATR | 42,7% | +0,798% | -1,041% | -0,255% |

**Risultato invariante**: l'expectancy OOS è costantemente ~-0,27%/trade indipendentemente
da TP e SL. Il problema è nel segnale stesso, non nei parametri di uscita.

### Analisi per anno (2021–2026)

| Anno | N | WR | Expectancy | PF |
|---|---:|---:|---:|---|
| 2021 | 997 | 69% | -0,184% | 0,75 ❌ |
| 2022 | 582 | 54% | -0,363% | 0,54 ❌ |
| 2023 | 717 | 59% | -0,207% | 0,69 ❌ |
| 2024 | 785 | 53% | -0,225% | 0,65 ❌ |
| 2025 | 810 | 47% | -0,335% | 0,53 ❌ |
| 2026 | 377 | 47% | -0,213% | 0,63 ❌ |

**Il segnale è negativo in OGNI anno del dataset. Non c'è mai stato un anno profittevole.**
Solo 2/30 mesi OOS risultano leggermente positivi (ottobre 2025: +0,002%; giugno 2026: +0,073%).

### Segmentazione OOS (analisi monotone)
Testati: quartili EMA50/200, ATR%, ADX, ora UTC, RSI, regime BTC, combinazioni.

- Miglior segmento: **"bull forte" (EMA50/200 > 0,0169)** → WR=61,6%, expect=**-0,117%**
- Dentro "bull forte" + ML P≥0,50: WR=64,4%, ma avg_loss peggiora a -1,699% → expect=-0,090%
- Breakeven "bull forte" richiede WR > 66,5% → ML max 64,4% → non raggiunge

## Verdetto definitivo: **IL SEGNALE V-BOUNCE V2 NON HA EDGE**

Dopo ricerca esaustiva (v1–v4, 6 varianti labeling, sweep 7 combinazioni TP/SL, loss predictor,
segmentazione su 10 feature, analisi per anno), la conclusione è netta:

> **Il segnale V-Bounce v2 su SOL/USDT 15m non ha mai prodotto expectancy positiva in 6 anni
> di dati (2021–2026). Nessun filtro ML, nessuna combinazione di parametri, nessun segmento
> di mercato produce edge robusto fuori campione.**

Il motivo non è il ML né l'exit: è che la strategia V-Bounce identifica rimbalzi validi
nel 60–65% dei casi (AUC 0,587), ma il profilo TP/SL del bot (TP fisso +1%, SL adattivo
~2×ATR) crea un'asimmetria strutturale dove servono WR > 70% per breakeven.
E anche modificando TP/SL, l'expectancy per trade rimane costantemente ~-0,27%.

### Cosa fare adesso (ricerca futura)

| Opzione | Effort | Probabilità |
|---|---|---|
| Segnale diverso (es. breakout range, mean-rev 4h) | Alto | Ignoto |
| Asset diverso (BTC invece di SOL) | Basso | Più stabile |
| Timeframe superiore (1h o 4h) | Basso | Migliore S/N |
| Accettare la strategia con position sizing limitato | Zero | Drawdown basso, rend basso |

> Il bot live (dry-run) può continuare come sandbox, ma non aspettarsi alpha positivo
> basandosi su questi risultati di ricerca. L'evidenza non supporta il trading live con size reale.

---

# Ricerca V3 — e se aggiungessi lo SHORT? (RISULTATO DEFINITIVO)

> Domanda: "e se gli aggiungessi lo short?". Test empirico, non teoria.
> Script: `scripts/test_short_side.py`. Lo short è lo **specchio esatto** del V-bounce:
> invece di comprare i dip in regime non-bear, shorta i "rip" (picchi RSI>60 / sopra
> banda alta) in regime non-bull che girano giù. Stessa triple-barrier (TP=SL=2×ATR),
> stesso split fisso 2024-01-01, stessi 5+ anni di dati.

## Risultati misurati

| Direzione | Periodo | N | WR | avg_win | avg_loss | PF | Expectancy |
|---|---|---:|---:|---:|---:|---:|---:|
| LONG | IS 2021-23 | 2296 | 47,9% | +1,87% | -2,12% | 0,81 | -0,211% ❌ |
| LONG | OOS 2024+ | 1972 | 45,9% | +0,97% | -1,41% | 0,59 | -0,314% ❌ |
| **SHORT** | IS 2021-23 | 2169 | 47,3% | +1,66% | -2,06% | 0,72 | **-0,301%** ❌ |
| **SHORT** | OOS 2024+ | 2154 | 49,3% | +1,06% | -1,52% | 0,68 | **-0,249%** ❌ |

### Short per anno (robustezza)

| Anno | N | WR | Expectancy |
|---|---:|---:|---:|
| 2021 | 564 | 44,5% | -0,596% ❌ |
| 2022 (bear) | 1047 | 47,9% | -0,175% ❌ |
| 2023 | 558 | 48,9% | -0,239% ❌ |
| 2024 | 787 | 47,4% | -0,276% ❌ |
| 2025 | 970 | 50,1% | -0,224% ❌ |
| 2026 | 397 | 50,9% | -0,255% ❌ |

Anche il **2022** (bear market conclamato, -55% SOL) — dove lo short *dovrebbe* brillare —
dà expectancy negativa. L'unica cella positiva è "short bear OOS" (n=69, +0,056%) ma il
suo gemello in-sample è -0,412%: positivo OOS + negativo IS = **rumore, non edge**
(esattamente il caso che lo script avverte di non confondere con un segnale).

## Verdetto: **lo short NON aiuta. Il problema non è la direzione.**

> **Long e short hanno la STESSA expectancy negativa (~-0,25%/trade) su SOL 15m.**
> La simmetria del risultato dimostra che il problema è strutturale dell'asset/timeframe
> (mean-reversion su SOL 15m), non della direzione di trading. Aggiungere lo short
> raddoppierebbe i trade ma anche le perdite — non crea alpha, lo specchia.

### Sul target "+10%/trade"
Irrealistico per questa strategia. Su SOL 15m la mossa media catturabile è ~0,8–1,5%/trade
(avg_win misurato). +10%/trade richiede holding di giorni su mosse del 10-20% — è
swing/position trading su timeframe 4h/1d, una strategia completamente diversa, non un
tuning del V-bounce. Nessun parametro trasforma +1% in +10% per trade.

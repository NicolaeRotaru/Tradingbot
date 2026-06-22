# Ricerca completa sulla strategia + verdetto del backtest

> Sintesi di 5 ricerche parallele (rilevamento regime classico e ML, machine
> learning/FreqAI, uscite adattive, validazione/insidie) **incrociate con un
> backtest fedele del V-Bounce su 5,5 anni di SOL reale**.
> Data: giugno 2026. Obiettivo: capire se la strategia ha un vantaggio reale.

---

## ⚠️ VERDETTO IN UNA RIGA

**Il V-Bounce ha il 72% di operazioni vincenti ma PERDE soldi (profit factor 0,80, −84% in 5,5 anni). Non è un bug: la mean-reversion "compra il dip" su SOL non ha un vantaggio matematico.** Confermato in-sample E out-of-sample, e nessuna correzione di principio lo rende positivo.

---

## 1. Il backtest che cambia tutto

Strumento: `scripts/backtest_vbounce.py` (logica identica al live, dati reali
`SOL_USDT-1h.csv` 2021–2026, fee+slippage 0,06%/lato, nessun lookahead,
stop controllato prima del take-profit = ipotesi pessimista).

> Caveat: dati a **1h** (il live è 15m). È una validazione della **logica** su
> molti regimi (bull 2021, bear 2022, range 2023, calo 2024–26), non una replica
> esatta del live. Per la replica esatta servono i dati 15m (vedi §6).

### Configurazione attuale
| metrica | tutto 2021–26 | out-of-sample 2024–26 |
|---|---|---|
| Trade | 841 | 334 |
| **Win rate** | **71,7 %** | 70,7 % |
| Avg win / Avg loss | +1,09 % / **−3,44 %** | +0,93 % / −2,78 % |
| **Profit factor** | **0,80** | 0,81 |
| Expectancy | −0,19 %/trade | −0,16 %/trade |
| **Rendimento** | **−84,4 %** | −44,1 % |
| Buy & hold SOL | **+1792 %** | −56,8 % |

**Perché il grafico inganna:** vedi il 72% di vincite piccole (+1%), non
"senti" il 28% di perdite grandi (−3,4%). Le rare perdite sono ~3× le vincite
→ matematicamente negativo nonostante l'alto win rate. È il classico
"raccogliere monetine davanti a uno schiacciasassi".

### Ho provato a salvarlo — nessuna correzione di principio funziona
| ipotesi | IS profit factor | OOS profit factor | esito |
|---|---|---|---|
| Stop più stretto (1,0–2,5×ATR) | 0,43–0,76 | 0,31–0,75 | **peggio** (lo stop taglia prima del rimbalzo) |
| Lasciar correre i vincitori (no ROI) | 0,69 | 0,55 | **peggio** (i rimbalzi sono piccoli per natura) |
| Solo RANGE (regime 0) | 0,80 | 0,83 | invariato (già opera quasi solo in range) |
| Range + ER molto basso | 0,80 | 0,83 | identico (conferma: è già "pulito") |
| Stop stretto + no ROI insieme | 0,53 | 0,38 | **catastrofico** (win rate crolla al 28%) |
| Costi sotto stress 0,11%/lato | 0,71 | — | peggio (i costi mangiano il poco) |

**Tutto negativo, in-sample e out-of-sample.** Non è overfitting (sarebbe
positivo in-sample), non è sfortuna: è **assenza di edge**.

---

## 2. Rilevamento regime — indicatori classici

- **Il gate più robusto e meno overfit è `prezzo > EMA200`** (e `EMA50 > EMA200`
  per il bull). È già nel codice — va tenuto come veto non negoziabile.
- **ADX**: soglia classica **20–25**; noi usiamo **15** (troppo bassa, fa
  passare il chop). Sotto 20 i +DI/−DI fanno whipsaw.
- **+DI/−DI**: utili **solo se gated da ADX in salita**, mai come gate secco —
  è esattamente l'errore che ha cancellato le entrate (al fondo di un dip −DI
  domina sempre).
- **Efficiency Ratio**: soglia utile 0,3–0,4; valutare finestra più corta di 96.
- **Volatilità**: un veto su **ATR normalizzato** (percentile >90–95) evita di
  comprare nei crolli (knife-catching).
- **Evitare**: Hurst su 15m (troppo rumoroso, serve ~1000 osservazioni), ZigZag
  / pivot non confermati (repaint = lookahead nei backtest).

Fonti: stockcharts/investopedia (ADX, Chandelier), quantifiedstrategies,
macrosynergy (Hurst), freqtrade lookahead-analysis.

---

## 3. Rilevamento regime — statistico/ML

- **HMM / Markov-switching** (statsmodels `MarkovRegression`) vanno usati come
  **filtro di rischio sulla volatilità** ("non operare nel regime cattivo"),
  **non** come segnale di direzione.
- **Regola di correttezza**: usare probabilità **filtered** (solo dati fino a t),
  mai **smoothed** (usa il futuro → backtest gonfiati). Errore silenzioso più
  comune nei tutorial.
- **Evitare**: GMM/k-means come segnale live (whipsaw, niente persistenza);
  `ruptures` dentro la strategia (è offline/retrospettivo = lookahead). Per
  l'online serve **BOCPD** (causale).
- Qualunque metodo: **smussare l'output** con barre di conferma + isteresi,
  o il whipsaw ai bordi di regime si mangia il vantaggio.

Fonti: quantstart, statsmodels docs, Two Sigma, macrosynergy, arxiv (HMM crypto).

---

## 4. Machine learning / FreqAI — aspettative realistiche

- **FreqAI NON è "un'IA che impara il mercato da sola".** È automazione di
  apprendimento *supervisionato*: tu dai le feature E il target; lui addestra
  e ri-addestra. L'intelligenza è nel tuo design, non in una scoperta automatica.
- **Uso migliore = meta-labeling** della regola che già hai: tieni il V-Bounce
  come segnale primario, e addestri un classificatore (LightGBM, triple-barrier)
  che decide *se fidarsi* di ogni segnale. ML come **filtro su una regola**, non
  come predittore da zero.
- **Accuratezza realistica out-of-sample: ~52–54%** (fino a 57–60% sul
  sottoinsieme più confidente). Non un oracolo.
- **I costi uccidono l'ML a 15m**: a 52–54% di accuratezza si perde contro il
  buy & hold dopo fee+slippage+funding, a meno di operare poco e selettivo.
- Validazione obbligatoria: **purged/embargoed CV**, `lookahead-analysis`
  (ignora i falsi flag sui target), **Deflated Sharpe Ratio** (conta i tentativi).
- **Onesto:** il meta-labeling può *migliorare* una base che ha già un edge.
  La nostra base ha edge **negativo** → l'ML difficilmente la salva.

Fonti: freqtrade.io/freqai, Lopez de Prado (Advances in Financial ML), hudson&thames.

---

## 5. Uscite adattive (take-profit)

- **Chandelier Exit** (`max_high(22) − 3×ATR`) è la linea trailing che "segue le
  candele" e ratchet solo verso l'alto — quello che volevi per il bull.
- **MA il trailing ha expectancy NEGATIVA in range** (mean-reversion): lì il
  target fisso (banda) è corretto, non trailare.
- **Giudicare su expectancy/profit factor, non sul win rate**: il trailing
  abbassa il win rate e alza la vincita media — è il trade voluto, non un peggioramento.
- **Scaling out (mezza posizione)** non aumenta l'expectancy (Van Tharp): riduce
  solo la varianza. Non adottarlo aspettandosi più profitto.
- Freqtrade: implementare il trailing in `custom_stoploss` con
  `stoploss_from_absolute`, e **disattivare** `trailing_stop` nativo (conflitto).
- **Verifica sul nostro backtest**: la linea bull-trail non scattava quasi mai
  (l'uscita ROI rapida chiudeva prima). Cambiare 1×→3×→5×ATR non sposta il
  risultato: il problema è l'asimmetria vincita/perdita, non l'uscita.

Fonti: stockcharts (Chandelier), investopedia, vantharpinstitute, freqtrade docs.

---

## 6. Validazione e insidie — la lezione più importante

La ricerca ha letto anche i documenti già nel repo, che **confermano col tuo
stesso storico** il rischio del "tuning a occhio":

- Una versione sembrava fare **+94.687%**; ritardando il segnale di **una
  candela** (togliendo il barare-sul-futuro) crollava a **+1.137%**
  (`docs/realta-rendimenti-e-rischio.md`).
- La stessa strategia: SOL +3071%, ma **BTC −36%**, ETH peggio del buy&hold
  (`docs/validazione-1h-multiasset.md`) → era "fortuna di Solana", non edge.

**Il modo in cui abbiamo lavorato (io modifico, tu guardi il grafico, ripeti) è
il meccanismo n.1 di curve-fitting.** Stavamo adattando il bot a *quel grafico*.
Il backtest qui sopra è la prova: ciò che sembrava perfetto, su 5,5 anni perde.

### Workflow di validazione da adottare SEMPRE
1. `freqtrade lookahead-analysis` e `recursive-analysis` ad ogni modifica.
2. Finestra **out-of-sample** mai toccata in fase di tuning.
3. **Walk-forward** (non un singolo backtest) per logica stateful come la nostra.
4. **Contare i tentativi**: dopo molte modifiche, lo Sharpe va "deflazionato".
5. **Costi realistici**: slippage 0,05–0,1%/lato + funding del perp.
6. **Campione**: ≥100 trade (meglio 200–500) su bull + range + bear.
7. **Leva 1x** e sizing frazionario (¼–½ Kelly), non ~95% del saldo.

Fonti: freqtrade docs, Bailey & Lopez de Prado (Deflated Sharpe), quantstart.

---

## 7. Opzioni oneste per andare avanti

1. **Progetto-giocattolo in dry-run** — continuare a imparare senza soldi veri,
   ora *con il backtest* come bussola (niente più "a occhio").
2. **Cambiare approccio → trend-following** — su SOL il buy&hold ha fatto +1792%.
   Una strategia che *cavalca* i grandi movimenti è allineata alla natura
   dell'asset (l'opposto del comprare-il-dip). È la via con più evidenza a favore.
3. **ML meta-labeling** — interessante didatticamente, ma non salverà una base
   a edge negativo; richiede settimane e validazione seria.

**Raccomandazione:** non mettere soldi veri sul V-Bounce. Se l'obiettivo è il
profitto reale, esplorare il trend-following e validarlo con lo stesso rigore
(backtest, OOS, walk-forward) prima di qualsiasi capitale.

---

*Tutti i numeri di backtest qui sono riproducibili: `python3 scripts/backtest_vbounce.py`.
I numeri di fonti esterne erano da snippet di ricerca (WebFetch bloccato in
sessione) — vanno riconfermati sui propri dati prima di farci affidamento.*

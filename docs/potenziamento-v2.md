# Potenziamento v2 — Più potente, efficiente e profittevole (senza illudersi)

> Estensione di [`analisi-completa.md`](analisi-completa.md). Qui non aggiungiamo
> "complessità", ma **leve concrete che aumentano il rendimento netto corretto
> per il rischio** e che fanno coincidere i risultati live con il backtest.
>
> **Versione:** 2.0 — 2026-06-20

---

## 0. Cosa significa DAVVERO "più profittevole"

Il profitto netto di lungo periodo dipende da **tre numeri**, non dalla
sofisticazione della strategia:

```
   Profitto composto ≈  ALPHA LORDO  −  COSTI  −  TASSA DELLA VOLATILITÀ  −  TASSE
                        (segnale)      (fee+      (drawdown/varianza)      (fisco)
                                        slippage)
```

Quindi ci sono **5 leve reali**, in ordine di rapporto impatto/sforzo:

| # | Leva | Meccanismo | Sforzo | Impatto |
|---|---|---|---|---|
| 1 | **Tagliare i costi di esecuzione** | ogni bps di fee/slippage risparmiato è profitto netto immediato | basso | **altissimo** |
| 2 | **Controllo del drawdown** | meno varianza ⇒ più crescita composta (vedi §4) | basso | **altissimo** |
| 3 | **Efficienza del capitale** | stesso alpha su più capitale produttivo | medio | alto |
| 4 | **Alpha market-neutral / robusto** | rendimento decorrelato dal mercato, più stabile | alto | medio-alto |
| 5 | **Rigore anti-overfitting** | live ≈ backtest (profitto "vero", non illusorio) | medio | **abilitante** |

> **Punto chiave:** le leve 1 e 2 sono le più potenti e le **meno** rischiose.
> Aumentare la leva finanziaria o la complessità del modello *sembra* potente,
> ma di solito **distrugge** valore (vedi §9). Iniziamo dalle leve "gratis".

---

## 1. Leva 1 — Esecuzione: il profitto "gratis"

Ridurre i costi è l'unico modo di aumentare il profitto **senza prevedere
niente**. L'espressione del valore atteso per trade:

```
   E[trade] = p·W − (1−p)·L − COSTI_round_trip
```

Tagliare `COSTI_round_trip` può **trasformare un sistema in perdita in uno in
profitto**, a parità di segnale.

**Come abbattere i costi:**

- **Maker / post-only invece di taker.** Gli ordini passivi pagano meno fee (o
  ricevono *rebate*). Differenza tipica taker→maker: anche 1–5 bps per lato →
  enorme su strategie ad alta frequenza.
- **Fee tier e token di sconto.** Scaglioni per volume + token dell'exchange per
  ridurre le commissioni: profitto strutturale ricorrente.
- **Algoritmi di esecuzione** per ordini non banali: **TWAP/VWAP**, **iceberg**,
  **passive-then-aggressive** (parti passivo, diventi aggressivo solo se rischi
  di non eseguire). Riducono *impatto* e *slippage*.
- **Slippage budget per trade:** se l'esecuzione supera il budget, **annulla**
  invece di inseguire il prezzo. Un trade non fatto è meglio di uno fatto male.
- **Best execution cross-exchange:** instrada dove spread + fee + profondità del
  book sono migliori.
- **Riduci il turnover inutile:** ogni rotazione paga costi. Aggiungi *isteresi*
  (bande di no-trade) per non entrare/uscire sul rumore.

> **Quick win misurabile:** strumenta il sistema per registrare `slippage_bps` e
> `fee_bps` per ogni fill. Ottimizzare questi due numeri è spesso più redditizio
> che cercare un nuovo segnale.

---

## 2. Leva 2 — Drawdown e la "tassa della volatilità"

Questa è la leva più sottovalutata. Il rendimento **composto** (quello che conta
davvero) è penalizzato dalla varianza:

```
   g  ≈  μ  −  σ²/2
   (crescita composta ≈ rendimento medio − metà della varianza)
```

**Conseguenza pratica:** due strategie con lo *stesso* rendimento medio ma
volatilità diversa producono ricchezza finale molto diversa. **Ridurre la
volatilità aumenta il capitale finale anche senza migliorare il segnale.**
Esempio: recuperare da un drawdown del −50% richiede un **+100%**; da −20%
basta +25%. Il drawdown è asimmetrico e va combattuto.

**Tecniche (basso sforzo, alto impatto):**

- **Volatility targeting:** dimensiona l'esposizione per puntare a una
  volatilità di portafoglio costante (es. 10–15% annua). Riduci size quando il
  mercato è agitato, aumenti quando è calmo. Stabilizza il compounding e taglia
  i drawdown.
- **Drawdown throttle:** al crescere del drawdown corrente, **riduci
  automaticamente** la size (es. −50% di size a −10% di DD, stop a −20%). Evita
  la spirale e protegge il capitale che fa il compounding.
- **Stop di portafoglio** (giornaliero/settimanale) → safe mode.
- **Decorrelazione** (vedi §3 e §5): combinare ritorni decorrelati abbassa σ del
  portafoglio senza abbassare μ — è "l'unico pasto gratis" della finanza.

---

## 3. Leva 3 — Efficienza del capitale

Stesso alpha, più capitale che "lavora" = più profitto in valore assoluto.

- **Vol targeting / risk parity a livello di portafoglio:** alloca *budget di
  rischio* (non di capitale) uguali tra strategie/asset, così nessuna posizione
  domina il rischio.
- **Cross-margin / netting:** posizioni che si compensano (es. delta-neutral)
  liberano margine → più capacità con lo stesso conto. Attenzione: il
  cross-margin aumenta il rischio di contagio tra posizioni → usarlo con limiti.
- **Leva dinamica per regime:** leva bassa in alta volatilità/regime incerto,
  leva moderata in trend stabili. **Mai** leva fissa alta.
- **Cash management:** il capitale inattivo in stablecoin può rendere (con cautela
  sul rischio di controparte); il funding dei perp può essere fonte di yield
  (vedi §5).

---

## 4. Leva 4 — Sizing ottimale (Kelly frazionato)

Il sizing è un moltiplicatore di profitto più potente del segnale stesso.

```
   f* = μ / σ²        (frazione di Kelly, approssimazione continua)
   usare  f = (¼ … ½)·f*   →   MAI Kelly pieno
```

- **Kelly pieno massimizza la crescita ma con drawdown insopportabili** (e
  presuppone di conoscere μ e σ esatti — non è così). Kelly **frazionato**
  (¼–½) dà ~75–90% della crescita con una frazione del drawdown.
- **Sizing per confidenza:** size proporzionale alla confidenza del segnale
  (vedi *meta-labeling* §5), non size fissa.
- **De-correlazione nel sizing:** riduci la size se la nuova posizione è
  correlata a quelle esistenti (è "la stessa scommessa").

---

## 5. Leva 5 — Alpha più ROBUSTO (non più complesso)

Qui aggiungiamo edge, ma scegliendo fonti **stabili e decorrelate**, non modelli
barocchi.

- **Cross-sectional / market-neutral (long-short ranking).** Invece di prevedere
  "salirà BTC?", classifica un *paniere* di asset e vai **long sui migliori,
  short sui peggiori**. Rimuovi gran parte del rischio di mercato (beta) →
  rendimento più stabile e meno drawdown. È il pane dei fondi sistematici.
- **Carry delta-neutral (funding/basis).** Nei mercati crypto perp, il *funding
  rate* e il *basis* (spot vs future) offrono yield raccoglibile con posizioni
  **delta-neutral** (long spot / short perp). Rischio di mercato ~nullo, profitto
  da struttura. È una delle fonti più robuste e meno "predittive".
- **Meta-labeling (López de Prado).** Un modello primario decide la *direzione*;
  un secondo modello decide **se fidarsi** e *quanto* scommettere. Migliora la
  *precision*, riduce i falsi positivi e fornisce la confidenza per il sizing.
- **Ensemble multi-strategia e multi-timeframe.** Combinare segnali decorrelati
  (momentum + mean reversion + carry su più orizzonti) alza lo Sharpe del
  portafoglio più di qualsiasi singola strategia "perfetta".
- **Regime-switching allocation.** Un classificatore di regime (trend/range,
  alta/bassa vol) **accende/spegne** le strategie adatte. Evita di applicare
  mean reversion in un crollo o momentum in un mercato laterale.
- **News come edge asimmetrico, non come trigger.** Pipeline a 2 livelli (vedi
  §7): la maggior parte del valore delle news è **difensivo** (ridurre/chiudere
  rischio prima di eventi macro ad alto impatto), non offensivo.

---

## 6. Leva 6 — Far coincidere live e backtest (profitto "vero")

Un backtest brillante che non si replica live **non è profitto: è un bug**.
Questi strumenti separano l'edge reale dalla fortuna:

- **Deflated Sharpe Ratio (DSR):** corregge lo Sharpe per il numero di
  configurazioni provate. Provando 1000 strategie, qualcuna sembra ottima per
  caso: il DSR lo smaschera.
- **Probability of Backtest Overfitting (PBO):** stima la probabilità che la
  strategia "migliore" in-sample sia in realtà sotto la media out-of-sample.
- **Combinatorial Purged Cross-Validation (CPCV) + purging/embargo:** validazione
  che elimina il *leakage* temporale tra train e test (target sovrapposti).
- **Walk-forward** come standard, mai split casuale sulle serie.
- **Rollout graduale:** backtest → paper → **canary** (capitale minimo) →
  *scale-in* progressivo solo se le metriche live confermano. Non passare allo
  step successivo senza significatività statistica.

> Senza questa leva, tutte le altre sono inutili: ottimizzeresti su un'illusione.

---

## 7. Leva 7 — Efficienza operativa e dei costi (infra + LLM)

"Sempre acceso" deve costare poco ed essere veloce, altrimenti i costi mangiano
l'edge.

- **Pipeline NLP a cascata (taglia il costo LLM ~90%).**
  1. Filtro **economico** (keyword + classificatore leggero tipo FinBERT) su
     *tutte* le news → tiene solo il top X% "potenzialmente market-moving".
  2. **LLM (es. Claude)** solo su quel sottoinsieme, per estrazione eventi e
     valutazione d'impatto.
  3. **Cache** dei risultati (notizie duplicate/ribattute) e **batching**.
  Risultato: copertura totale del flusso, costo LLM ridotto a una frazione.
- **Architettura event-driven asincrona:** reagisci agli eventi (tick, fill,
  news) invece di fare *polling*; meno CPU, meno latenza, meno costi.
- **Co-location/VPS vicino all'exchange:** meno latenza ⇒ meno slippage ⇒ più
  profitto netto (rientra nella Leva 1).
- **Hot path snello:** mantieni il percorso decisione→ordine leggero; sposta
  ML/NLP pesante fuori dal hot path (precalcolo, feature store).

---

## 8. Leva 8 — Efficienza fiscale (rendimento netto-tasse)

Il profitto che conta è **al netto delle imposte** (Italia/UE — verifica con un
commercialista):

- **Tracciamento accurato** di ogni operazione (il bot logga già tutto): base di
  costo, holding period, plus/minus.
- **Tax-loss harvesting** dove consentito: realizzare perdite per compensare
  plusvalenze.
- **Attenzione al turnover:** strategie ad altissima frequenza generano molti
  eventi tassabili e adempimenti. A volte una strategia a turnover più basso
  rende di più **al netto** pur avendo un rendimento lordo inferiore.

---

## 9. Anti-pattern: cosa sembra "più potente" ma DISTRUGGE valore

Da evitare, anche se la tentazione è forte:

- ❌ **Più leva finanziaria.** Aumenta i profitti e le perdite in modo simmetrico,
  ma il *rischio di rovina* in modo **non** simmetrico. Causa #1 di liquidazione.
- ❌ **Modelli più complessi (deep learning su prezzi grezzi).** Più parametri =
  più overfitting. Raramente battono baseline + buona esecuzione.
- ❌ **Ottimizzare i parametri finché il backtest è perfetto.** Stai adattando il
  rumore. Live fallirà.
- ❌ **Reagire a ogni notizia.** La maggior parte è rumore; inseguirle = costi +
  whipsaw.
- ❌ **Full-Kelly o sizing aggressivo.** Drawdown insopportabili, anche con edge
  vero.
- ❌ **Aggiungere asset/strategie correlate.** Sembra diversificazione, ma è la
  stessa scommessa con size doppia.

---

## 10. Roadmap di potenziamento (prioritizzata per ROI)

Ordine consigliato — prima i guadagni "gratis", poi l'alpha:

| Fase | Intervento | Leva | Sforzo | Impatto atteso |
|---|---|---|---|---|
| P1 | Strumentazione costi (`fee_bps`, `slippage_bps`) + maker/post-only + fee tier | 1 | basso | **alto** |
| P2 | Volatility targeting + drawdown throttle | 2 | basso | **alto** |
| P3 | Kelly frazionato + sizing per confidenza + de-correlazione | 4 | basso | alto |
| P4 | Pipeline NLP a cascata + architettura event-driven | 7 | medio | alto (costi) |
| P5 | Validazione robusta (walk-forward, DSR/PBO, purged CV) | 6 | medio | **abilitante** |
| P6 | Regime detection + ensemble multi-strategia | 5 | medio-alto | medio-alto |
| P7 | Market-neutral (long-short ranking) + carry delta-neutral | 5/3 | alto | medio-alto |
| P8 | Best execution cross-exchange + algos (TWAP/iceberg) | 1 | alto | medio |

> **Filosofia:** ogni fase è misurabile e reversibile. Aggiungi complessità solo
> quando i dati *live* dimostrano che paga. Le fasi P1–P3 da sole, applicate a
> una strategia mediocre, spesso valgono più di mesi di ricerca su nuovi segnali.

---

## 11. Metriche-bersaglio aggiornate

Misura il "potenziamento" su questi numeri, non sul rendimento grezzo:

- **Sharpe / Sortino / Calmar** (rendimento per unità di rischio/drawdown)
- **Max drawdown** e **tempo in drawdown** (più bassi = più compounding)
- **Costi totali** (`fee_bps + slippage_bps`) per trade e in aggregato
- **Profit factor**, **expectancy netta** per trade
- **Correlazione** tra strategie/asset (più bassa = più robusto)
- **DSR / PBO** (quanto è reale l'edge)
- **Tracking error live-vs-backtest** (più basso = più affidabile)
- **Turnover** (controlla costi e impatto fiscale)

---

## 12. In una frase

> Non lo rendiamo più profittevole aggiungendo complessità, ma **togliendo
> costi e varianza**: esecuzione efficiente (Leva 1), drawdown sotto controllo
> (Leva 2), sizing disciplinato (Leva 4) e rigore anti-overfitting (Leva 6).
> L'alpha più "fancy" (Leve 5) viene per ultimo, perché è il pezzo più fragile.

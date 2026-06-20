# Analisi completa di un Trading Bot autonomo 24/7

> Documento di analisi e architettura per un sistema di trading algoritmico
> sempre attivo, che integra dati di mercato, notizie e segnali alternativi in
> tempo reale.
>
> **Stato:** documento di progettazione (nessun codice ancora implementato).
> **Versione:** 1.0 — 2026-06-20

---

## 0. Premessa onesta (leggere prima di tutto)

Hai chiesto "le strategie più complesse ed efficienti al mondo". Devo essere
diretto, perché è la cosa che ti farà risparmiare più tempo e denaro:

1. **Complessità ≠ profitto.** Le strategie più complesse (deep learning,
   modelli a centinaia di feature) sono anche le più fragili: si adattano al
   rumore del passato (*overfitting*) e falliscono sul futuro. I fondi che
   guadagnano davvero con la complessità (es. Renaissance/Medallion) hanno
   decine di PhD, dati proprietari, infrastruttura co-locata in borsa e
   decenni di ricerca. **Non è replicabile da un individuo**, e nessuna
   libreria open-source ti dà quel vantaggio.

2. **La maggior parte dei bot retail perde denaro.** Le stime serie parlano del
   **70–90% di trader algoritmici retail in perdita** nel medio periodo. Il bot
   non cambia questa statistica da solo; cambia solo la *velocità* con cui
   esegui una strategia che può essere giusta o sbagliata.

3. **Ciò che fa davvero la differenza** non è la strategia, ma in ordine:
   **gestione del rischio → qualità ed esecuzione (costi/slippage) → assenza di
   overfitting → disciplina operativa → strategia**. La strategia è l'ultimo
   anello, non il primo.

4. **"Sempre acceso" è un problema di ingegneria, non di trading.** Un sistema
   24/7 richiede monitoraggio, failover, kill-switch, gestione dei guasti e
   sicurezza delle chiavi API. Se il bot resta acceso ma rotto, perde soldi
   *più in fretta*.

Detto questo, un bot serio, prudente e ben ingegnerizzato è un progetto
**fattibile, legittimo e molto istruttivo**. Questa analisi ti dà il quadro
completo per costruirlo bene. L'obiettivo realistico non è "battere il mercato
del 300%", ma **automatizzare una strategia con edge documentato, con rischio
controllato e drawdown sopportabile**.

---

## 1. Obiettivi, vincoli e decisioni di partenza

Prima di scrivere una riga di codice servono delle scelte. Cambiano tutta
l'architettura.

### 1.1 Decisioni fondamentali (da fissare)

| Decisione | Opzioni | Impatto |
|---|---|---|
| **Mercato** | Crypto / Azioni / Forex / Futures / Opzioni | Crypto = 24/7 reale, API aperte, leva alta, rischio alto. Azioni/Forex = orari limitati, broker regolamentati, dati spesso a pagamento. |
| **"Sempre acceso"** | Letteralmente 24/7 (crypto) vs orari di borsa | Solo le crypto sono *davvero* 24/7. "Resta sempre acceso" punta naturalmente alle crypto. |
| **Stile temporale** | HFT (ms) / Intraday / Swing (giorni) / Position (settimane) | HFT è fuori portata retail (serve co-location). Lo *sweet spot* per un progetto serio è **intraday/swing**. |
| **Capitale** | Da definire | Sotto i ~1.000–5.000 € i costi fissi (dati, infra, fee) mangiano i profitti. |
| **Modalità** | Solo segnali / Semi-auto (conferma manuale) / Full-auto | Si parte SEMPRE da paper trading → semi-auto → full-auto con limiti. |
| **Chi lo gestisce** | Solo tu / per altri | Gestire denaro di terzi richiede licenze (consulenza/gestione patrimoniale): **non farlo senza autorizzazione regolamentare**. |

> **Raccomandazione di default per questo progetto:** mercato **crypto** (per il
> 24/7 e l'apertura delle API), stile **intraday/swing**, avvio in **paper
> trading**, esecuzione su exchange tramite libreria unificata. Tutto il resto
> del documento assume questo default, segnalando dove le azioni differiscono.

### 1.2 Requisiti non funzionali

- **Affidabilità:** il sistema deve sopravvivere a crash, riavvii, perdita di
  connessione, riconciliando lo stato reale con l'exchange all'avvio.
- **Sicurezza:** chiavi API mai in chiaro nel codice; permessi minimi (no
  prelievo); segregazione dei segreti.
- **Osservabilità:** ogni decisione, ordine ed errore tracciato e ispezionabile.
- **Determinismo/riproducibilità:** ogni trade deve essere riproducibile in
  backtest dalla stessa logica.
- **Fail-safe:** in caso di anomalia il default è **non operare** (chiudere o
  bloccare), non "continuare alla cieca".

---

## 2. Architettura del sistema (visione d'insieme)

Un trading bot serio NON è un singolo script. È un sistema a componenti
disaccoppiati, idealmente collegati da un bus di eventi/messaggi.

```
                        ┌──────────────────────────────────────────────┐
                        │                 ORCHESTRATORE                 │
                        │  (scheduler, supervisione, kill-switch)       │
                        └──────────────────────────────────────────────┘
                                          │
   ┌──────────────┬──────────────┬────────┼────────┬───────────────┬──────────────┐
   ▼              ▼              ▼        ▼         ▼               ▼              ▼
┌───────┐   ┌──────────┐   ┌─────────┐ ┌──────┐ ┌─────────┐  ┌──────────┐  ┌──────────┐
│ DATI  │   │ FEATURE/ │   │ ALPHA / │ │ RISK │ │ PORTFOL.│  │ EXECUTION│  │ MONITOR. │
│ INGEST│──▶│ SIGNAL   │──▶│ STRATEG.│─▶│ MGMT │─▶│ ALLOC.  │─▶│ ENGINE   │─▶│ /ALERTING│
└───────┘   └──────────┘   └─────────┘ └──────┘ └─────────┘  └──────────┘  └──────────┘
   │              │              │         │          │            │             │
   └──────────────┴──────────────┴─────────┴──────────┴────────────┴─────────────┘
                                          │
                        ┌──────────────────────────────────────────────┐
                        │   PERSISTENZA: time-series DB + DB relazionale │
                        │   (prezzi, feature, ordini, fill, PnL, log)    │
                        └──────────────────────────────────────────────┘
```

### 2.1 I dodici componenti

1. **Data Ingestion** — raccolta dati grezzi (mercato, notizie, on-chain,
   macro, social) via WebSocket/REST.
2. **Feature/Signal Engineering** — trasforma i dati grezzi in feature
   normalizzate e indicatori.
3. **Alpha / Strategy Engine** — uno o più modelli che producono segnali
   (long/short/flat + confidenza).
4. **Risk Management** — sizing delle posizioni, stop, limiti di esposizione,
   circuit breaker. **Il componente più importante.**
5. **Portfolio / Allocation** — combina i segnali in un portafoglio target,
   gestisce correlazioni e budget di rischio.
6. **Execution Engine (OMS/EMS)** — traduce gli ordini target in ordini reali
   con smart routing, gestione fill parziali, retry idempotenti.
7. **Backtesting & Simulation** — motore offline per validare le strategie su
   dati storici, con costi e slippage realistici.
8. **Paper Trading** — esecuzione live su dati reali ma con denaro finto.
9. **Persistence** — time-series DB (prezzi/feature) + DB relazionale (ordini,
   PnL, stato).
10. **Monitoring & Alerting** — metriche, dashboard, allarmi (Telegram/email),
    health check.
11. **Orchestrazione & Scheduling** — avvio/arresto componenti, supervisione,
    riconciliazione stato.
12. **Failsafe / Kill-switch** — meccanismi automatici e manuali per fermare
    tutto e mettere in sicurezza le posizioni.

---

## 3. Layer dati: "analizza tutto in tempo reale"

Questo è il cuore della tua richiesta ("mercato, notizie, ..."). I dati si
dividono in famiglie, ognuna con sfide diverse.

### 3.1 Dati di mercato (price/volume/order book)

- **Cosa:** OHLCV (candele), tick, profondità del book (L2), trade stream,
  funding rate (perp), open interest.
- **Come:** **WebSocket** per il real-time (push), REST per storico e fallback.
- **Sfide:** riconnessione automatica, gestione gap, sincronizzazione orologio,
  rate limit, deduplica, gestione candele "incomplete".
- **Crypto:** API pubbliche e gratuite per i dati (Binance, Bybit, Kraken,
  Coinbase…). Accesso tramite libreria unificata (**CCXT** / CCXT Pro per WS).
- **Azioni/Forex:** dati di qualità spesso a pagamento (es. provider dati di
  mercato). I dati gratuiti sono ritardati o limitati.

### 3.2 Notizie e testo (NLP/sentiment)

Questa è la parte "analizza le notizie". È fattibile ma **piena di insidie**:

- **Fonti:** feed di news finanziarie, RSS, API di aggregatori, comunicati,
  calendario macro (eventi: CPI, FOMC, NFP…), per crypto anche annunci di
  listing/delisting e governance.
- **Elaborazione:**
  - **Sentiment classico:** modelli specializzati su testo finanziario
    (es. famiglia FinBERT) → punteggio bullish/bearish.
  - **LLM (es. Claude):** estrazione di eventi strutturati, classificazione di
    rilevanza, riassunto, *event detection* ("questa notizia è market-moving?").
    Più flessibile, ma con **latenza** (centinaia di ms–secondi) e **costo per
    chiamata**: adatto a swing/intraday, NON a strategie ultra-veloci.
- **Insidie reali:**
  - *Latenza:* quando la notizia arriva al tuo feed, il prezzo si è già mosso.
    Competere sulla velocità delle news contro gli HFT è perso in partenza.
  - *Rumore e falsi segnali:* la maggior parte delle news non muove i prezzi.
  - *Lookahead/survivorship bias* nel backtest delle news (timestamp affidabili
    sono difficili).
  - *Manipolazione:* social e "pump" coordinati. Trattare i social con
    sospetto.
- **Uso realistico:** le news servono meglio come **filtro di rischio** ("non
  aprire posizioni 5 minuti prima/dopo un evento macro ad alto impatto",
  "riduci size in caso di sentiment estremo") più che come *trigger* diretto di
  entrata.

### 3.3 Dati alternativi (opzionali, avanzati)

- **On-chain (crypto):** flussi verso/dagli exchange, attività whale, metriche
  di rete, stablecoin supply.
- **Derivati:** funding rate, basis, term structure, skew delle opzioni, open
  interest, liquidazioni.
- **Macro:** tassi, DXY, rendimenti, calendario economico.
- **Social:** volume e sentiment (con forte scetticismo).

### 3.4 Principi di gestione dati

- **Normalizzazione e timestamp UTC** ovunque; un orologio sbagliato corrompe
  tutto.
- **Point-in-time correctness:** in backtest puoi usare SOLO ciò che era noto in
  quel momento (evitare *lookahead bias*). È l'errore #1 che gonfia i risultati.
- **Persistenza grezza:** salva i dati raw per poter ri-derivare le feature e
  fare backtest fedeli.
- **Qualità:** rilevamento outlier, gap, prezzi anomali, gestione delle
  interruzioni del feed.

---

## 4. Strategie (alpha): cosa esiste davvero

Qui sono il più concreto possibile. Nessuna strategia è "la migliore"; ognuna
funziona in **regimi di mercato** diversi.

### 4.1 Famiglie di strategie

| Famiglia | Idea | Funziona quando | Rischio principale |
|---|---|---|---|
| **Trend following / Momentum** | Compra ciò che sale, vendi ciò che scende | Mercati in trend | *Whipsaw* nei mercati laterali |
| **Mean reversion** | Il prezzo torna alla media | Mercati laterali/range | Si rompe nei trend forti ("knife catching") |
| **Statistical arbitrage / Pairs** | Spread tra strumenti correlati torna alla media | Relazioni stabili | Rottura della correlazione |
| **Market making** | Quota bid/ask, guadagna lo spread | Alta liquidità, bassa volatilità | *Inventory risk*, *adverse selection* |
| **Arbitraggio** | Stesso asset, prezzi diversi (cross-exchange, triangolare, funding) | Inefficienze temporanee | Latenza, fee, rischio di esecuzione |
| **Breakout / Volatility** | Entra alla rottura di livelli/volatilità | Espansione di volatilità | Falsi breakout |
| **ML predittivo** | Modello stima direzione/prob. | Se c'è segnale stabile | Overfitting, *regime change* |
| **News/Sentiment-driven** | Reagisce a eventi/sentiment | Eventi ad alto impatto | Latenza, rumore, manipolazione |

### 4.2 Approccio raccomandato: ensemble + regime detection

Le strategie singole sono fragili. L'approccio robusto:

1. **Regime detection** — classifica il mercato (trend / range / alta vol /
   bassa vol) con indicatori semplici o modelli (es. volatilità realizzata,
   ADX, Hurst, HMM).
2. **Strategie specializzate** — attiva la strategia adatta al regime
   (momentum in trend, mean reversion in range).
3. **Ensemble/meta-modello** — combina i segnali pesandoli per performance
   recente e confidenza, invece di affidarsi a un'unica logica.
4. **Diversificazione** — più strumenti e più strategie *decorrelate* riducono
   il drawdown molto più di una singola strategia "perfetta".

### 4.3 Sul Machine Learning (aspettative realistiche)

- **Cosa funziona meglio:** modelli **a gradiente** (XGBoost/LightGBM) su
  feature ben costruite, con target onesti (es. rendimento futuro classificato),
  **walk-forward validation** e *feature importance* controllata. Sono robusti,
  interpretabili e veloci.
- **Cosa è sopravvalutato:** deep learning su serie di prezzi grezze (LSTM,
  Transformer) per "prevedere il prezzo". Raramente batte modelli semplici, ha
  enorme rischio di overfitting e costi di sviluppo alti.
- **Regola d'oro:** se un modello complesso non batte una baseline semplice
  *out-of-sample*, la baseline vince. Sempre.
- **Il vero rischio dell'ML qui è il data leakage**: feature che "vedono il
  futuro", normalizzazioni calcolate sull'intero dataset, target sovrapposti.
  Un risultato di backtest "troppo bello" è quasi sempre un bug, non un'edge.

---

## 5. Risk management (il componente più importante)

> Se hai poco tempo, investilo qui. Una strategia mediocre con ottimo risk
> management sopravvive; una strategia ottima senza risk management ti rovina
> in un brutto giorno.

### 5.1 Sizing della posizione

- **Fixed fractional:** rischia una % fissa del capitale per trade (es. 0.5–1%).
  Semplice, robusto, raccomandato all'inizio.
- **Volatility targeting:** dimensiona la posizione in modo che ogni trade abbia
  lo stesso rischio in termini di volatilità (più size su asset calmi, meno su
  asset agitati).
- **Kelly criterion (frazionato):** ottimale in teoria, **pericoloso intero**.
  Usare al massimo *frazioni* (¼ o meno) di Kelly. Kelly pieno porta a drawdown
  insopportabili.

### 5.2 Controlli di rischio (livelli)

- **Per trade:** stop-loss (hard), take-profit, rischio massimo per posizione.
- **Giornaliero:** *daily loss limit* → se superato, stop fino al giorno dopo.
- **Drawdown:** *max drawdown* di portafoglio → riduzione size o stop totale.
- **Esposizione:** limite di esposizione lorda/netta, per asset e per settore.
- **Correlazione:** evita di accumulare rischio su asset altamente correlati
  (sono "la stessa scommessa").
- **Leva:** limiti rigidi; la leva alta è il motivo #1 di liquidazione nei bot
  crypto.
- **Concentrazione:** percentuale massima del capitale su un singolo asset.

### 5.3 Circuit breaker e kill-switch

- **Automatici:** condizioni di emergenza (perdita anomala, dati assenti,
  spread anomalo, latenza eccessiva, divergenza tra stato locale ed exchange,
  errori ripetuti) → il bot **smette di aprire** e/o **chiude** e va in
  *safe mode*.
- **Manuale:** un comando (es. bottone/telegram) che ferma tutto e mette in
  sicurezza. Deve esistere ed essere testato.
- **Default sicuro:** in dubbio, **non operare**. "Flat è una posizione."

---

## 6. Execution engine (OMS/EMS)

Tradurre un segnale in un ordine reale è dove si perdono soldi silenziosamente.

- **Tipi di ordine:** market (veloce, costoso in slippage), limit (controlla il
  prezzo, rischia di non eseguire), post-only (per market making), stop, TWAP/
  iceberg per ordini grandi.
- **Slippage e impatto:** ordini grandi muovono il prezzo. Modellare e limitare
  l'impatto; spezzare gli ordini se serve.
- **Idempotenza:** ogni ordine ha un *client order id* univoco; in caso di
  timeout/retry NON devi inviare due volte lo stesso ordine.
- **Gestione fill parziali** e degli ordini "appesi".
- **Riconciliazione:** all'avvio e periodicamente, lo stato del bot deve
  coincidere con lo stato reale dell'exchange (posizioni, ordini aperti, saldo).
  Le divergenze sono un segnale di pericolo → safe mode.
- **Costi:** fee maker/taker, funding (perp), spread. Inseriscili **sempre** nei
  calcoli e nei backtest, altrimenti le strategie ad alta frequenza sembrano
  redditizie ma non lo sono.

---

## 7. Backtesting e validazione (dove muoiono le illusioni)

Il backtest è lo strumento che ti dice se una strategia ha senso — **e anche
quello che mente di più** se fatto male.

### 7.1 Errori che gonfiano i risultati (da evitare assolutamente)

- **Lookahead bias:** usare dati non ancora disponibili in quel momento.
- **Survivorship bias:** testare solo su asset "sopravvissuti" (ignorando i
  delisting/falliti).
- **Overfitting / curve fitting:** ottimizzare i parametri finché il passato è
  perfetto. Risultato: fallimento nel futuro.
- **Costi ignorati:** niente fee, niente slippage, niente funding → numeri
  fantasiosi.
- **Data snooping:** provare 1000 strategie e tenere la "migliore" per caso
  (servono correzioni statistiche per i test multipli).
- **Fill irrealistici:** assumere di eseguire sempre al prezzo migliore.

### 7.2 Metodologia corretta

1. **Train/validation/test split temporale** (mai shuffle casuale sulle serie).
2. **Walk-forward analysis:** ottimizza su una finestra, testa sulla successiva,
   scorri. Simula il riadattamento reale.
3. **Out-of-sample sacro:** un periodo di dati che NON guardi mai durante lo
   sviluppo, usato solo alla fine.
4. **Stress test:** crisi del 2020, crollo crypto 2022, flash crash. La
   strategia sopravvive?
5. **Monte Carlo / bootstrap:** rimescola l'ordine dei trade per stimare il
   range di drawdown possibili.
6. **Metriche oltre il rendimento:** Sharpe, Sortino, Calmar, max drawdown,
   *profit factor*, win rate, expectancy, tempo in drawdown, *turnover*.

### 7.3 Paper trading (passaggio obbligatorio)

Prima di soldi veri: **settimane/mesi in paper trading** su dati live. Verifica
che i risultati live assomiglino al backtest. Se divergono molto → c'è un bug o
un bias nel backtest. **Non saltare questo passo.**

---

## 8. Stack tecnologico consigliato

Scelte pragmatiche per un progetto serio ma realizzabile da una persona/piccolo
team.

### 8.1 Linguaggio

- **Python** per il 95% dei casi (intraday/swing): ecosistema dati/ML imbattibile.
- **Rust/C++/Go** solo se servono latenze sub-millisecondo (HFT/market making):
  fuori dallo scopo iniziale.

### 8.2 Componenti

| Esigenza | Tecnologia tipica |
|---|---|
| Accesso exchange unificato | **CCXT** / CCXT Pro (WS) |
| Framework bot crypto pronto | **Freqtrade**, **Hummingbot** (market making), **Jesse** |
| Backtesting | **vectorbt**, **backtrader**, **backtesting.py**, motore custom event-driven |
| Dati & calcolo | **pandas**, **numpy**, **polars** (veloce), **TA-Lib**/**pandas-ta** |
| ML | **scikit-learn**, **XGBoost**, **LightGBM** |
| NLP/sentiment | modelli FinBERT, **transformers**; LLM (es. Claude) per eventi/riassunti |
| Time-series DB | **TimescaleDB** (Postgres), **InfluxDB**, **ClickHouse**, **QuestDB** |
| DB relazionale/stato | **PostgreSQL** |
| Cache / bus messaggi | **Redis**, **NATS**, **Kafka** (se scala) |
| Orchestrazione | **Docker** + **docker-compose**; **Kubernetes** solo se cresce |
| Scheduling/workflow | **APScheduler**, **Prefect**/**Airflow**; **n8n** per automazioni/notifiche |
| Monitoring | **Prometheus** + **Grafana**, **Sentry** (errori) |
| Alerting | Bot **Telegram**, email |
| Segreti | variabili d'ambiente, vault, mai in git |

> **Nota pragmatica:** non costruire tutto da zero. **Freqtrade** (open source,
> maturo) ti dà già ingestion, backtesting, paper/live trading, gestione
> strategie e notifiche Telegram per le crypto. Partire da lì e aggiungere il
> layer news/ML è molto più efficiente che reinventare l'OMS.

### 8.3 Infrastruttura "sempre acceso"

- **VPS/cloud** sempre attivo (non il tuo PC di casa). Per le crypto, una VPS
  affidabile vicina (in rete) all'exchange riduce latenza e disconnessioni.
- **Process manager** (systemd/Docker restart policy) per riavvio automatico.
- **Health check + watchdog**: se un componente muore, riavvio e alert.
- **Stato persistente** per ripartire dopo un crash riconciliando con l'exchange.
- **Backup** di DB e configurazioni.
- **Sicurezza:** chiavi API con permessi **minimi** (trading sì, **prelievo
  NO**), IP whitelist, 2FA, firewall, niente segreti nel repo.

---

## 9. Aspetti legali, fiscali e di sicurezza (Italia/UE)

Non sono un consulente legale/fiscale; questi sono punti da verificare con un
professionista. Ma sono parte dell'"analisi completa".

- **Trading del proprio capitale:** generalmente lecito. Automatizzarlo per te
  stesso è legittimo.
- **Gestire denaro di terzi / dare segnali a pagamento:** può configurare
  **consulenza finanziaria o gestione del risparmio**, attività **regolamentate**
  (in UE quadro MiFID II; in Italia vigilanza CONSOB/Banca d'Italia). **Non
  farlo** senza le autorizzazioni: rischi sanzioni penali/amministrative.
- **Fiscalità (Italia):** le plusvalenze da trading (incluse crypto) sono
  tassabili e vanno dichiarate; servono registri accurati di ogni operazione.
  Il bot deve **loggare tutto** anche per questo motivo.
- **Termini degli exchange/broker:** verifica che il trading via API/bot sia
  consentito dai loro ToS.
- **Sicurezza operativa:** la compromissione delle chiavi API = furto di fondi.
  Permessi minimi, segreti cifrati, monitoraggio degli accessi.
- **Antiriciclaggio/KYC:** rispettare gli obblighi degli exchange.

---

## 10. Costi realistici (perché il capitale conta)

| Voce | Indicazione |
|---|---|
| VPS/cloud 24/7 | da ~5–50 €/mese (entry) fino a centinaia se scala |
| Dati di mercato | crypto: spesso gratis; azioni/forex: da decine a centinaia €/mese |
| Dati news/sentiment | da gratis (RSS) a costosi (feed professionali) |
| Chiamate LLM (news) | a consumo; controllabile con buon design |
| Fee di trading | maker/taker per ogni ordine: **erodono** le strategie ad alta frequenza |
| Slippage | "costo nascosto" spesso > delle fee |
| Tempo di sviluppo | la voce più grande: mesi di lavoro per qualcosa di solido |

**Conseguenza:** con capitale piccolo (poche centinaia/migliaia di €), i costi
fissi e le fee rendono difficile la redditività. Serve capitale sufficiente
perché l'edge superi i costi — oppure ridurre la frequenza di trading.

---

## 11. Roadmap di sviluppo consigliata (incrementale)

Non costruire tutto insieme. Procedi a fasi, ognuna con valore e verificabile.

**Fase 0 — Fondamenta (settimane 1–2)**
- Scelte di §1 fissate. Repo, ambiente, gestione segreti, logging.
- Connessione a UNA fonte dati (un exchange) e salvataggio storico OHLCV.

**Fase 1 — Backtesting onesto (settimane 2–4)**
- Motore di backtest con **fee + slippage** e split temporale.
- 1–2 strategie semplici (es. momentum + mean reversion) come baseline.
- Metriche complete (Sharpe, max DD, profit factor) e walk-forward.

**Fase 2 — Paper trading live (settimane 4–8)**
- Esecuzione live su dati reali con denaro finto.
- Riconciliazione stato, monitoring, alert Telegram, kill-switch.
- Confronto backtest vs paper: devono assomigliarsi.

**Fase 3 — Risk management completo (in parallelo)**
- Sizing, stop, limiti giornalieri/drawdown, circuit breaker, safe mode.

**Fase 4 — Live con capitale minimo (solo dopo Fasi 1–3 superate)**
- Capitale piccolo, size ridotte, limiti rigidi.
- Monitoraggio quotidiano; confronto continuo con le aspettative.

**Fase 5 — Estensioni avanzate (opzionali)**
- Layer **news/sentiment** (prima come *filtro di rischio*, poi come segnale).
- Modelli **ML** (XGBoost) con walk-forward rigoroso.
- **Regime detection** ed ensemble multi-strategia.
- Multi-exchange, più asset, diversificazione.

> **Regola:** non si passa alla fase successiva finché la precedente non è
> verificata. La fretta nel trading automatico si paga in denaro reale.

---

## 12. Struttura di progetto proposta

```
tradingbot/
├── README.md
├── docs/
│   └── analisi-completa.md          # questo documento
├── config/
│   ├── config.example.yaml          # parametri (NIENTE segreti)
│   └── .env.example                 # template variabili d'ambiente
├── src/
│   ├── data/                        # ingestion (market, news, alt-data)
│   ├── features/                    # feature engineering, indicatori
│   ├── strategies/                  # strategie (alpha) + regime detection
│   ├── risk/                        # sizing, limiti, circuit breaker
│   ├── portfolio/                   # allocazione, gestione posizioni
│   ├── execution/                   # OMS/EMS, connettori exchange
│   ├── backtest/                    # motore di backtest + metriche
│   ├── monitoring/                  # health, metriche, alert
│   └── orchestrator/                # supervisione, scheduler, kill-switch
├── tests/                           # unit + integration test
├── notebooks/                       # ricerca/analisi esplorativa
└── infra/                           # docker, compose, deploy
```

---

## 13. I 10 errori che fanno fallire questi progetti

1. **Overfitting del backtest** — la strategia "perfetta" sul passato.
2. **Ignorare fee e slippage** — profitti immaginari.
3. **Niente risk management** — un brutto giorno azzera l'account.
4. **Leva eccessiva** (crypto) — liquidazione.
5. **Andare live senza paper trading** — bug scoperti coi soldi veri.
6. **Nessun kill-switch / riconciliazione** — il bot opera "alla cieca".
7. **Chiavi API insicure o con permesso di prelievo** — furto di fondi.
8. **Cambio di regime** — strategia tarata su un mercato che non esiste più.
9. **Aspettative irrealistiche** — inseguire rendimenti da "fondo segreto".
10. **Complessità prematura** — deep learning prima ancora di una baseline.

---

## 14. Conclusione e prossimo passo

Un trading bot 24/7 che integra mercato e notizie è **fattibile e legittimo**,
ma il successo dipende dal fare bene le cose noiose — rischio, dati, backtest
onesti, infrastruttura affidabile — molto più che dalle strategie "complesse".

**Il mio consiglio operativo:** non puntare alla "strategia più complessa del
mondo". Punta a un sistema **semplice, robusto e ben monitorato**, con rischio
controllato, e aggiungi complessità solo dove dimostra di pagare *out-of-sample*.

### Decisioni che servono da te per procedere

Per trasformare questa analisi in codice, mi servono le risposte di §1.1:
**mercato**, **stile temporale**, **capitale indicativo**, **livello di
automazione** e **se parti da un framework** (es. Freqtrade) o costruiamo da
zero. Da lì posso impostare Fase 0–1 (struttura, ingestion, backtest onesto)
direttamente nel repository.

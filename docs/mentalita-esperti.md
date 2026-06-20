# Mentalità da esperti — Come ragionano i quant che costruiscono questi sistemi

> Il livello più importante e più ignorato. L'analisi e il potenziamento dicono
> *cosa* costruire e *come* migliorarlo. Qui c'è **come pensano** le persone che
> costruiscono davvero questi sistemi: market maker, trader proprietari, gestori
> CTA, ricercatori stat-arb e quant ML. Sono i modelli mentali che separano chi
> sopravvive da chi si illude.
>
> **Versione:** 1.0 — 2026-06-20

---

## Premessa: l'edge non è una strategia, è un modo di pensare

I dilettanti cercano "la strategia che funziona". I professionisti costruiscono
un **processo di ricerca** che genera, valida e ritira strategie in continuazione,
perché sanno che ogni singola strategia **muore**. Il vero vantaggio competitivo
(il *moat*) non è un'idea: è la **fabbrica di idee** e la **disciplina** con cui
le si verifica e le si dimensiona.

I 20 principi che seguono sono il "sistema operativo mentale" dietro questi bot.

---

## Parte I — Epistemologia: non ingannare te stesso

### 1. "La prima regola è non ingannare te stesso — e sei la persona più facile da ingannare." (Feynman)
Tutto il resto deriva da qui. In trading l'auto-inganno è la norma: un backtest
bello è un piacere emotivo che spegne il senso critico. **Tratta ogni risultato
positivo come sospetto finché non hai provato a ucciderlo.**

### 2. Il backtest è un test di un'ipotesi, non una proiezione di profitto
L'esperto non chiede "quanto ho guadagnato nel backtest?". Chiede: *quante
configurazioni ho provato? quanti gradi di libertà? il risultato sopravvive
out-of-sample che non ho mai guardato? è statisticamente distinguibile dalla
fortuna (Deflated Sharpe, PBO)?* Il backtest serve a **falsificare**, non a
confermare.

### 3. Metodo scientifico, non data mining
Prima l'**ipotesi economica** ("esiste un premio al rischio per X perché Y"),
poi il test. Non il contrario. Cercare pattern nei dati finché qualcosa
"funziona" produce solo rumore travestito da segnale (*data snooping*). Pre-
registra mentalmente cosa ti aspetti **prima** di guardare i risultati.

### 4. Distingui processo e risultato
Una buona decisione può perdere denaro; una pessima può guadagnarlo. Su un
singolo trade il risultato è dominato dalla fortuna. Giudica la **qualità del
processo** e l'**expectancy su grandi numeri**, non l'esito del singolo trade.
Questo è ciò che impedisce di buttare una strategia buona dopo 3 perdite e di
amare una pessima dopo 3 vincite.

---

## Parte II — Da dove viene davvero l'edge

### 5. Chi è dall'altra parte del trade, e perché perde?
È **la** domanda dei trader professionisti. Il mercato è quasi a somma zero al
netto dei costi: il tuo profitto è la perdita (o il premio pagato) di qualcun
altro. Se non sai **chi** ti paga e **perché**, il sucker sei tu. Un edge senza
una controparte identificabile è un'illusione.

### 6. Ogni edge reale ha una causa economica (un "perché")
Le fonti di edge **vere** sono poche e identificabili:
- **Fornire liquidità** (market making): ti pagano lo spread per il servizio e
  per il rischio di inventario.
- **Sopportare un rischio che altri rifiutano** (carry, premio di volatilità,
  "vendere assicurazione"): ti pagano un premio.
- **Vantaggio informativo o di velocità** (difficile da ottenere per un retail).
- **Vincoli strutturali di altri**: venditori forzati, ribilanciamenti di
  indici, flussi di funding, liquidazioni a cascata, fine mese/trimestre.
- **Bias comportamentali** persistenti (overreaction, herding).
Se non riesci a collocare la tua strategia in una di queste categorie, **non hai
un edge**: hai overfitting.

### 7. Ogni edge decade (alpha decay)
Gli edge vengono arbitraggiati via. Più sono semplici e noti, più in fretta
muoiono. L'esperto **monitora il decadimento** (lo Sharpe live che scende, gli
spread che si comprimono), tiene una **pipeline** di strategie e **ritira**
quelle morte senza rimpianti. Non esiste la strategia "per sempre".

### 8. Capacità e affollamento (reflexivity)
Una strategia che rende su 10k € può non rendere su 10M € (impatto di mercato).
E un trade **affollato** si smonta violentemente quando tutti corrono
all'uscita insieme. L'esperto pensa alla **capacità** e si chiede: "quanto è
affollato questo trade? cosa succede quando si svuota?"

---

## Parte III — Rischio: il prodotto vero

### 9. Il rischio è il prodotto, non il rendimento
I gestori seri non "vendono" rendimenti: vendono **rendimenti corretti per il
rischio** con drawdown controllati. Ragionano in **budget di rischio**, non in
P&L. La domanda non è "quanto posso guadagnare?", ma "**quanto posso perdere, e
sopravvivo?**".

### 10. Sopravvivenza prima di tutto: rischio di rovina ed ergodicità
"Per arrivare primo, prima devi arrivare." Una serie di rendimenti **non è
ergodica**: la media temporale di un singolo conto ≠ la media d'insieme. Un
+50%/−50% ripetuto **ti rovina** anche se la media aritmetica è positiva. Per
questo si usa **Kelly frazionato** e si evita la leva alta: massimizzare la
crescita **composta** sopravvivendo, non il rendimento atteso del singolo trade.

### 11. Il sizing conta più del segnale (lezione Thorp/Kelly)
Dato un edge, è la **dimensione della scommessa** a determinare la ricchezza
finale e la sopravvivenza. Sizing troppo grande ⇒ rovina anche con edge vero;
troppo piccolo ⇒ lasci profitto sul tavolo. Gli esperti passano più tempo sul
*money management* che sulla ricerca del segnale "magico".

### 12. Le correlazioni vanno a 1 quando serve di meno
La diversificazione che vedi in tempi calmi **evapora nelle crisi**: tutto crolla
insieme. L'esperto dimensiona per lo **scenario di stress**, assume code grasse
(*fat tails*), e si chiede sempre "e se la correlazione andasse a 1 domani?".
Taleb: proteggi il **lato sinistro** (le perdite estreme); è lì che si muore.

### 13. Pensa in distribuzioni, non in punti
Non "il prezzo andrà a X", ma "ecco la distribuzione dei risultati, ecco la
coda, ecco l'expectancy". Il futuro è una distribuzione di probabilità; ragionare
per scenari (e Monte Carlo) è il default, non l'eccezione.

---

## Parte IV — La realtà dell'esecuzione (microstruttura)

### 14. Il "prezzo" del backtest è una finzione; il fill è la realtà
I principianti ragionano sul prezzo di chiusura della candela. I professionisti
ragionano sul **book**: profondità, spread, *queue position*, probabilità di
fill, slippage, impatto. Il denaro vero si fa e si perde nei dettagli
dell'esecuzione, non nel segnale teorico.

### 15. Adverse selection e rischio di inventario (lente del market maker)
Se fornisci liquidità, vieni eseguito **proprio quando hai torto** (chi ti
"prende" spesso sa qualcosa che tu non sai). Per questo i market maker
**inclinano** le quote, gestiscono l'**inventario** e ragionano su flusso
"tossico" vs benigno. Anche un bot direzionale deve sapere che i fill migliori
arrivano quando il mercato ti sta per andare contro.

### 16. I costi sono certi, l'alpha è incerto
Fee, spread, slippage e funding li paghi **sempre**; il profitto è una speranza
probabilistica. Per questo l'esperto ottimizza in modo ossessivo i costi (sono
"alpha garantito") e diffida delle strategie che funzionano solo ignorandoli.

---

## Parte V — Il mondo cambia (non-stazionarietà e adattamento)

### 17. Nessun processo di mercato è stazionario
I mercati cambiano regime: ciò che funzionava smette di funzionare. Un modello
addestrato su un regime **fallirà** in un altro. L'esperto costruisce
**umiltà e adattività** nel sistema (regime detection, riallenamento controllato,
strategie che si accendono/spengono) e **non** crede mai che la legge trovata sia
permanente.

### 18. Riflessività (Soros): i tuoi modelli cambiano ciò che modellano
Quando una strategia diventa popolare, altera il mercato che cercava di sfruttare.
L'osservatore è parte del sistema. Pensa al **secondo ordine**: "cosa succede
quando molti fanno la mia stessa cosa?".

---

## Parte VI — Disciplina operativa e meta-gioco

### 19. Il default è FLAT: la pazienza è una posizione
I professionisti **non** cercano di essere sempre nel mercato. La maggior parte
del tempo la mossa migliore è non fare nulla e aspettare il set-up con edge
chiaro. L'iperattività è un costo (fee, slippage, errori, whipsaw). "Non
operare" è una decisione attiva e spesso la migliore.

### 20. Il vero moat è la fabbrica, non la strategia (la "strategy factory")
Il vantaggio duraturo non è una formula segreta: è l'**infrastruttura di
ricerca** — dati puliti point-in-time, backtester onesto, validazione anti-
overfitting, deployment graduale, monitoraggio del decadimento, gestione del
rischio centralizzata. Chi costruisce questa **catena di montaggio** produce un
flusso di edge e sopravvive al decadimento di ognuno. È così che ragionano i
team dietro questi sistemi: investono nel **processo**, non nel singolo trade.

---

## Le scuole di pensiero (a chi "rubare" il ragionamento)

| Scuola | Cosa ti insegna a pensare | Concetti chiave |
|---|---|---|
| **Market making / prop** | microstruttura, inventario, adverse selection, costi | spread, queue, toxic flow, skew |
| **CTA / Managed futures (trend)** | diversificazione, vol targeting, sopravvivenza | risk parity, crisis alpha, drawdown control |
| **Statistical arbitrage** | market-neutral, mean reversion, relazioni | cointegrazione, pairs, beta-hedging |
| **Quant ML (López de Prado)** | rigore anti-overfitting, ML finanziario fatto bene | meta-labeling, purged CV, DSR/PBO, sample uniqueness |
| **Kelly / Thorp** | il sizing come motore della crescita | crescita composta, frazione di Kelly, rovina |
| **Taleb / risk** | code grasse, asimmetria, sopravvivenza | fat tails, convessità, ergodicità, ruin |
| **Behavioral finance** | da dove vengono i bias che sfrutti (o subisci) | overreaction, herding, anchoring |

---

## La checklist mentale prima di ogni strategia (cosa si chiede un esperto)

1. **Qual è la causa economica dell'edge?** Chi paga, e perché?
2. **Chi è dall'altra parte** e perché continua a perdere?
3. **Quanto in fretta decadrà** questo edge? Come lo monitoro?
4. **Quanti gradi di libertà** ho usato? Il risultato sopravvive out-of-sample?
5. **È distinguibile dalla fortuna?** (Deflated Sharpe, PBO)
6. **Costi e slippage realistici** lo lasciano in vita?
7. **Qual è il drawdown peggiore plausibile** e sopravvivo? (stress, code, corr→1)
8. **Qual è la capacità?** Quanto è affollato?
9. **In quale regime funziona** e cosa faccio quando il regime cambia?
10. **Come lo dimensiono** (Kelly frazionato) e come lo spengo (kill-switch)?

> Se non sai rispondere a queste dieci domande, non hai una strategia: hai una
> scommessa travestita da scienza. Gli esperti rispondono **prima** di mettere
> un euro a rischio.

---

## In una frase

> I migliori non cercano la strategia perfetta: costruiscono un **processo
> scientifico, paranoico verso l'auto-inganno e ossessionato dalla
> sopravvivenza**, in cui ogni edge ha una causa economica, viene validato senza
> pietà, dimensionato per non morire e ritirato quando smette di pagare. Il bot
> è solo l'esecutore disciplinato di questo modo di pensare.

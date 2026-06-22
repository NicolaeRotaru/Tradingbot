# Ricerca — 10 strategie diverse su SOL: dove sta (e dove NON sta) l'edge

> Domanda dell'utente: "fai 10 tentativi con 10 strategie completamente diverse".
> Risposta con numeri veri, non a occhio. Script: `scripts/test_10_strategies.py`
> e `scripts/test_trend_robustness.py`.

## Regola del gioco: alpha, non beta

SOL è passato da ~$1,5 a ~$150. **Qualsiasi** strategia long sembra geniale solo per il
beta. Quindi il test NON è il rendimento grezzo, ma:

- **Sharpe** e **Calmar** (rischio-aggiustato) **vs Buy & Hold**
- robustezza **IS vs OOS** (split fisso 2024-01-01) e **per anno**
- fee realistiche (0,06%/lato), nessun lookahead (segnale a t → posizione in t+1)

Esito `✅ batte B&H robusto` = Sharpe E Calmar OOS > Buy & Hold, E Sharpe > 0 sia IS che OOS.

## Le 10 strategie (famiglie completamente diverse)

| # | Strategia | Famiglia |
|---|---|---|
| 1 | EMA cross 20/50 | trend veloce |
| 2 | EMA cross 50/200 (golden cross) | trend lento |
| 3 | Donchian 20 breakout | breakout (turtle corto) |
| 4 | Donchian 55 breakout | breakout (turtle lungo) |
| 5 | Time-series momentum (1 giorno) | momentum |
| 6 | MACD 12/26/9 | momentum oscillatore |
| 7 | Bollinger breakout | volatilità |
| 8 | RSI mean-reversion | mean-reversion (≠ V-bounce) |
| 9 | Trend filter EMA200 | regime/filtro |
| 10 | Keltner ATR breakout | volatilità/canale |

## Risultato 1 — il timeframe 15m è un cimitero (conferma definitiva)

Su 15m **tutte e 10** le strategie falliscono OOS (OOS Sharpe ≤ 0,14, Calmar negativo).
Fee + whipsaw distruggono qualsiasi segnale. **Il timeframe del bot live (15m) è la scelta
peggiore possibile**, indipendentemente dalla strategia. Questo spiega — di nuovo, da
un'angolazione diversa — perché il V-bounce 15m non ha mai avuto edge.

## Risultato 2 — su 4h il trend-following batte Buy & Hold (rischio-aggiustato)

| Strategia 4h | ret full | Sharpe full | OOS Sharpe | OOS Calmar | OOS ret | verdetto |
|---|---:|---:|---:|---:|---:|---|
| **1. EMA cross 20/50** | +2516% | 1,19 | **0,37** | **0,12** | **+15%** | ✅ batte B&H |
| **9. Trend filter EMA200** | +1324% | 1,03 | **0,37** | **0,12** | **+14%** | ✅ batte B&H |
| 10. Keltner ATR breakout | +466% | 0,84 | 0,23 | 0,02 | +3% | ~ positivo |
| Buy & Hold | +560% | 0,87 | 0,25 | -0,16 | -29% | riferimento |

Il salto da 15m a 4h cambia tutto: il rumore cala, il trend emerge.

## Risultato 3 — robustezza del vincitore (è edge vero, non fortuna)

`scripts/test_trend_robustness.py` sul trend-following 4h:

**A) Griglia parametri**: **21/35** combinazioni EMA-cross battono B&H OOS su Sharpe — non
solo 20/50 ma tutto l'intorno (fast 15-30, slow 50-150). Un intorno positivo = **edge reale**,
non curve-fitting su un singolo parametro.

**B) Sensibilità fee**: EMA 20/50 sopravvive fino a 0,15%/lato, muore a 0,25%. L'edge è
**reale ma fragile ai costi** — serve un exchange a fee basse (Kraken Futures taker ~0,05%).

**C) Long/short**: aggiungere lo short **PEGGIORA** (OOS +15% → -32%). Terza conferma
indipendente che **shortare SOL non funziona** — solo long/flat.

**D) Per anno (la verità onesta)** — EMA 30/100 vs Buy & Hold:

| Anno | Strat ret | B&H ret | Chi vince |
|---|---:|---:|---|
| 2021 (bull) | +685% | +1430% | B&H (trend è in ritardo) |
| 2022 (bear) | -66% | -94% | **Strat (perde meno)** |
| 2023 (bull) | +583% | +920% | B&H |
| 2024 | +17% | +84% | B&H |
| 2025 (choppy) | -1% | -35% | **Strat (protegge)** |
| 2026 | -25% | -41% | **Strat** |

## Sintesi: cosa fa davvero il trend-following su SOL

Il trend-following 4h **non genera rendimento extra**: nei bull (2021, 2023) **resta indietro**
a Buy & Hold (entra in ritardo, esce in anticipo). Il suo valore è la **DIFESA**: nei bear e
nei choppy (2022, 2025, 2026) **perde molto meno**. Risultato netto: stesso rendimento di
lungo periodo ma con **MaxDD -65% invece di -97%** e Sharpe più alto → equity più liscia.

> **È un overlay di riduzione del rischio, non una macchina di alpha.** Cambia "compra e
> soffri -97%" in "segui il trend e soffri -65%, con meno notti insonni".

## Raccomandazione finale basata sull'evidenza

1. **Abbandonare il V-bounce mean-reversion 15m.** È il quadrante peggiore (timeframe basso
   + mean-reversion + SOL): nessun edge in 5+ anni, in nessuna direzione, con nessun ML.
2. **Se si vuole essere su SOL**: trend-following long/flat su **4h** (EMA cross ~20/50 o
   filtro EMA200), solo long, su exchange a fee basse. Aspettativa realistica: rendimento ≈
   Buy & Hold ma con **drawdown ~30% più basso** e meno stress.
3. **Niente short, niente +10%/trade.** Lo short bleeds; +10%/trade non esiste per questo
   tipo di strategia (avg-win realistico ~1-2% sui timeframe operativi).
4. Il bot dry-run resta utile come sandbox, ma la decisione informata su SOL è:
   *trend-following 4h per ridurre il drawdown, oppure semplicemente accumulare e tenere.*

---

## Appendice — "fare 10% a settimana con stop loss basso": verifica empirica

> Richiesta: "trova un modo per fare 10% a settimana con stop loss basso".
> Script: `scripts/test_10pct_weekly.py`. 10%/sett composto = 1,10^52 = **142× l'anno =
> +14.100%/anno**. Testato sui dati reali, non a parole.

**1) Rendimenti settimanali reali (leva 1×):**

| | media | mediana | % settimane ≥10% | migliore | peggiore |
|---|---:|---:|---:|---:|---:|
| Buy & Hold | +1,85% | -0,60% | 23% | +59% | -60% |
| Trend 4h EMA20/50 | +1,76% | 0,00% | 14% | +59% | -19% |

La media settimanale realistica è **~+1,8%**, non +10%. Per centrare il target servirebbe
che la *media* fosse +10% ogni settimana: 5,6× la realtà.

**2) Leva — il rendimento sale ma arriva la liquidazione:**

| Leva | CAGR | media sett. | MaxDD | liquidato? |
|---:|---:|---:|---:|---|
| 1× | +84% | +1,76% | -65% | no |
| 2× | +94% | +3,58% | **-91%** | no |
| 3× | -100% | -3,50% | -85% | 💀 azzerato |
| 5× | -100% | -14,76% | -99% | 💀 azzerato |
| 10× | -100% | -100% | — | 💀 azzerato |

Nota: già a 2× il CAGR sale appena (+84%→+94%) ma il MaxDD esplode a -91% (tassa di
volatilità). Da 3× in su le gambe larghe di SOL (barre 4h da -15%/-25%, frequenti)
**liquidano il conto**. "Stop loss basso" = poco margine = liquidazione *garantita* a leva.

**3) È mai successo storicamente?** Su 279 settimane, solo 39 (14%) hanno fatto ≥10%, e la
**striscia massima consecutiva è 7 settimane**. Per il target ne servirebbero 52 di fila.

**4) La matematica dello "stop basso":** per +10%/sett con stop al 2% servirebbe un win rate
> 75% a R:R 1:1 — non esiste su SOL. A R:R 3:1 servirebbe colpire +6% in un giorno
ripetutamente: il backtest reale dà expectancy **negativa**.

### Verdetto

> **10% a settimana sostenuto NON è realizzabile sui dati reali di SOL.** A leva 1× la
> realtà è ~+1,8%/sett; con la leva il numero teorico sale ma "stop basso + leva" =
> liquidazione nei crash (che su SOL arrivano spesso). Non è mai esistita una striscia
> lunga di settimane ≥10%. **Chiunque prometta 10%/sett con stop basso vende fumo** — o,
> peggio, ti mette a leva e ti liquida. L'obiettivo realistico resta: trend-following 4h
> long-only per un rendimento ≈ Buy & Hold con drawdown molto più basso.

---

# Ricerca — altre 22 tecniche (32 totali): il vincitore robusto

> Richiesta: "testa altre 20 strategie/tecniche". Fatte 22 (oltre alle 10 base).
> Script: `scripts/test_20_techniques.py`. Tecniche: Supertrend, Hull MA, TEMA, Ichimoku,
> Parabolic SAR, Vortex, Stocastico, CCI, Williams %R, ROC, Awesome Oscillator,
> MACD-hist, RSI2 Connors, Bollinger %B, Z-score, Williams Vix Fix, OBV, Chaikin Money
> Flow, Volatility targeting, Ensemble multi-TF, Donchian+filtro, Heikin-Ashi.

⚠ **Multiple-testing**: con 44 test (22 tecniche × 2 timeframe), qualcuno sembra buono per
puro caso. Conta solo ciò che ha logica economica, è positivo in PIÙ anni, batte B&H, e
ha un INTORNO di parametri positivo (non un singolo punto).

## Risultato — convergenza sul trend-following multi-livello

Quasi tutte le tecniche vincono IS (2021-23, mega-bull) e degradano OOS (2024-26, choppy).
Questo è il marchio del trend-following: brilla nei trend forti, soffre nel laterale.
**Mostrando IS/OOS/FULL insieme** (niente scarto cieco), emerge un vincitore netto:

| Tecnica (4h) | IS Sharpe | OOS Sharpe | OOS ret | FULL ret | MaxDD | verdetto |
|---|---:|---:|---:|---:|---:|---|
| **20. Ensemble multi-TF** | 1,52 | **0,69** | **+66%** | +2133% | -57% | ✅ migliore |
| 9. Williams %R | 0,98 | 0,49 | +33% | +431% | -71% | ✅ |
| 21. Donchian+filtro EMA200 | 1,19 | 0,28 | +9% | +523% | -57% | ✅ |
| 2. Hull MA 20/50 | 0,92 | 0,26 | -5% | +222% | -64% | ✅ marginale |
| Buy & Hold | 1,24 | 0,25 | -29% | +560% | -97% | riferimento |

**Ensemble multi-TF** = long solo quando EMA20>50 **E** EMA100>200 concordano. È il
trend-following più selettivo (solo 65 trade in 5 anni): resta fuori da SOL nel chop/bear,
dentro solo nei trend confermati su due scale.

## Robustezza dell'Ensemble — 9/9 varianti battono B&H OOS

`scripts/test_20_techniques.py` + griglia parametri:

| Parametri EMA | OOS Sharpe | OOS ret | FULL ret |
|---|---:|---:|---:|
| (20/50)&(80/200) | **0,76** | +80% | +2233% |
| (25/50)&(100/200) | 0,69 | +68% | +2359% |
| (20/50)&(100/200) | 0,69 | +66% | +2133% |
| (20/60)&(100/200) | 0,65 | +60% | +2567% |
| ...altre 5 varianti | 0,40-0,57 | +22-46% | +885-1676% |

**9 su 9** battono Buy & Hold OOS → l'edge è un INTORNO robusto, non curve-fitting.
La logica è economica e chiara: due livelli di trend che concordano filtrano il rumore.

## Verdetto finale dopo 32 strategie testate

> **Il vincitore robusto su SOL è il trend-following multi-livello (Ensemble multi-TF) su 4h:
> ~78% CAGR full, MaxDD -57% (vs -97% di Buy & Hold), batte B&H sia in rendimento grezzo
> che risk-adjusted, OOS, con 9/9 varianti positive.**

Caveat onesti che restano:
- **Campione sottile**: ~25-30 trade OOS → lo Sharpe ha barre d'errore ampie. Il +66% OOS è
  incoraggiante ma non "certezza statistica". Va confermato in dry-run forward.
- **È difensivo**: ~78% CAGR è ottimo per crypto, ma è **78%/anno, non +14.100%/anno** del
  target "10%/settimana". Nessuna delle 32 strategie si avvicina a quel numero.
- Funziona perché STA FUORI nei momenti brutti (2022, parte 2025), non perché indovina i top.

**Questa è la strategia da costruire come bot reale**: Ensemble multi-TF trend-agreement su
4h, long-only. Aspettativa realistica e documentata, niente fumo.

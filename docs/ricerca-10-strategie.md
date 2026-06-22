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

# Riferimento — bot con rete neurale (deep ML)

Regole non negoziabili. La skill `SKILL.md` è la procedura; qui c'è il *perché tecnico* e le tabelle.

## 1. Obiettivo realistico (perché "1–5% al giorno" non esiste)
- 1%/giorno composto ≈ **+3.700%/anno**; 5%/giorno ≈ numero con 7 zeri. Nessun fondo al mondo lo fa (il miglior quant della storia: ~39% **all'anno**).
- La bussola del progetto è il **Calmar** (rendimento ÷ max drawdown), non il rendimento nudo. Vedi `docs/realta-rendimenti-e-rischio.md`.
- Target sano: massimizzare Calmar/Sharpe **out-of-sample** con drawdown sopportabile. Un Calmar OOS > 1 stabile è già ottimo.

## 2. Anti-leakage (la differenza tra un numero vero e uno falso)
- **Feature**: solo dati fino alla barra di ingresso `i` (la funzione `feature_matrix` non usa il futuro).
- **Label**: tripla barriera (TP/SL = ±2·ATR, orizzonte 168h) — guarda avanti solo per *etichettare*, mai per le feature.
- **Walk-forward purged + embargo 168h**: il test è sempre *dopo* il train; i campioni entro l'embargo dal test sono **rimossi** dal train.
- **Scaler per-fold**: media/varianza stimate **solo** sul train del fold, mai sull'intero dataset.
- Se cambi queste regole, il risultato non vale più. Lo scopo è battere l'overfitting, non il backtest.

## 3. Leva e liquidazione (tabella)
Approssimazione: con leva L, una mossa avversa di ~**1/L** ti liquida (al netto del maintenance margin, che la peggiora).

| Leva | Mossa che liquida | Realtà su SOL (1h) |
|---|---|---|
| 1x | −100% | praticamente mai |
| 2x | −50% | raro |
| 3x (default) | −33% | possibile in settimane brutte |
| 5x | −20% | qualche volta l'anno |
| 10x | −10% | **una giornata normale** |

- Il sizing del motore (`engine.py`) è **vol-targeting con tetto** `max_leverage`: in mercati calmi alza la size, in mercati agitati la abbassa. La leva nominale è un **tetto**, non un target.
- Lo script `train_deep.py` rifiuta leva >5x senza `--i-understand-liquidation` e >10x sempre.
- Regola pratica: la leva **non aumenta l'edge**, moltiplica sia profitti sia perdite **sia** la probabilità di liquidazione. Più volatile è l'asset, più basso il tetto.

## 4. Gate di adozione (quando la rete entra in produzione)
Il modello si adotta **solo se**, sui trade OUT-OF-SAMPLE:
1. il ret medio per trade dei trade "fidati" (proba ≥ soglia) **>** ret medio di tutti;
2. l'hit-rate dei trade "fidati" **>** hit-rate di tutti;
3. il **Calmar-proxy** (per-trade) dei "fidati" **≥** quello di tutti.

Se anche solo uno fallisce → **NON adottare**, si tiene la strategia semplice. Un modello che non passa il gate è rumore costoso.

## 5. Rischio in produzione (Freqtrade)
Mappa la confidenza della rete sul sizing e tieni i circuit breaker:
- `custom_stake_amount()` / `leverage()` ← scala con la confidenza (0–1), entro il tetto §3.
- `stoploss` + `trailing_stop` come rete di sicurezza per-trade.
- `protections`: **MaxDrawdown** (stop globale), **StoplossGuard** (troppi stop = pausa), **CooldownPeriod** (niente re-entry impulsivi).
- **Kill-switch** sempre raggiungibile (Telegram `/stopentry`, `/forceexit all`).

## 6. Percorso verso il live (mai saltare passi)
1. Verdetto `ADOTTARE` sullo script.
2. Backtest Freqtrade con **fee + slippage** reali → leggi max drawdown e Calmar.
3. **Dry-run** (soldi finti) per settimane; l'equity dev'essere coerente col backtest.
4. Solo allora, **live con capitale minimo** e leva bassa; scala solo se regge.

## 7. Note tecniche sullo script
- `--asset` SOL/ETH/BTC (serve il CSV 1h in `user_data/data_sources/`).
- `--model lstm` (veloce, robusto) o `transformer` (più capace, più dati richiesti).
- `--seq-len` lunghezza della finestra (default 32 barre = 32h di contesto).
- Output: `results/research/deep_<asset>_<model>.{png,json,pt}`.
- Su dati **tabellari/finanziari** il gradient boosting (ramo `research/ml_meta.py`) spesso eguaglia o batte la rete: confronta i due verdetti prima di scegliere.

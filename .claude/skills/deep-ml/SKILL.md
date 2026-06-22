---
name: deep-ml
description: >-
  Costruisce e valida un bot di trading con rete neurale (LSTM/Transformer) sul
  codice di ricerca esistente, in modo ONESTO: meta-labeling con walk-forward
  purged + embargo, leva con tetto e controllo della liquidazione, e adozione
  SOLO se batte la baseline fuori campione. Usala quando l'utente dice "crea il
  bot con la rete neurale", "deep learning sul trading", "addestra la rete",
  "bot con AI/LSTM/transformer", "machine learning per il bot", "voglio il bot
  che impara". Non promette rendimenti fissi (no "% al giorno"): misura
  Calmar/drawdown reali e RIFIUTA il modello se non migliora out-of-sample.
argument-hint: "[asset] [lstm|transformer]"
allowed-tools:
  - Read
  - Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/train_deep.py:*)
  - Bash(python3 research/*)
---

# Bot con rete neurale (deep ML) — onesto e con leva controllata

Addestra una rete (LSTM/Transformer) come **meta-labeler**: la strategia primaria
(`research/strategies.py`) decide la **direzione**, la rete decide **se fidarsi**
del trade e **quanto** scommettere. Si **adotta solo se batte la baseline fuori
campione**.

**Principio non negoziabile:** nessuna promessa di "% al giorno". Il successo si
misura in **Calmar / max drawdown / Sharpe out-of-sample**. Regole complete in
`reference.md` — leggile prima di toccare la leva.

## Prerequisiti
1. Dati 1h in `user_data/data_sources/<ASSET>_USDT-1h.csv` (SOL/ETH già presenti).
2. Dipendenze sul PC/VPS dove addestri: `pip install torch scikit-learn`
   (numpy/pandas/matplotlib già usati dal repo). L'ambiente Claude qui **non** ha
   torch: il training gira sulla macchina dell'utente.

## Procedura
1. **Addestra + valida** (build dataset → walk-forward purged → verdetto):
   ```
   python3 ${CLAUDE_SKILL_DIR}/scripts/train_deep.py --asset SOL --model lstm --leverage 3
   ```
   Argomenti: `/deep-ml <asset> <lstm|transformer>` per cambiare
   (es. `/deep-ml ETH transformer`). Tetto leva di default **3x**.
2. **Leggi il VERDETTO** stampato a fine run:
   - **`ADOTTARE`** → la rete migliora ret medio, hit-rate **e** Calmar OOS. Salva
     modello+scaler in `results/research/deep_<asset>_<model>.pt`. Vai al passo 3.
   - **`NON adottare`** → la rete non aiuta: **tieni la strategia semplice**, non
     forzare. **Non** aumentare la leva per "compensare": amplifica solo le perdite.
3. **(Solo se adottato) Cabla nella strategia Freqtrade**: crea una nuova strategia
   in `user_data/strategies/` che carica il modello e usa la **confidenza** (0–1)
   come moltiplicatore in `custom_stake_amount()` e/o `leverage()`, con il tetto
   del passo 5. Modello a bassa confidenza → size/leva ridotte o trade saltato.
4. **Backtest Freqtrade** con fee+slippage reali, poi **dry-run** (soldi finti) per
   settimane confrontando col backtest. Guida: `docs/setup-freqtrade.md`.
5. **Leva & liquidazione** (tabella in `reference.md`): default **3x**. Lo script
   rifiuta leve >5x senza `--i-understand-liquidation` e >10x sempre. Con leva 10x
   ti liquida un **−10%**: su SOL succede in una giornata normale.
6. **Kill-switch**: tieni attive le `protections` Freqtrade (MaxDrawdown,
   StoplossGuard, CooldownPeriod) + stoploss/trailing come circuit breaker.

## Mai
- Mai live senza un dry-run lungo che conferma il backtest.
- Mai alzare la leva per inseguire un target: il rischio cresce più del rendimento.
- Mai adottare un modello che non passa il gate OOS.

Dettagli completi (anti-leakage, leva, rischio, gate di adozione): **`reference.md`**.

# 🚦 GATE-OOS — la regola anti-overfitting (vale SEMPRE)

> Nata dalla radiografia del 2026-06-24: l'edge regge **solo su SOL** ed è instabile
> (`deflated_sharpe` SOL 0,0028 · BTC 3,4e-6 · ETH 0,00044; WFO OOS BTC −3,7%, ETH −11%).
> Per non spacciare overfitting per edge, prima di "promuovere" qualsiasi strategia/modello deve
> passare questo cancello. Lo presidiano @backtest-engineer e @quant-strategist; veto a @risk-manager.

## Una strategia/modello si PROMUOVE solo se passa TUTTI questi check
1. **Walk-forward OOS positivo** — Sharpe OOS > 0 e profit factor > 1 sul periodo fuori campione
   (non in-sample). Fonte: `results/research/summary.json` (blocco `wfo_oos`).
2. **Generalizza oltre SOL** — risultato OOS **non negativo** su almeno un asset diverso da SOL
   (es. BTC o ETH). Se vince solo su SOL, è un caso, non un edge: resta confinata a SOL e dichiarata tale.
3. **Robustezza alla ricerca multipla** — `deflated_sharpe` non trascurabile rispetto al numero di
   trial (oggi n_trials=400). Un deflated_sharpe ≈ 0 è una bandiera rossa: l'edge è probabilmente fortuna.
4. **Stabilità tra i fold** — niente fold con Sharpe estremi alternati (es. SOL: +2,47 e −2,00):
   se la dispersione tra fold è enorme, la strategia non è affidabile.
5. **Costi realistici** — backtest con fee/slippage credibili (oggi 0,10%/lato unico; migliorare con
   maker/taker reali Kraken). I margini sottili (PF ~1,03) non reggono costi più alti.
6. **Niente look-ahead** — verificato che il segnale sia applicato alla barra **successiva**
   (nel motore: `engine.py` usa `w_target[i-1]` → ok). Ogni nuova feature va ricontrollata.

## Conseguenze
- ✅ Passa tutti → si può promuovere in **paper** (🟡, avvisando) e, in seguito, proporre verso il
  live (🔴, firma di Nicola).
- ❌ Non passa anche uno solo → **non si promuove**. Si documenta il perché e si torna in R&D.
- Lo stato attuale (giugno 2026): l'ensemble su SOL **passa parzialmente** (OOS SOL +42%, ma fallisce
  il check 2 di generalizzazione e ha deflated_sharpe ≈ 0). → **Confinata a SOL, non promossa altrove.**

## Dove si applica
- Prima di cambiare `pair_whitelist` o aggiungere un asset operativo.
- Prima di proporre il passaggio a live.
- A ogni nuova strategia/variante o modello ML (gate prima dell'adozione, vedi `04-Modelli-ML/`).

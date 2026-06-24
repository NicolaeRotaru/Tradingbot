# 01 — Strategia

## Mandato del bot
Far crescere il capitale in modo **robusto** (sopravvivenza prima del rendimento), in **paper**
finché Nicola non firma il passaggio al live. Niente overfitting spacciato per edge.

## Strategie nel repo (`user_data/strategies/`)
| Strategia | Idea | Mercato |
|---|---|---|
| `StarterStrategy` | Baseline anti-overfitting: compra il ribasso in trend rialzista (EMA200 + RSI). Solo long, no leva. | spot 1h |
| `StarterStrategyLS` | Variante long+short (futures, più rischiosa). | futures |
| `TrendFollowStrategy` | Trend-following (su SOL ha reso di più, con caveat overfitting/drawdown). | — |
| `SolLongShortStrategy` | Solo SOL, Kraken Futures, long+short. | futures |
| **`EnsembleRegimeStrategy`** ⭐ | Commutazione di regime: trend-long quando sale, mean-reversion (compra basso/vende alto) in laterale; short di trend disattivato di default. Vol-targeting + drawdown-throttle + filtro ML. | futures 15m, SOL/USD:USD |

## Tesi di edge (da mantenere onesta)
L'edge principale documentato è su **SOL**. Attenzione: **non generalizza** su BTC/ETH (vedi
`docs/validazione-1h-multiasset.md`) e degrada fuori campione (vedi sotto). La disciplina di
rischio e l'assenza di overfitting valgono più della complessità.

## Numeri reali da non dimenticare (fonte: `results/research/summary.json`)
SOL, strategia Trend-long:
- **In-sample**: total +71%, Calmar **1,97**, Sharpe 1,44, DD −20%.
- **Out-of-sample**: total **+11,4%**, CAGR 4,5%, Calmar **0,19**, Sharpe 0,32, DD −23,6%, win-rate 50,5%, PF 1,02.
Il forte degrado IS→OOS è il promemoria n.1: validare sempre fuori campione.

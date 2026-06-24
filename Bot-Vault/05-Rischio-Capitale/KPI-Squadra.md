# 🎯 KPI-Squadra — l'OKR che ogni senior possiede

Ogni reparto possiede UN numero. Target indicativi (paper) da tarare col desk. Lo STOP automatico:
se un reparto brucia rischio senza rendere, si ferma e si rivede.

| Senior | KPI posseduto | Target indicativo |
|---|---|---|
| quant-strategist | n. edge validati OOS che battono la baseline | ≥1 nuovo edge robusto / trimestre |
| trader-esecuzione | slippage+fee medi per trade | minimizzare (misurati da diario) |
| portfolio-manager | rendimento corretto per il rischio (Calmar) | Calmar > 1 (su periodo onesto) |
| risk-manager | max drawdown reale | sotto soglia (es. < 20% paper) |
| market-analyst | qualità della lettura di regime | regime corretto vs realtà |
| onchain-analyst | segnali on-chain azionabili (non rumore) | ≥1 segnale utile / settimana |
| sentiment-analyst | accuratezza degli estremi di sentiment | contrarian che funziona |
| macro-analyst | eventi macro anticipati con impatto | nessun evento ad alto impatto mancato |
| news-intelligence | catalizzatori veri segnalati / falsi allarmi | alta precisione, copertura oraria |
| data-engineer | qualità dati (gap/duplicati/look-ahead) | 0 difetti nei dataset usati |
| ml-engineer | modelli che superano il gate OOS | adottare solo ciò che batte la baseline |
| backtest-engineer | onestà dei backtest (costi+OOS) | 0 backtest con look-ahead/lookahead |
| bot-architect | semplicità/manutenibilità del codice | refactor a parità di comportamento |
| exchange-dev | affidabilità connettività (no ordini doppi) | 0 ordini duplicati, reconnect ok |
| devops-sre | uptime del bot | ≥ 99% (24/7) |
| qa-test | regressioni catturate / parità paper↔live | 0 regressioni in produzione |
| security | segreti nel repo / chiavi non conformi | 0 segreti esposti, whitelist attiva |
| performance-analytics | onestà e tempestività dei report | STATO sempre aggiornato coi numeri reali |
| compliance-fiscale | adempimenti coperti (bozze) | 0 scadenze mancate |
| builder-automazioni | automazioni affidabili attive | scheduler orario + alert funzionanti |

> I valori operativi di rischio vivono qui e nelle `protections` delle strategie. Aggiornali col desk.

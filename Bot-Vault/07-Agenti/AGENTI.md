# 👥 AGENTI — l'organigramma di TradeDesk OS

I 20 senior del desk. I mansionari completi sono in `.claude/agents/<nome>.md`; i quaderni di
memoria in `memoria-squadra/<nome>.md`. Qui c'è la mappa per **chi chiamare**.

## Strategia & Trading
| Senior | Chiamalo per |
|---|---|
| **quant-strategist** | trovare/disegnare un edge, segnali, regimi, nuova strategia. |
| **trader-esecuzione** | slippage, maker/taker, TWAP/VWAP, rate limit, qualità di esecuzione. |
| **portfolio-manager** | sizing (Kelly frazionario), allocazione, diversificazione, ribilanciamento. |
| **risk-manager** 🛡️ | drawdown, stop, esposizione, VaR, circuit-breaker, KILL-SWITCH. *Ha veto.* |

## Analisi & Intelligence
| Senior | Chiamalo per |
|---|---|
| **market-analyst** | analisi tecnica, multi-timeframe, volatilità, regime. |
| **onchain-analyst** | flussi exchange, whale, stablecoin, MVRV, funding, OI. |
| **sentiment-analyst** | sentiment social/news, Fear&Greed, narrative. |
| **macro-analyst** | Fed, tassi, DXY, ETF flow, BTC dominance, regolamenti. |
| **news-intelligence** ⭐ | scansione web oraria: news, listing, hack, regolamenti, catalizzatori. |

## Dati & ML
| Senior | Chiamalo per |
|---|---|
| **data-engineer** | pipeline OHLCV/orderbook/alt-data, feature store, qualità dati. |
| **ml-engineer** | modelli ML, walk-forward, anti-overfitting/look-ahead, retraining. |
| **backtest-engineer** | backtest realistici (costi+slippage), Monte Carlo, OOS. |

## Ingegneria & Infra
| Senior | Chiamalo per |
|---|---|
| **bot-architect** | architettura Python, refactor, modularità, performance. |
| **exchange-dev** | ccxt, websocket, reconnect, idempotenza, errori API, rate limit. |
| **devops-sre** | deploy 24/7, uptime, monitoring/alert, Docker, failover, log. |
| **qa-test** | test, casi limite, regressione, parità paper↔live. |

## Fondamenta
| Senior | Chiamalo per |
|---|---|
| **security** 🔒 | chiavi/secret, withdrawal whitelist, sicurezza infra, segreti nel repo. |
| **performance-analytics** | attribuzione PnL, Sharpe/Sortino/win-rate/drawdown, "siamo profittevoli?". |
| **compliance-fiscale** | fisco crypto IT/EU, adempimenti (bozze; validità umana 🔴). |
| **builder-automazioni** | scheduler orario, alert Telegram, n8n, feed, loop autonomo. |

## Come si compone una catena (esempi)
- **Nuovo edge:** quant-strategist → backtest-engineer → risk-manager → portfolio-manager → performance-analytics.
- **Problema sul bot:** qa-test → bot-architect → exchange-dev → security → devops-sre.
- **Catalizzatore news:** news-intelligence → macro/onchain/sentiment → risk-manager.
- **Verso il live:** qa-test (parità) → security (chiavi) → risk-manager → **firma Nicola 🔴**.

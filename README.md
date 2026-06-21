# Tradingbot

Progetto per un trading bot autonomo, sempre attivo (24/7), che analizza in
tempo reale dati di mercato, notizie e segnali alternativi.

> ⚠️ **Stato attuale:** bot funzionante in **paper trading (dry-run)** basato su
> Freqtrade, exchange Kraken. **Live disabilitato di default.** Non usare con
> denaro reale finché non hai completato backtest + paper trading (vedi guida).

## 🚀 Avvio rapido (paper trading)

Richiede Docker. Il bot parte già in dry-run (portafoglio simulato da 50€):

```bash
docker compose pull
docker compose up -d        # avvia il bot (sempre acceso)
docker compose logs -f      # log in tempo reale
```

Guida completa (backtest, dry-run, passaggio al live con 50€):
**[docs/setup-freqtrade.md](docs/setup-freqtrade.md)**.

## Com'è fatto

- **Framework:** [Freqtrade](https://www.freqtrade.io) (Docker, `restart: unless-stopped` → 24/7)
- **Exchange:** Kraken — spot, stake in EUR, **long-only, nessuna leva**
- **Strategia:** `user_data/strategies/StarterStrategy.py` — baseline semplice e
  anti-overfitting (filtro di trend EMA200 + entrata su pullback RSI). Variante
  **long + short** (buy *e* sell) in `StarterStrategyLS.py` + `config-futures.json`
  ⚠️ futures/leva, più rischiosa — vedi doc dedicato.
- **Rischio:** stoploss + trailing + ROI + `protections` (MaxDrawdown,
  StoplossGuard, CooldownPeriod) come circuit breaker
- **Sicurezza:** dry-run di default, chiavi API solo per il live (trade-only, no
  prelievo), segreti fuori dal repo

## Documentazione

- 🛠️ **[Guida operativa](docs/setup-freqtrade.md)** — setup, backtest, paper
  trading e checklist per il passaggio al live.
- 📈 **[Backtest su Solana](docs/backtest-solana.md)** — backtest reale della
  strategia sullo storico di SOL (2021-2024) con risultati, grafico e lettura
  onesta (vs "compra e tieni").
- 🔀 **[Buy & Sell + dati 1h](docs/buy-and-sell-e-dati-1h.md)** — strategia
  long + short (vendita allo scoperto, futures: più rischiosa) con backtest
  reale, e come procurare lo storico a 1 ora (il "ponte GitHub").
- 🚀 **[Miglioramento performance](docs/miglioramento-performance.md)** — la
  variante **trend-following** (`TrendFollowStrategy`) che sui dati di SOL ha
  reso molto di più (con i caveat onesti su overfitting e drawdown).
- 🎯 **[Strategia definitiva SOL](docs/strategia-sol-definitiva.md)** — bot
  **solo su SOL**, Kraken Futures, long+short (`SolLongShortStrategy`), validato
  sui dati 1h reali: perché su SOL conviene il **solo long**, setup futures, PAC
  €500/mese e i compromessi onesti.
- ⚖️ **[Realtà rendimenti e rischio](docs/realta-rendimenti-e-rischio.md)** — la
  lettura ONESTA: perché il "+10.000%" era **lookahead** (numero falso), la
  differenza in-sample vs **fuori campione**, il trade-off leva/drawdown e perché
  la bussola giusta è il **Calmar**. Da leggere prima di credere a qualsiasi numero.
- 🤖 **[Ricerca ML — meta-labeling](docs/ricerca-ml-meta-labeling.md)** — il ramo
  "AI": un filtro LightGBM che prova a scartare i trade peggiori, con **purged
  walk-forward** e **gate fuori campione** (si adotta solo se batte la versione
  semplice). Dataset generabile qui, training sul tuo PC.
- 🔬 **[Validazione 1h multi-asset](docs/validazione-1h-multiasset.md)** — la
  prova del nove su SOL/BTC/ETH a 1h: la strategia **non generalizza** (ottima su
  SOL, perde su BTC). La lezione più importante: niente overfitting.
- 📄 **[Analisi completa](docs/analisi-completa.md)** — analisi approfondita di
  architettura, strategie, gestione del rischio, dati, backtesting, stack
  tecnologico, aspetti legali/fiscali, costi e roadmap di sviluppo.
- 🚀 **[Potenziamento v2](docs/potenziamento-v2.md)** — le 8 leve concrete che
  aumentano il rendimento netto corretto per il rischio (esecuzione, drawdown,
  capitale, alpha robusto, anti-overfitting) con roadmap prioritizzata.
- 🧠 **[Mentalità da esperti](docs/mentalita-esperti.md)** — come ragionano i
  quant, i market maker e i ricercatori che costruiscono davvero questi sistemi:
  i 20 principi e modelli mentali di prim'ordine.

## In sintesi (TL;DR)

- **La complessità non è l'obiettivo.** Ciò che fa la differenza è la gestione
  del rischio, la qualità dei dati e l'assenza di overfitting — non le
  "strategie più complesse del mondo".
- **Approccio incrementale:** Fondamenta → Backtest onesto → Paper trading →
  Risk management → Live con capitale minimo → Estensioni (news/ML).
- **Mai live senza** backtest realistico (con fee e slippage) e un periodo di
  paper trading.
- **Sicurezza prima di tutto:** chiavi API con permessi minimi (no prelievo),
  segreti fuori dal repository, kill-switch sempre disponibile.

## Disclaimer

Questo software è a scopo educativo e di ricerca. Il trading comporta il rischio
concreto di **perdere l'intero capitale**. Nessuna parte di questo progetto
costituisce consulenza finanziaria. Verifica gli obblighi legali e fiscali
applicabili nella tua giurisdizione prima di operare.

## Prossimi passi

1. Esegui il **backtest** su dati Binance e leggi il report (max drawdown, Sharpe).
2. Tieni il bot in **paper trading** per settimane e confrontalo col backtest.
3. Solo dopo, valuta il **live con 50€** seguendo la checklist di sicurezza.

Tutti i dettagli e i comandi sono nella **[guida operativa](docs/setup-freqtrade.md)**.

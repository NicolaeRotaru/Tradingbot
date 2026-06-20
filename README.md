# Tradingbot

Progetto per un trading bot autonomo, sempre attivo (24/7), che analizza in
tempo reale dati di mercato, notizie e segnali alternativi.

> ⚠️ **Stato attuale:** fase di analisi e progettazione. Nessuna logica di
> trading è ancora implementata. **Non usare con denaro reale.**

## Documentazione

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

Vedi la sezione "Decisioni che servono da te per procedere" in fondo all'
[analisi completa](docs/analisi-completa.md#14-conclusione-e-prossimo-passo).

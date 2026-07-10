# 📚 Bot-Vault — Indice della memoria di TradeDesk OS

La memoria del desk. Leggi qui prima di ragionare. Le cartelle:

| Cartella | Contenuto |
|---|---|
| [01-Strategia/](01-Strategia/) | Tesi di edge, mandato del bot, strategie attive. |
| [02-Mercati-Asset/](02-Mercati-Asset/) | Exchange, coppie, struttura di mercato. |
| [03-Dati-Segnali/](03-Dati-Segnali/) | Fonti dati, feature, segnali, indicatori. |
| [04-Modelli-ML/](04-Modelli-ML/) | Modelli, esperimenti, validazione. |
| [05-Rischio-Capitale/](05-Rischio-Capitale/) | Limiti di rischio, sizing, capitale + `KPI-Squadra.md`. |
| [06-Piani/](06-Piani/) | Roadmap miglioramenti, backlog esperimenti. |
| [07-Agenti/](07-Agenti/) | `AGENTI.md` (organigramma) + `CULTURA-SQUADRA.md`. |
| [90-Memoria-AI/](90-Memoria-AI/) | STATO, DECISIONI, AZIONI-IN-ATTESA, Sala, Briefing, news. |

## Dove scrive l'AI
`90-Memoria-AI/` (cruscotto e log) e `memoria-squadra/` (quaderni per ruolo). Il resto del vault
lo cura il desk, registrando le decisioni di peso (🟡/🔴) senza cancellare la storia.

## Il bot in una riga
Trading bot **Freqtrade** su **Kraken**, **paper/dry-run**. Strategia principale:
`EnsembleRegimeStrategy` (15m, commutazione di regime su SOL). Motore di ricerca/backtest in
`research/`. Obiettivo: profitto + efficienza + robustezza, con rischio sempre presidiato.

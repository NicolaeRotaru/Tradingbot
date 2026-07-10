# ⌨️ COMANDI — il menù di TradeDesk OS

Nicola lancia lavori con frasi brevi. Riconoscile anche se scritte in modo diverso ed esegui la
capacità giusta. Resta sempre valido il cancello 🟢🟡🔴: le azioni reali si accodano/firmano.

| Frase (anche varianti) | Cosa fa | File/strumento |
|---|---|---|
| **"fai un giro"** | Leggi STATO (PnL/posizioni/errori), sentinelle e ultime news → scrivi un briefing in `Bot-Vault/90-Memoria-AI/Briefing/AAAA-MM-GG.md` e aggiorna `STATO.md`. | `cervello/giro.md` |
| **"polso orario"** | Mini-giro orario: news + rischio. news-intelligence sintetizza i catalizzatori, risk-manager controlla le sentinelle. | `cervello/polso-orario.md` |
| **"report PnL" / "come va il bot?" / "siamo profittevoli?"** | performance-analytics calcola le metriche oneste dal diario e aggiorna STATO. | `python cervello/diario.py report` |
| **"metriche" / "report KPI"** | Stampa le metriche precise (PnL, win-rate, profit factor, Sharpe, Sortino, max drawdown). | `python cervello/diario.py metriche` |
| **"registra trade …"** | Aggiunge un trade (PAPER) al libro mastro. | `python cervello/diario.py aggiungi '<json>'` |
| **"posizioni aperte"** | Mostra i trade ancora aperti nel diario. | `python cervello/diario.py posizioni` |
| **"scansiona news" / "cosa è successo?" / "catalizzatori"** | Esegui la scansione multi-fonte, dedup, sintesi dei catalizzatori e impatto sul book. | `.claude/workflows/scansione-news.js` + `cervello/news.py` |
| **"backtest X" / "testa la strategia"** | backtest-engineer esegue un backtest realistico (costi+slippage, OOS) sul motore di ricerca. | `research/` · `scripts/backtest_*.py` |
| **"radiografia" / "analizza tutto il bot" / "trova tutti i bug"** | Audit PROFONDO multi-dimensione (strategia/edge, rischio, esecuzione, dati, ML, sicurezza, infra, test), ogni problema verificato → report per gravità in `consegne/audit/`. | `.claude/workflows/radiografia-bot.js` |
| **"audit strategia" / "il nostro edge regge?"** | Caccia agli edge deboli/overfitting, ogni ipotesi verificata sui dati reali. | `.claude/workflows/audit-strategia.js` |
| **"siamo troppo esposti?" / "controlla il rischio" / "kill-switch"** | risk-manager: drawdown, stop, esposizione, circuit-breaker, sentinelle di rischio. | risk-manager · `cervello/sentinelle.md` |
| **"è sicuro?" / "controlla le chiavi" / "segreti nel repo?"** | security: audit segreti/permessi, withdrawal whitelist, config con credenziali deboli. | security · `.gitignore` · `.env.example` |
| **"review della settimana" / "chiusura del mese"** | Cadenze di ritmo: review strategie (settimana), performance+fisco (mese). | `cervello/ritmo.md` |
| **"[reparto], fai X" / "riunione su X"** | Delega al senior giusto o componi la catena (team play). | `.claude/agents/` |
| **"cosa devo decidere?"** | Mostra la coda delle azioni 🔴 in attesa di firma. | `Bot-Vault/90-Memoria-AI/AZIONI-IN-ATTESA.md` |
| **"ok [n]"** | Esegui l'azione approvata n della coda (dopo firma di Nicola). | AZIONI-IN-ATTESA.md |
| **"che comandi ho?"** | Mostra questo file. | `COMANDI.md` |

## Note
- Il comando **avvia** il lavoro; il colore 🟢🟡🔴 decide se eseguire, avvisare o accodare.
- Se Nicola dice *"d'ora in poi quando scrivo X fai Y"*, aggiungi il comando a questo file.
- Tutte le metriche e i backtest usano **dati reali**: mai numeri inventati.

# 🚀 INIZIA QUI — la mappa di TradeDesk OS

Benvenuto nel **secondo cervello** del trading bot. Questo file è la bussola: da qui raggiungi
tutto. Il bot vero (Freqtrade) sta in `user_data/`, `research/`, `scripts/`; **TradeDesk OS** è il
desk quant che lo gestisce e lo migliora.

## 🧭 Cosa leggere per primo
1. **[CLAUDE.md](CLAUDE.md)** — il manuale del desk: chi sei, la regola d'oro 🟢🟡🔴, il ciclo,
   i 20 senior, gli strumenti.
2. **[COMANDI.md](COMANDI.md)** — le frasi rapide ("fai un giro", "report PnL", "scansiona news",
   "backtest X", "radiografia").
3. **[Bot-Vault/00-Index.md](Bot-Vault/00-Index.md)** — l'indice della memoria.

## 🗂️ La mappa
| Dove | Cosa c'è |
|---|---|
| `CLAUDE.md` | Manuale del desk (persona, regole, organigramma). |
| `COMANDI.md` | I comandi rapidi. |
| `.claude/agents/` | I **20 senior** (un file ciascuno). |
| `.claude/workflows/` | `radiografia-bot.js`, `audit-strategia.js`, `scansione-news.js`. |
| `Bot-Vault/` | La **memoria**: strategia, mercati, dati, ML, rischio, piani, agenti. |
| `Bot-Vault/90-Memoria-AI/` | Dove scrive l'AI: STATO, DECISIONI, AZIONI-IN-ATTESA, Sala, Briefing, news. |
| `cervello/` | Il **motore**: `diario.py` (metriche), `news.py` (notizie), i prompt dei rituali. |
| `consegne/` | Gli **artefatti finiti** (report, backtest, dossier, audit). |
| `memoria-squadra/` | I **quaderni** dei 20 senior (memoria append-only per ruolo). |
| `.github/workflows/intel-orario.yml` | Il **cron orario** che scarica le news. |

## ▶️ Primi 3 comandi da provare
```bash
# 1) Le metriche del diario trade (PAPER)
python cervello/diario.py metriche

# 2) Scarica le notizie crypto dell'ora (degrada con grazia se offline)
python cervello/news.py

# 3) Poi, in chat con il desk:  "fai un giro"   →   briefing + STATO aggiornato
```

## 🎯 La prima missione consigliata
Esegui la **radiografia del bot** (`.claude/workflows/radiografia-bot.js`) sul codice reale, poi
porta le **3 mosse a maggior impatto** su profittabilità/efficienza/robustezza da approvare.
Il primo briefing dei punti deboli è già pronto in
`Bot-Vault/90-Memoria-AI/Briefing/` (la radiografia esplorativa iniziale).

## 🛡️ Promemoria di sicurezza
Il bot è in **paper/dry-run**: sperimenta liberamente. **Tutto ciò che muove soldi veri è 🔴** e
serve la firma di Nicola. I segreti stanno in `.env` (mai committato). Vedi il senior `security`.

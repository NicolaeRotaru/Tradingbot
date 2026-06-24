# 🔭 "fai un giro" — perlustrazione del desk

Quando Nicola dice **"fai un giro"**, esegui questo giro di osservazione e lascia un briefing.

## Passi
1. **Osserva lo stato reale**
   - Leggi `Bot-Vault/90-Memoria-AI/STATO.md` (PnL, posizioni, drawdown, stato del bot).
   - Esegui `python cervello/diario.py metriche` per i numeri freschi del diario (PAPER).
   - Controlla gli errori/uptime se disponibili (devops-sre, log Freqtrade).
2. **Controlla le sentinelle** (`cervello/sentinelle.md`): qualcuna è scattata?
   (drawdown oltre soglia, API down, posizione fuori limiti, volatilità anomala, funding/OI estremo,
   catalizzatore news, model drift, exchange outage, kill-switch.)
3. **Leggi le ultime news** (`Bot-Vault/90-Memoria-AI/news/` più recente). Se manca il log dell'ora,
   esegui `python cervello/news.py`. Fai sintetizzare i catalizzatori a `news-intelligence`.
4. **Capisci**: cosa va bene/male su profitto–efficienza–rischio? Quali 1-3 opportunità?
5. **Scrivi il briefing** in `Bot-Vault/90-Memoria-AI/Briefing/AAAA-MM-GG.md`:
   - Situazione (numeri reali) · Opportunità · Azioni proposte (con colore 🟢🟡🔴).
6. **Aggiorna** `Bot-Vault/90-Memoria-AI/STATO.md` (numeri chiave + ultime mosse).
7. Le azioni 🟢 eseguile; le 🟡 falle e avvisa; le 🔴 accodale in `AZIONI-IN-ATTESA.md`.

## Output atteso
Un briefing conciso con **numeri reali** e 1-3 mosse pronte, ciascuna col suo colore.

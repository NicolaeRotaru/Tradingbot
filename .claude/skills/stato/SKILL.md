---
name: stato
description: Mostra come sta andando il bot di trading sul VPS (acceso/spento, trade aperti, profitto, errori, log). Usala quando l'utente chiede "come va il bot", "è acceso?", "quanto sta guadagnando", "stato", "controlla il bot".
---

# Skill: stato del bot

Obiettivo: dire all'utente (principiante, in italiano) in che stato è il bot sul VPS,
in modo semplice e rassicurante.

## Contesto fisso del progetto
- VPS: `root@162.55.51.250` (Hetzner, Ubuntu, bot in Docker 24/7, **dry-run**).
- Due bot possibili (uno alla volta, **stessa porta 8080**):
  - **TREND**: `docker-compose-sol.yml` → strategia `SolLongShortStrategy` (1h).
  - **ENSEMBLE "compra basso/vende alto"**: `docker-compose-ensemble.yml` → `EnsembleRegimeStrategy` (15m).
- Dashboard: tunnel SSH → http://127.0.0.1:8080, login `freqtrader` / `solbot123`.

## IMPORTANTE: questo ambiente NON raggiunge il VPS
Non posso eseguire i comandi sul server da qui. Quindi:
1. Fornisci all'utente i comandi ESATTI pronti da incollare nella finestra SSH del VPS.
2. Invitalo a **incollarmi l'output**: lo interpreto io (Up / Restarting / Exited, errori, trade).

## Comandi da fornire (copia-incolla, uno alla volta)
Collegati al VPS (se non già dentro):
```
ssh root@162.55.51.250
```
Stato del bot (usa il compose giusto — chiedi quale bot sta girando se non è ovvio):
```
cd ~/Tradingbot && docker compose -f docker-compose-sol.yml ps
```
Log recenti / errori:
```
docker compose -f docker-compose-sol.yml logs --tail 30
```

## Come leggere il risultato
- STATUS **`Up`** → bot acceso e sano. Per i numeri (profitto, trade): dashboard FreqUI (skill `telefono`).
- STATUS **`Restarting (N)`** → crasha in loop. Causa più comune già vista = **permessi del log**. Fix pronto:
  ```
  docker compose -f docker-compose-sol.yml down && mkdir -p user_data/logs && chown -R 1000:1000 user_data && docker compose -f docker-compose-sol.yml up -d
  ```
- STATUS **`Exited`** → fermo. Riavvia con `docker compose -f <compose> up -d` e guarda i log.

Se l'utente incolla l'output, interpretalo in parole semplici e proponi il passo successivo.

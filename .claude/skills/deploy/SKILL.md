---
name: deploy
description: Mette o aggiorna il bot di trading sul VPS (cloud 24/7, dry-run). Usala quando l'utente vuole "installare il bot sul server", "aggiornare il bot sul VPS", "metti online il bot", "deploy", "porta le ultime modifiche sul server".
---

# Skill: deploy del bot sul VPS

Obiettivo: portare/aggiornare il bot sul VPS Hetzner, **sempre in DRY-RUN** (soldi simulati).

## Contesto fisso
- VPS: `root@162.55.51.250`, Ubuntu, Docker, repo clonato in `~/Tradingbot`.
- Bot **TREND**: `docker-compose-sol.yml`. Bot **ENSEMBLE** (compra basso/vende alto): `docker-compose-ensemble.yml`.
- Dashboard 127.0.0.1:8080, login `freqtrader`/`solbot123`. Mai esporre 8080; accesso via tunnel SSH (skill `telefono`).

## QUESTO ambiente NON raggiunge il VPS → genera comandi pronti
Non eseguo io sul server. Fornisci all'utente i comandi esatti, un blocco alla volta, e chiedigli di incollare l'output per conferma.

## Prima installazione (one-shot)
```
ssh root@162.55.51.250
```
poi, sul VPS:
```
curl -fsSL https://raw.githubusercontent.com/NicolaeRotaru/Tradingbot/main/scripts/vps-setup.sh | bash
```

## Aggiornamento all'ultima versione
```
cd ~/Tradingbot && git pull origin main && mkdir -p user_data/logs && chown -R 1000:1000 user_data && docker compose -f docker-compose-sol.yml up -d
```
(sostituisci il compose se sta girando l'ensemble: `docker-compose-ensemble.yml`)

## SEMPRE includere il fix permessi
La cartella `user_data` clonata da root NON è scrivibile dall'utente Docker (uid 1000) → il bot va in `Restarting`. Includi sempre prima dell'avvio:
```
mkdir -p user_data/logs && chown -R 1000:1000 user_data
```

## Dopo il deploy
- Verifica: `docker compose -f <compose> ps` → STATUS deve essere **`Up`** (usa skill `stato`).
- Guarda dal telefono/PC: skill `telefono`.
- Resta in **dry-run**. Per il LIVE servono chiavi Kraken (trade-only, NO prelievo) in un `.env` sul VPS — **mai nel repo** — e `dry_run:false`. Solo dopo settimane di dry-run.

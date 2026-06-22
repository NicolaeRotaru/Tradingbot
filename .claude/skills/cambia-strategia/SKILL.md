---
name: cambia-strategia
description: Cambia la strategia attiva del bot sul VPS tra TREND (insegue il trend) ed ENSEMBLE "compra basso/vende alto" (15m). Usala quando l'utente vuole "passare all'altra strategia", "usa il bot che compra basso e vende alto", "torna al trend", "cambia bot".
---

# Skill: cambia strategia sul VPS

Due bot, **una sola porta 8080** → va sempre **fermato uno prima** di avviare l'altro.

| Strategia | Compose | Cosa fa |
|---|---|---|
| **TREND** | `docker-compose-sol.yml` | `SolLongShortStrategy`, 1h, insegue il trend (Chandelier ATR) |
| **ENSEMBLE** (compra basso/vende alto) | `docker-compose-ensemble.yml` | `EnsembleRegimeStrategy`, 15m: mean-reversion sui "cerchi" (compra a `bb_low`, vende a `bb_up`) + trend-long |

## QUESTO ambiente NON raggiunge il VPS → genera comandi pronti

## Passare a ENSEMBLE (compra basso / vende alto)
```
cd ~/Tradingbot && git pull origin main && docker compose -f docker-compose-sol.yml down && mkdir -p user_data/logs && chown -R 1000:1000 user_data && docker compose -f docker-compose-ensemble.yml up -d
```
Verifica: `docker compose -f docker-compose-ensemble.yml ps` (STATUS **`Up`**).

## Tornare a TREND
```
cd ~/Tradingbot && docker compose -f docker-compose-ensemble.yml down && docker compose -f docker-compose-sol.yml up -d
```

## Note
- Sempre **dry-run**. Dashboard su 127.0.0.1:8080 (login `freqtrader`/`solbot123`).
- Dopo il cambio, gli indicatori sul grafico cambiano: l'ensemble mostra la linea **VERDE `bb_up`** (dove vende alto = i cerchi) e la **ROSSA `chan_stop`** (lo stop del trend).
- Se dopo il cambio va in `Restarting`: è il fix permessi (già incluso sopra) — vedi skill `stato`.

# 05 — Rischio & Capitale

## Capitale (paper)
- Spot: `dry_run_wallet = 50` EUR, `stake_amount = 20`, `max_open_trades = 2`.
- Futures (ensemble): `dry_run_wallet = 500` USD, `stake_amount = unlimited`, `max_open_trades = 1`, leva 1x.

## Limiti di rischio (presidiati da risk-manager)
- **Stop**: `stoploss` di strategia (es. −5% ensemble) + `custom_stoploss` (Chandelier per il trend,
  −2% per la mean-reversion).
- **Protections** (circuit breaker): `MaxDrawdown` (es. 25% / lookback 672 candele), `StoplossGuard`,
  `CooldownPeriod`.
- **Attenzione**: `stoploss_on_exchange = false` → se il bot/VPS cade, nessuno stop lato exchange.
  Da valutare per il live (vedi briefing radiografia).

## Regola ferrea
Ogni cambiamento di **rischio/capitale reale** è 🔴: si accoda in `90-Memoria-AI/AZIONI-IN-ATTESA.md`
e parte solo con la firma di Nicola. In paper si può sperimentare.

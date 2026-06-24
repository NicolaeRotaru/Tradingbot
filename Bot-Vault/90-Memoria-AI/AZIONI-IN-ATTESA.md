# ⏳ AZIONI-IN-ATTESA — coda delle azioni 🔴 pronte (servono la firma di Nicola)

> Ogni azione 🔴 va qui COMPLETA e pronta a partire. Parte solo con "ok [n]" di Nicola.
> Formato: numero · cosa · perché · cosa serve da Nicola · chi l'ha preparata.

### 1 · 🔴 Stop lato exchange + whitelist prelievi (prerequisito LIVE)
- **Cosa:** prima di qualsiasi passaggio a live: (a) impostare `"stoploss_on_exchange": true` nei
  config/strategie; (b) configurare su Kraken la **withdrawal whitelist** (solo indirizzi ammessi)
  con chiavi API **solo-trading** (no prelievo); (c) `listen_ip_address:"127.0.0.1"` + SSH tunnel.
- **Perché:** oggi lo stop è solo software (`config.json:67`) → se il VPS cade in live la posizione
  resta scoperta; e senza whitelist chi ottiene le chiavi può prelevare. Vedi radiografia 2026-06-24.
- **Cosa serve da Nicola:** la firma per andare verso il live (è 🔴). In **paper non serve** e non
  cambia nulla: resta pronta per quando deciderai il live.
- **Preparata da:** risk-manager + security + exchange-dev · **Stato:** in attesa di firma.

---

_(Nessun'altra azione in coda.)_

Esempi di azioni che finiranno qui (NON eseguite senza firma):
- Passaggio da paper a **live** (dry_run:false) con capitale reale.
- Cambio di **parametri di rischio/capitale** o di **leva**.
- **Prelievi/withdrawal** dall'exchange.
- **Deploy in produzione live** del bot.
- Generazione/rotazione di **chiavi API** reali.

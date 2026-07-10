# 🥁 ritmo.md — le cadenze del desk (crypto è 24/7)

Il ritmo è il battito che tiene vivo il desk. Ogni cadenza chiede: **cosa · numeri reali · blocchi · prossimo passo.**

## 🕐 POLSO ORARIO (ogni ora) — news + rischio
Vedi `cervello/polso-orario.md`. news-intelligence sintetizza i catalizzatori, risk-manager
controlla le sentinelle. Log news automatico via cron.

## 📅 REVIEW GIORNALIERA — PnL, posizioni, errori
- `python cervello/diario.py report 1g` → PnL e metriche del giorno (PAPER).
- Posizioni aperte, stop attivi, errori/uptime del bot.
- performance-analytics aggiorna `STATO.md`. Drawdown sotto controllo? Sentinelle ok?

## 🗓️ REVIEW SETTIMANALE — strategie
- Le strategie attive reggono? Confronto performance reale vs backtest (scostamenti).
- quant-strategist + backtest-engineer + risk-manager: una strategia va ritarata, messa in pausa
  o promossa? (Promozione a LIVE = 🔴, firma Nicola.)
- Retrospettiva: cosa abbiamo imparato? Aggiorna i quaderni `memoria-squadra/`.

## 🌙 CHIUSURA MENSILE — performance + fisco
- performance-analytics: report mensile onesto (Sharpe/Sortino/Calmar/drawdown, attribuzione PnL).
- compliance-fiscale: bozza registro fiscale dal diario (validità umana 🔴).
- portfolio-manager + risk-manager: il capitale è allocato bene? Limiti ancora giusti?
- Aggiorna `Bot-Vault/01-Strategia/`, `05-Rischio-Capitale/`, `06-Piani/`.

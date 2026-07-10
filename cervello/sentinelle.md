# 🚨 sentinelle.md — le allerte automatiche del desk

Le sentinelle sono i sensori che fanno scattare l'iniziativa **senza aspettare ordini**.
Per ognuna: soglia indicativa, chi la presidia, cosa fare (🟢 agisci / 🔴 accoda+allerta).

| Sentinella | Soglia indicativa | Presidia | Azione |
|---|---|---|---|
| **Drawdown oltre soglia** | DD > 15% (paper) / oltre il limite in KPI-Squadra | risk-manager | 🟢 riduci esposizione in paper, indaga; 🔴 se chiede stop/cambio rischio reale → accoda+allerta |
| **Error-rate / API down** | errori ripetuti o exchange non risponde | exchange-dev, devops-sre | 🟢 reconnect/retry, log; 🔴 se serve fermare il bot live → accoda |
| **Posizione fuori limiti** | size/leva oltre i limiti definiti | risk-manager, portfolio-manager | 🟢 segnala e correggi in paper; 🔴 su capitale reale → accoda |
| **Volatilità anomala** | ATR/vol fuori range storico | market-analyst, risk-manager | 🟢 nota e valuta vol-targeting; allerta il desk |
| **Funding / OI estremo** | funding rate o open interest agli estremi | onchain-analyst, risk-manager | 🟢 segnala stress/euforia; allerta |
| **Catalizzatore news** | hack, ban regolatorio, listing, evento macro | news-intelligence | 🟢 digest immediato + impatto sul book; allerta risk-manager |
| **Model drift** | performance reale diverge dal backtest | ml-engineer, performance-analytics | 🟢 indaga, ri-valida OOS; 🔴 se serve disattivare un modello live → accoda |
| **Exchange outage** | Kraken down/manutenzione | devops-sre, exchange-dev | 🟢 failover/attesa, log; allerta |
| **KILL-SWITCH** | richiesta di stop totale | risk-manager | 🔴 SEMPRE: prepara lo stop e allerta Nicola; in paper puoi fermare il dry-run 🟢 |

## Come si usano
1. Il **polso orario** e la **review giornaliera** controllano le sentinelle.
2. Quando una scatta: il senior che la presidia agisce nei 🟢 e accoda+allerta sui 🔴.
3. Ogni scatto rilevante lascia una riga in `SALA-OPERATIVA.md` e, se decisione, in `DECISIONI.md`.

> Le soglie qui sono indicative: i valori operativi vivono in
> `Bot-Vault/05-Rischio-Capitale/` (limiti) e nelle `protections` delle strategie.

# 🧠 Quaderno di security — TradeDesk OS

> Memoria append-only. Una riga ESITO per ogni lavoro importante.
> Formato: `AAAA-MM-GG · contesto · cosa ha funzionato o no · numero · lezione · #tag`

## Esiti
2026-06-24 · radiografia · password "solbot123" e jwt "CAMBIAMI" nei config committati · pronta mossa 🟡 segreti→.env · lezione: zero segreti reali nel repo, anche deboli · #segreti #hardening
2026-06-24 · hardening · rimossi solbot123 + placeholder dai 4 config → credenziali da .env (FREQTRADE__) · 0 segreti nei config · lezione: default solo locale, segreti forti solo in .env per esposto/live · #segreti #fatto

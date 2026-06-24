# 🩻 Radiografia del bot — 2026-06-24

**Metodo:** audit profondo READ-ONLY su 10 dimensioni (3 esploratori in parallelo) +
**verifica adversariale** dei punti contestati contro i file reali. Ogni numero è letto da
`results/research/summary.json` o dai file config/codice (nessun numero inventato).

**Verdetto in una riga:** il bot è una base onesta e conservativa, **sicura in paper**. I rischi
veri sono tutti sul **passaggio a LIVE** e sulla **robustezza dell'edge** (overfit su SOL). Nessuna
sorpresa catastrofica in dry-run.

---

## ✅ Verifiche (cosa ho confermato, refutato, corretto)
| Esito | Affermazione | Prova |
|---|---|---|
| ❌ **REFUTATO** | "Look-ahead nelle Bollinger Bands" | `research/engine.py:65`: `ep = w_target[i-1]` (peso barra precedente) × rendimento barra `i`. Segnale già shiftato di 1 barra → nessun leakage. Il docstring (riga 12) lo dice: "shift gestito internamente". **Falso positivo.** |
| ⚠️ **CORRETTO** | "BTC in-sample Sharpe +1,44 / Calmar 1,97" | Quei numeri sono di **SOL**. BTC era negativo **già in-sample** (Trend long IS Sharpe −0,13). ETH IS +0,45 → OOS −0,37. |
| ⚠️ **RIDIMENSIONATO** | "exit_profit_only blocca lo stop" | `custom_stoploss` scatta comunque (−2% MR / Chandelier). Resta vero solo il **ritardo delle uscite a segnale** in perdita → MINORE. |
| ⚠️ **RIDIMENSIONATO** | "93 candele mancanti su 48.000" | Reale: 47.907 barre (2021-01-01 → 2026-06-20), ~43 gap (~0,08%). MINORE. |
| ✅ CONFERMATO | `stoploss_on_exchange:false` ovunque | `user_data/config.json:67` + order_types delle strategie. |
| ✅ CONFERMATO | Segreti deboli committati | `config-ensemble.json:69` / `config-sol-krakenfutures.json:69` `"password":"solbot123"`; `config.json:76-77` jwt/ws "CAMBIAMI". |
| ✅ CONFERMATO | Overfitting / edge solo su SOL | `deflated_sharpe`: SOL 0,0028 · BTC 3,4e-6 · ETH 0,00044 (n_trials=400, n_folds=6). |
| ✅ CONFERMATO | Nessun test/CI sul bot | Nessun `tests/`, solo `research/_smoke.py` manuale. |

---

## 🔴 BLOCCANTI — solo per il passaggio a LIVE (in paper NON mordono)

### B1 · `stoploss_on_exchange: false` su tutte le strategie e config
**Prova:** `user_data/config.json:67`; `EnsembleRegimeStrategy.py:67`; `StarterStrategy.py:~100`;
`TrendFollowStrategy.py:~63`.
**Impatto (live):** lo stop è solo software. Se il VPS cade (crash/OOM/disconnect), la posizione
resta aperta senza protezione lato exchange; su futures → rischio liquidazione.
**Fix:** `"stoploss_on_exchange": true` prima del live. *(risk-manager + exchange-dev)*

### B2 · Withdrawal whitelist assente + api_server esposto con password debole
**Prova:** nessuna whitelist Kraken documentata; `api_server.listen_ip_address:"0.0.0.0"`
(`config.json:72`) con `"password":"solbot123"` (`config-ensemble.json:69`).
**Impatto (live):** chi ottiene le chiavi potrebbe prelevare; FreqUI raggiungibile dall'esterno se
esposta su VPS senza tunnel.
**Fix:** whitelist prelievi su Kraken + chiavi solo-trading; `listen_ip_address:"127.0.0.1"` + SSH
tunnel; password/jwt da `.env`. *(security)*

### B3 · Nessun test di parità paper↔live
**Prova:** nessun test che confronti il comportamento paper vs backtest/live.
**Impatto (live):** comportamento divergente (slippage, fee, ordini doppi al reconnect) scoperto
solo coi soldi veri.
**Fix:** test di parità + checklist di promozione. *(qa-test)*

---

## 🟠 SERI — da affrontare ora (in paper)

### S4 · Overfitting: l'edge regge solo su SOL, instabile, deflated_sharpe ≈ 0
**Prova (numeri reali):**
| Asset | WFO OOS total | Sharpe | Profit factor | deflated_sharpe |
|---|---|---|---|---|
| **SOL** | **+42%** | 0,49 | 1,03 | 0,0028 |
| **BTC** | **−3,7%** | −0,12 | 0,997 | 0,0000034 |
| **ETH** | **−11%** | −0,27 | 0,995 | 0,00044 |

Fold scelti su SOL (instabilità): Sharpe −0,34 / −0,82 / **+2,47** / +0,38 / +0,15 / **−2,00**.
Il `deflated_sharpe` ~0 (con 400 trial) dice che la probabilità che l'edge sia reale e non fortuna
da ricerca multipla è bassissima. **SOL è l'unico profittevole, e fragile.**
**Fix:** **gate OOS obbligatorio** (vedi mossa 🟢 sotto). Non operare BTC/ETH con questi parametri.
*(quant-strategist + backtest-engineer)*

### S5 · Segreti deboli nei config committati
**Prova:** `config-ensemble.json:69` `"password":"solbot123"`; `config-sol-krakenfutures.json:69`
idem; `config.json:76-77` jwt/ws "CAMBIAMI".
**Fix:** spostare in `.env` via `FREQTRADE__API_SERVER__...` (il `.env.example` lo prevede già).
*(security — mossa 🟡)*

### S6 · Nessuna suite di test / CI sul bot
**Prova:** nessun `tests/`, nessun `pytest`, CI solo per le news (`intel-orario.yml`).
**Fix:** `tests/` con smoke su strategie + diario + news, e un gate OOS in CI. *(qa-test)*

### S7 · Costi di backtest semplificati
**Prova:** `research/engine.py:30` `cost = 0.0010` (0,10%/lato unico).
**Impatto:** non distingue maker/taker reali Kraken (taker spot ~0,26%). I profitti marginali
(PF ~1,03) sono sensibili a questa assunzione.
**Fix:** modellare fee maker/taker separate e ri-validare i margini. *(trader-esecuzione + backtest-engineer)*

---

## 🟡 MINORI
- **M8** Telegram/alert disabilitati in tutti i config; nessun healthcheck Docker. *(devops-sre)*
- **M9** `cancel_open_orders_on_exit:false` → rischio ordini orfani al riavvio (live). *(exchange-dev)*
- **M10** `tradable_balance_ratio` 0,95–0,99 → buffer basso per fee/errori. *(portfolio-manager)*
- **M11** ~43 barre mancanti su 47.907 (~0,08%): aggiungere un check gap, ma impatto trascurabile. *(data-engineer)*

---

## 🎯 Le 3 mosse a maggior impatto
1. 🟢 **Gate anti-overfitting OOS** — regola scritta: nessuna strategia/modello va in paper "promosso"
   o verso il live senza walk-forward OOS positivo **e** prova su un asset diverso da SOL.
   → eseguita: vedi `Bot-Vault/01-Strategia/GATE-OOS.md`.
2. 🟡 **Hardening segreti** — config che leggono password/jwt/ws da `.env`, in un branch, senza
   toccare il live. → pronta da preparare al via di Nicola.
3. 🔴 **Stop lato exchange + whitelist prelievi** — `stoploss_on_exchange:true` + whitelist Kraken.
   → **accodata** in `Bot-Vault/90-Memoria-AI/AZIONI-IN-ATTESA.md`, parte solo con la firma di Nicola.

> Priorità: in **paper** conta la **mossa 1** (robustezza dell'edge) e la **2** (igiene segreti).
> Le **B1–B3** sono prerequisiti del LIVE: si chiudono prima di passare a soldi veri.

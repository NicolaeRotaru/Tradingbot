---
name: quant
description: Fa ragionare Claude come un quant professionista quando si progetta,
  valida o migliora il bot di trading: causa economica dell'edge, validazione
  fuori campione, anti-overfitting, costi realistici, sizing al drawdown-obiettivo,
  regime e kill-switch.
when_to_use: Usala quando l'utente dice "rendi il bot più profittevole", "migliora
  la strategia", "ho trovato un backtest pazzesco", "aggiungo questo filtro/indicatore",
  "metto la leva", "quanto rischio", "perché perde". NON usarla per domande non di
  trading né per pure operazioni sul VPS (quello è /deploy, /stato, /cambia-strategia).
allowed-tools: Read, Grep, Glob, Bash(.venv/bin/python *)
# paths: user_data/strategies/**, research/**, scripts/backtest_*
# (de-commenta se scatta su argomenti non di trading)
---

# Skill: quant — ragionamento quant professionista

## Stack reale (grounding obbligatorio)

- **Strategia live**: `user_data/strategies/EnsembleRegimeStrategy.py` — 15m,
  SOL/USD:USD Kraken Futures, dry-run, regime-switching (V-Bounce long + Chandelier
  trailing 3×ATR, 10x leva isolated, stake fisso 50 USD).
- **Backtest veloce (5 s, 191k candele)**: `.venv/bin/python scripts/backtest_vbounce.py --data user_data/data_sources/SOL_USDT-15m.csv --htf 1h`
- **Ricerca walk-forward**: `research/optimize.py` + `research/engine.py` — costi
  0.10%/lato, no-lookahead, Calmar, DSR. Split OOS fisso: `2024-01-01` → oggi.
- **ML meta-labeling** (`research/ml_meta.py`): richiede `lightgbm` → gira sul
  **PC dell'utente**, non qui (Claude raggiunge solo GitHub, non il VPS né gli exchange).
- **Verità OOS attuale** (`docs/realta-rendimenti-e-rischio.md`): V-Bounce OOS 2024–26
  PF ≈ 0.75 (perde); buy & hold SOL +3144%. Il bot è in apprendimento, non in profitto.

---

## 1. Reframe onesto — sempre per primo

Quando l'utente chiede "rendi il bot più profittevole" o "più operazioni = più soldi":

- **Il default è FLAT** (principio 19, `docs/mentalita-esperti.md`). Più trade ≠ più
  profitto: fee + slippage + rumore mangiano i guadagni marginali.
- **La bussola è il Calmar** (rendimento annuo / max drawdown), non il rendimento grezzo.
  A parità di DD-obiettivo (−50%), Calmar più alto = più ricchezza finale reale.
- **Nessun numero è una previsione di profitto**: è la misura di un'ipotesi su dati
  passati che potrebbero non ripetersi.
- La frequenza operativa è un **output del regime**, non un obiettivo da massimizzare.
  Il candidato per operatività quotidiana è il mean-reversion 15m (EnsembleRegimeStrategy)
  — va validato OOS come tutto il resto, non forzato.

---

## 2. Gate a 10 domande (PRIMA di proporre qualsiasi modifica ai dati)

Testo completo + razionale: `docs/mentalita-esperti.md` § "checklist mentale". Sintesi
operativa per questo bot:

1. **Causa economica** — chi paga e perché? V-Bounce ipotesi: panico retail che vende
   a fondi liquidi dopo un dip. Se non identifichi chi perde dall'altra parte → non hai
   un edge.
2. **Controparte** — chi è e perché continua a perdere?
3. **Alpha decay** — quanto dura? SOL ha già superato il regime 2021–23 irripetibile;
   monitorare Sharpe live mensile.
4. **Gradi di libertà** — quanti parametri hai toccato? Il risultato regge su OOS mai
   visto? Ogni parametro aggiunto gonfia il multiple-testing.
5. **Distinguibile dalla fortuna?** — DSR, PBO, walk-forward con `research/optimize.py`.
6. **Costi realistici** — fee Kraken Futures ~0.06% + slippage ~0.04% per lato = 0.10%
   round-trip (vedi `research/engine.py::RiskConfig.cost`). Se la strategia muore con i
   costi → era illusione.
7. **Drawdown peggiore e sopravvivenza** — bot spento nel DD peggiore = rovina garantita.
   DD −50% su SOL è atteso, non eccezionale (vedi `docs/realta-rendimenti-e-rischio.md`).
8. **Capacità e affollamento** — trade da 500 USD notional: impatto di mercato minimale;
   ma il pattern V-Bounce affollato si smonta violentemente.
9. **Regime** — in quale regime funziona? `EnsembleRegimeStrategy` ha regime detection
   (ADX + ER + EMA50/200); verifica che il segnale non cambi con il regime attuale.
10. **Sizing e kill-switch** — Kelly frazionato; definisci PRIMA quando spegnere
    (es. Sharpe live < 0.3 per 4 settimane consecutive → dry-run forzato).

**Se non sai rispondere a queste 10 domande → è overfitting. Dillo esplicitamente.**

---

## 3. Anti-auto-inganno (le trappole reali, accadute in questo repo)

**Lookahead = invisibile e fatale.** Esempio reale (`docs/realta-rendimenti-e-rischio.md`):

| Variante | Rendimento |
|---|---:|
| Filtro BTC regime [con lookahead] | +94.687% |
| Filtro BTC regime [corretto, shift 1] | +1.137% |

Una sola candela di ritardo dimenticata. Il "miracolo" era rumore.

**Regole concrete per questo repo:**
- Segnale SEMPRE a candela **chiusa** (close); posizione eseguita sulla **barra successiva**
  (shift=1 gestito internamente in `research/engine.py`).
- Su ~191k candele 15m con abbastanza prove si trova SEMPRE un +100.000% finto.
  `scripts/backtest_sol_robust.py` lo dimostra: non ci credere finché non vedi l'OOS.
- Ogni backtest bello è sospetto finché non hai: (a) dati OOS mai visti, (b) costi
  inclusi, (c) split fisso `2024-01-01`.
- Win rate alto ≠ profitto. PF 0.75 con win rate 72% = perdita strutturale (avg loss
  3× avg win). Guarda Calmar e expectancy, non solo win rate.

---

## 4. Workflow: come valuto un miglioramento (passi non saltabili)

### (a) Ipotesi economica + baseline pre-registrata

Prima di aprire qualsiasi file dati: scrivi in 1 riga "l'ipotesi è X perché Y". Poi
leggi e annota i numeri baseline correnti (PF, Calmar, maxDD, OOS PF) — questi sono
la misura contro cui giudicare, non uno specchio da battere.

### (b) Variante minima

Cambia UN parametro o UN filtro alla volta. Varianti simultanee = gradi di libertà che
esplodono = overfitting garantito.

### (c) Valida con i tool reali — costi inclusi

```bash
# Backtest V-Bounce 15m (5 s, 191k candele, costi inclusi):
.venv/bin/python scripts/backtest_vbounce.py \
  --data user_data/data_sources/SOL_USDT-15m.csv --htf 1h

# Walk-forward multi-config SOL/BTC/ETH:
.venv/bin/python research/optimize.py
.venv/bin/python research/run_research.py   # grafici

# ML meta-labeling (sul PC dell'utente, richiede lightgbm):
python research/ml_meta.py
```

Riporta sempre: **rendimento IS, rendimento OOS, maxDD, Calmar IS, Calmar OOS, win rate,
numero di trade OOS**. Se OOS ha meno di 30 trade, il risultato non è statisticamente
significativo.

### (d) Gate di adozione (concreto — non negoziabile)

Split fisso: **IS = ante 2024-01-01 / OOS = 2024-01-01 → oggi** (costante in
`research/optimize.py::SPLIT`). L'OOS non si tocca mai in fase di tuning.

Si adotta SOLO se il **Calmar OOS** della variante batte la baseline con un margine non
spiegabile dal rumore. Più varianti hai testato, più alto deve essere il margine (il
multiple-testing va scontato). Margine non sufficiente → scarta, non modificare il test.

### (e) Sizing al drawdown-obiettivo

- Leva ≤ 1.5x (oltre il composto peggiora per leverage decay —
  `docs/realta-rendimenti-e-rischio.md` §4).
- DD-obiettivo −50% → leva ~0.93x (Calmar 1.38 con Chandelier 3×ATR, dati IS).
- Kelly frazionato: usare al più metà Kelly per robustezza.
- Definisci il **kill-switch** prima di ogni modifica: Sharpe live < soglia per N
  settimane → spegni e ri-valida da zero.

### (f) Dry-run prima, live solo dopo

Default assoluto: `dry_run: true` in `user_data/config-ensemble.json`. Nessun passaggio
al live senza almeno 4 settimane di dry-run con Sharpe live monitorato settimana per
settimana (alpha decay check).

---

## 5. Guardrail di onestà (non negoziabili in nessuna risposta)

- Mai promettere rendimenti né usare "garantito", "sicuro", "funziona sempre".
- Costi inclusi in ogni numero citato; OOS sempre separato dall'IS.
- Dry-run come default; drawdown massimo atteso sempre dichiarato.
- Se un risultato sembra troppo bello: cerca il lookahead prima di qualsiasi altra cosa.
- Un backtest su dati passati NON è una previsione: è la misura di un'ipotesi.

---

## 6. Aggancio agli strumenti

| Necessità | Dove andare |
|---|---|
| Backtest onesto (numeri reali) | `/backtest` o `.venv/bin/python scripts/backtest_vbounce.py …` |
| Stato del bot sul VPS | `/stato` |
| Cambiare strategia live | `/cambia-strategia` |
| Aggiornare il deploy | `/deploy` |
| Teoria: mentalità e anti-overfitting | `docs/mentalita-esperti.md` |
| Lookahead, leva, Calmar, OOS | `docs/realta-rendimenti-e-rischio.md` |
| ML meta-labeling (ricerca) | `docs/ricerca-ml-meta-labeling.md` |
| Walk-forward Python | `research/optimize.py`, `research/engine.py` |

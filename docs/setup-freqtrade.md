# Guida operativa — dal setup al paper trading (e poi al live)

> Bot crypto basato su **Freqtrade**, su **Kraken**, **paper-first**.
> Segui i passi **in ordine**. Non saltare il paper trading.

---

## 0. Cosa ti serve

- **Docker** e **Docker Compose** installati (è il modo più semplice e "sempre acceso").
- Per il **dry-run (paper)**: nient'altro. Nessuna chiave, nessun deposito.
- Per il **live** (dopo): un conto Kraken verificato (KYC) e 50€ depositati via SEPA.

> Tutti i comandi vanno lanciati dalla cartella del progetto (quella con
> `docker-compose.yml`).

---

## 1. Avvio rapido in PAPER TRADING (dry-run)

Il bot è già configurato in dry-run (`"dry_run": true` in `user_data/config.json`):
fa trading simulato su dati **reali** di Kraken, con un portafoglio finto da 50€.

```bash
# scarica l'immagine ufficiale di Freqtrade
docker compose pull

# avvia il bot in background (resta sempre acceso)
docker compose up -d

# guarda i log in tempo reale
docker compose logs -f
```

Per fermarlo: `docker compose down`.

> ⚠️ Prima di esporre FreqUI, apri `user_data/config.json` e **cambia** i tre
> valori `CAMBIAMI_...` nella sezione `api_server` (password, jwt_secret_key,
> ws_token). FreqUI è raggiungibile solo da locale su http://127.0.0.1:8080.

---

## 2. Backtest (validare la strategia sul passato)

Il backtest va fatto su **dati Binance** (abbondanti), non su Kraken: Kraken
fornisce solo 720 candele storiche. La logica della strategia è identica.

```bash
# 1) scarica i dati storici (Binance, timeframe 1h)
docker compose run --rm freqtrade download-data \
  --exchange binance -t 1h --timerange 20230101- \
  --config /freqtrade/user_data/config-backtest-binance.json

# 2) lancia il backtest
docker compose run --rm freqtrade backtesting \
  --strategy StarterStrategy \
  --config /freqtrade/user_data/config-backtest-binance.json \
  --timeframe 1h --timerange 20230101-
```

**Cosa guardare nel report** (non solo il profitto!):
- **Max drawdown** — quanto avresti sofferto. Più basso è, meglio è.
- **Sharpe / Sortino** — rendimento per unità di rischio.
- **Profit factor**, **win rate**, numero di trade.
- Conferma che **fee e slippage** siano inclusi (Freqtrade li modella in automatico).

**Walk-forward "a mano"** (anti-overfitting): ripeti il backtest su periodi
diversi (es. `--timerange 20230101-20231231`, poi `20240101-`) e verifica che il
comportamento sia coerente. Se funziona solo su un periodo, **è overfitting**.

> ❗ Non ottimizzare i parametri finché il backtest è "perfetto": staresti
> adattando il rumore del passato. Una baseline onesta batte una curva-fittata.

---

## 3. Lasciare il bot in dry-run e osservare

Tieni il bot in paper trading (`docker compose up -d`) per **settimane**. Obiettivo:
verificare che i risultati live assomiglino al backtest. Se divergono molto, c'è
un bug o un bias nel backtest. **Questo passo non si salta.**

Monitoraggio:
- **FreqUI**: http://127.0.0.1:8080 (login con le credenziali del config).
- **Log**: `docker compose logs -f`.
- **Telegram** (opzionale): vedi sezione 5.

---

## 4. Passaggio al LIVE con 50€ (solo dopo la validazione)

> Vai live **solo** se: il backtest è onesto, il dry-run gli assomiglia, e hai
> capito come fermare il bot. Con 50€ l'obiettivo è **imparare e non perdere**,
> non fare reddito.

**Checklist di sicurezza:**

1. **Deposita** 50€ su Kraken via **bonifico SEPA** (commissioni minime).
2. **Crea una chiave API** su Kraken con permesso **SOLO "Trading"**.
   **MAI** il permesso di **Prelievo/Withdrawal**. Aggiungi una **IP whitelist**.
3. **Inserisci le chiavi** con UNO di questi due metodi (non entrambi):
   - **`.env`**: `cp .env.example .env`, compila `FREQTRADE__EXCHANGE__KEY/SECRET`,
     poi **decommenta** `env_file: - .env` in `docker-compose.yml`.
   - **`config-private.json`**: `cp config-private.example.json config-private.json`,
     compila le chiavi e aggiungi `-c /freqtrade/user_data/config-private.json` al
     comando (sposta il file in `user_data/`).
4. **Disattiva il paper trading**: metti `"dry_run": false` (nel `.env` o nel
   config-private).
5. Avvia: `docker compose up -d` e **osserva i primi trade da vicino**.

> 🔴 **Kill-switch**: per fermare tutto subito → `docker compose down`. Da FreqUI
> puoi mettere il bot in pausa (`/stop`) o forzare l'uscita dai trade.

---

## 5. (Opzionale) Notifiche Telegram

Per ricevere avvisi su ogni trade ed errore:
1. Crea un bot Telegram con **@BotFather** → ottieni il `token`.
2. Ottieni il tuo `chat_id`.
3. Compila i valori `FREQTRADE__TELEGRAM__*` nel `.env` (o la sezione `telegram`
   del config) e imposta `enabled: true`.

---

## 6. Comandi utili

```bash
docker compose ps              # stato del bot
docker compose logs -f         # log in tempo reale
docker compose restart         # riavvia
docker compose down            # ferma (kill-switch)
docker compose pull            # aggiorna l'immagine Freqtrade

# elenco strategie viste da Freqtrade
docker compose run --rm freqtrade list-strategies

# verifica/validazione della configurazione
docker compose run --rm freqtrade show-config \
  --config /freqtrade/user_data/config.json
```

---

## 7. Promemoria onesto

- Il **backtest non è una previsione di profitto**: è un test di ipotesi.
- La maggior parte dei bot retail **perde**. Il tuo vantaggio è la **disciplina**:
  rischio controllato, niente leva, paper prima del live.
- Aggiungi complessità (news/NLP, ML) **solo** se dimostra di pagare
  *out-of-sample*. Vedi `docs/potenziamento-v2.md`.

# Avviare il bot in DRY-RUN su Windows (Docker + FreqUI)

Guida per far girare il bot SOL in **paper trading** (soldi **simulati**, nessun rischio
reale) sul tuo **PC Windows**, con **Docker Desktop** e la dashboard web **FreqUI**.

> 🎯 Obiettivo del dry-run: vedere il bot operare **dal vivo** sui dati reali di Kraken,
> e confrontarlo col backtest, **prima** di mettere un solo euro vero.
>
> 💶 Portafoglio simulato: **500**. Niente chiavi API, niente soldi reali, leva 1x.

---

## 1. Installa Docker Desktop

1. Scarica **Docker Desktop for Windows**: https://www.docker.com/products/docker-desktop/
2. Installalo (accetta l'attivazione di **WSL2** se te lo chiede) e **riavvia** il PC se richiesto.
3. Apri **Docker Desktop** e aspetta che in basso a sinistra l'icona diventi **verde**
   ("Engine running"). Lascialo aperto: serve acceso mentre il bot gira.

Verifica veloce (apri **PowerShell** e digita):
```powershell
docker --version
```
Deve stampare una versione (es. `Docker version 27.x`).

---

## 2. Scarica il progetto

Hai due modi:

**A) Con Git** (consigliato, così aggiorni facilmente):
```powershell
git clone https://github.com/NicolaeRotaru/Tradingbot.git
cd Tradingbot
```

**B) Senza Git:** vai sulla pagina GitHub del progetto → bottone verde **Code** → **Download ZIP**,
estrai la cartella, poi in PowerShell entra nella cartella estratta:
```powershell
cd C:\Users\TUO_NOME\Downloads\Tradingbot
```

---

## 3. Imposta la TUA password per la dashboard (richiesto)

Per sicurezza nel repo **non c'è nessuna password vera**. Apri
`user_data/config-sol-krakenfutures.json` con il Blocco Note e nella sezione
`api_server` sostituisci `"CAMBIA_QUESTA_PASSWORD"` con una password tua:

```json
"username": "freqtrader",
"password": "la_tua_password_qui"
```

Userai `freqtrader` + questa password per entrare in FreqUI (passo 5). La chiave di
sicurezza interna (`jwt_secret_key`) la genera **Freqtrade da solo** a ogni avvio: non
devi impostare nulla. La dashboard è comunque legata a **127.0.0.1** (solo il tuo PC).

---

## 4. Avvia il bot (dry-run)

Dentro la cartella del progetto, in PowerShell:
```powershell
docker compose -f docker-compose-sol.yml up -d
```
La prima volta scarica l'immagine di Freqtrade (qualche minuto). `-d` = gira in background.

Controlla che sia partito e guarda i log dal vivo:
```powershell
docker compose -f docker-compose-sol.yml logs -f
```
All'avvio il bot scarica ~400 candele orarie di storico dal **feed pubblico di Kraken
Futures** (serve a calcolare EMA200/400), poi inizia a "osservare" SOL e ad aprire trade
**simulati** quando scattano le condizioni. Per uscire dai log premi **Ctrl + C** (il bot
continua a girare lo stesso).

---

## 5. Apri la dashboard FreqUI

Nel browser vai su:

**http://127.0.0.1:8080**

Fai login con utente/password del punto 3. Da qui vedi:

- **Saldo simulato** (parte da 500) e profitto/perdita corrente;
- **Trade aperti** (entrata, prezzo, P&L in tempo reale) e **chiusi** (storico);
- **grafici** del prezzo con i segnali;
- pulsanti per mettere in pausa / far ripartire il bot.

---

## 6. Comandi utili

| Cosa | Comando (in PowerShell, dentro la cartella) |
|---|---|
| Avviare | `docker compose -f docker-compose-sol.yml up -d` |
| Vedere i log | `docker compose -f docker-compose-sol.yml logs -f` |
| Fermare | `docker compose -f docker-compose-sol.yml down` |
| Aggiornare Freqtrade | `docker compose -f docker-compose-sol.yml pull` poi `up -d` |
| Stato container | `docker ps` |

---

## 7. Cose importanti da sapere

- **Soldi simulati.** In dry-run non si compra nulla davvero: serve a validare il
  comportamento del bot, non a guadagnare.
- **Il bot gira finché il PC è acceso.** Se **spegni o sospendi** Windows, il dry-run si
  ferma (riparte da solo quando riaccendi, grazie a `restart: unless-stopped`, ma solo se
  Docker Desktop è impostato per avviarsi all'avvio di Windows). Per un test **24/7** vero
  serve un piccolo server sempre acceso (VPS) — passo successivo, quando vorrai.
- **Pochi trade.** La strategia è di tipo trend-following: spesso resta **in contanti** e
  apre posizioni solo quando SOL è in trend chiaro. È **normale** vedere giorni senza trade.
- **Quanto tenerlo.** Lascialo girare **alcune settimane** e confronta i trade reali (dry)
  con quanto visto nel backtest (durata ~2 giorni, uscita su trailing, ecc.).

---

## 8. Aspettative oneste (rileggi prima di pensare ai soldi veri)

I numeri del backtest (es. €500 → €9.658, o il PAC €500/mese → ~€104k nel 2021-2026)
sono **in-sample** e dominati dal boom di SOL 2021-2023. Lo stesso PAC partito nel 2024
sarebbe stato in **leggera perdita**. Dettagli in
**[docs/realta-rendimenti-e-rischio.md](realta-rendimenti-e-rischio.md)**. Il dry-run
serve proprio a vedere la realtà **attuale**, non quella passata.

---

## 9. Passaggio al LIVE (solo MOLTO dopo)

**Non** passare ai soldi veri finché il dry-run non ti convince, per settimane. Quando
sarà il momento (te lo preparo io):

1. Crea un account su **futures.kraken.com** e una **chiave API solo-trading, SENZA
   permesso di prelievo** (e, se possibile, con IP whitelist).
2. Metti chiave/segreto in un file `.env` (fuori dal repo, mai committato).
3. In `config-sol-krakenfutures.json` imposta `"dry_run": false`.
4. Parti con importi **piccoli** e tieni la leva a **1x**.

⚠️ I futures usano margine: con leva > 1 rischi la **liquidazione**. Qui restiamo a **1x**.

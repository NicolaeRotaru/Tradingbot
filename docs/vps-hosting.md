# Spostare il bot su un VPS (acceso 24/7, indipendente dal tuo PC)

Guida per principianti: far girare il bot SOL su un piccolo **server cloud sempre acceso**
(VPS), così continua a lavorare anche con il tuo computer **spento**.

> 🟢 Resta in **dry-run** (soldi simulati). Gira **lo stesso identico Docker** che hai già
> usato sul PC. La password della dashboard (`solbot123`) è già nel progetto: sul VPS è
> **"clona e avvia"**, non devi modificare file.

---

## Quanto costa e cosa scegliere

Un VPS piccolo basta e avanza: **1 CPU, 2 GB di RAM, ~20 GB disco**.

| Provider | Prezzo indicativo | Note |
|---|---|---|
| **Hetzner Cloud** (consigliato) | ~4 €/mese (CX22) | Ottimo rapporto qualità/prezzo, datacenter in UE |
| DigitalOcean | ~6 $/mese | Interfaccia molto semplice, tanti tutorial |
| Contabo | ~5 €/mese | Economico, risorse abbondanti |

Scegli **Ubuntu 24.04** come sistema operativo.

---

## Passo 1 — Crea il VPS

1. Registrati sul provider scelto (es. Hetzner Cloud).
2. Crea un nuovo server (“Add Server” / “Create Droplet”):
   - **Immagine/OS:** Ubuntu 24.04
   - **Tipo:** il più piccolo (1 vCPU / 2 GB), es. Hetzner **CX22**
   - **Località:** una vicina a te (es. Germania/Finlandia per l'UE)
   - **Accesso:** se puoi, aggiungi una **chiave SSH** (più sicuro); altrimenti ti arriverà
     una **password di root** via email/pannello.
3. Alla fine avrai un **indirizzo IP pubblico** (es. `203.0.113.45`). Tienilo da parte.

---

## Passo 2 — Collegati al VPS (da Windows)

Apri **PowerShell** sul tuo PC e connettiti (sostituisci con il TUO IP):

```powershell
ssh root@203.0.113.45
```

- La prima volta chiede “Are you sure… (yes/no)” → scrivi **yes**.
- Se usi la password, incollala quando la chiede (non si vede mentre digiti: è normale).

Ora i comandi che scrivi vengono eseguiti **sul server**, non sul tuo PC.

---

## Passo 3 — Installa e avvia tutto (un comando)

Sul VPS (cioè nella finestra SSH appena aperta) incolla questo **unico** comando:

```bash
curl -fsSL https://raw.githubusercontent.com/NicolaeRotaru/Tradingbot/main/scripts/vps-setup.sh | bash
```

Cosa fa da solo: installa Docker, scarica il progetto e **avvia il bot in dry-run**.
Al termine stampa un riepilogo con l'indirizzo per la dashboard. Ci mette un paio di minuti.

> Vuoi farlo a mano invece dello script? In alternativa:
> ```bash
> apt update && apt install -y git curl
> curl -fsSL https://get.docker.com | sh
> git clone https://github.com/NicolaeRotaru/Tradingbot.git
> cd Tradingbot
> docker compose -f docker-compose-sol.yml up -d
> ```

---

## Passo 4 — Apri la dashboard FreqUI in modo SICURO

La dashboard sul VPS **non è aperta a Internet** (è legata a `127.0.0.1`, solo "interno"):
è la scelta giusta per sicurezza. Per vederla dal tuo PC si usa un **tunnel SSH**.

Apri una **nuova** finestra PowerShell sul tuo PC e lancia (col tuo IP):

```powershell
ssh -L 8080:127.0.0.1:8080 root@203.0.113.45
```

Lascia quella finestra **aperta**, poi nel browser vai su:

```
http://127.0.0.1:8080
```

Login: utente **`freqtrader`**, password **`solbot123`**.

> In pratica: il tunnel collega "il porto 8080 del tuo PC" a "il porto 8080 del server",
> passando dentro la connessione SSH cifrata. Chiudendo quella finestra, la dashboard non è
> più raggiungibile da fuori (e va benissimo così).

---

## Passo 5 — Metti in sicurezza il server (consigliato)

Sul VPS, attiva un firewall che lascia passare **solo SSH**:

```bash
ufw allow OpenSSH
ufw --force enable
```

Così non c'è nessuna porta aperta verso Internet a parte SSH. (FreqUI resta raggiungibile
solo tramite il tunnel del Passo 4.)

Consigli extra:
- Se puoi, usa una **chiave SSH** invece della password di root.
- **Non** aprire la porta 8080 verso l'esterno e **non** mettere mai chiavi reali di Kraken
  nel repository.

---

## Gestione di tutti i giorni

Tutti questi comandi vanno dati **sul VPS** (finestra SSH), dentro la cartella `~/Tradingbot`
(`cd ~/Tradingbot`):

| Cosa | Comando |
|---|---|
| Vedere i log dal vivo | `docker compose -f docker-compose-sol.yml logs -f` |
| Stato del bot | `docker compose -f docker-compose-sol.yml ps` |
| Fermare | `docker compose -f docker-compose-sol.yml down` |
| Avviare | `docker compose -f docker-compose-sol.yml up -d` |
| Aggiornare alla versione più recente | `git pull origin main && docker compose -f docker-compose-sol.yml up -d` |

**Puoi spegnere il tuo PC quando vuoi:** il bot gira sul server, non sul tuo computer. Anche
se il VPS si riavvia, il bot riparte da solo (`restart: unless-stopped`).

---

## Verso il LIVE (solo molto più avanti)

Quando, dopo settimane di dry-run, vorrai passare ai soldi veri (lo prepariamo insieme):

1. Crea su **futures.kraken.com** una **chiave API solo-trading, SENZA prelievo**.
2. Mettila in un file `.env` **sul VPS** (mai nel repository).
3. In `config-sol-krakenfutures.json` imposta `"dry_run": false`.
4. Parti con importi piccoli e leva **1x**.

⚠️ Promemoria onesto: i numeri del backtest sono **in-sample** e non sono una previsione.
Vedi [realta-rendimenti-e-rischio.md](realta-rendimenti-e-rischio.md). Il dry-run sul VPS
serve proprio a vederlo lavorare a lungo, di continuo, prima di rischiare denaro reale.

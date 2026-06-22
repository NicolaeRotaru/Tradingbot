---
name: telefono
description: Prepara l'accesso al bot dal telefono o dal PC per vedere la dashboard/grafico in tempo reale. Usala quando l'utente vuole "vedere il bot dal telefono", "aprire la dashboard", "il grafico in tempo reale", "guardare il bot".
---

# Skill: guarda il bot dal telefono / PC

La dashboard FreqUI è legata a `127.0.0.1` sul VPS (sicuro, **non** esposta a Internet): si vede via **tunnel SSH**.

## PC (Windows PowerShell)
```
ssh -L 8080:127.0.0.1:8080 root@162.55.51.250
```
Lascia aperta la finestra, poi browser → http://127.0.0.1:8080 (login `freqtrader` / `solbot123`).

## Telefono Android (app Termux)
1. Installa SSH (solo la prima volta): `pkg update` poi `pkg install openssh -y`
2. Tunnel: `ssh -L 8080:127.0.0.1:8080 root@162.55.51.250`
3. **NON chiudere Termux**: tendina notifiche → tocca **"Acquire wakelock"** (lo tiene vivo).
4. Browser del telefono → http://127.0.0.1:8080 (login `freqtrader` / `solbot123`).

## Alternativa comoda da telefono: Telegram (notifiche push + comandi)
Per il controllo quotidiano senza tunnel. Richiede:
1. Creare un bot con **@BotFather** sul telefono → ottieni *token* e *chat_id*.
2. Attivarlo nel config **sul VPS** via file `.env` (il token è un **segreto: MAI nel repo**).
Dà notifiche automatiche dei trade e comandi `/status` `/profit` `/balance` `/daily`.
Proponilo se l'utente vuole monitorare in mobilità senza tenere il tunnel aperto.

## Se appare "Connection refused"
Il bot non è in ascolto: probabilmente è in `Restarting`. Diagnostica con la skill `stato`
(quasi sempre è il fix permessi: `chown -R 1000:1000 user_data`).

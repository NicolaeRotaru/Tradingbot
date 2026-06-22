# Skill del progetto (comandi rapidi)

Skill di Claude Code per pilotare il trading bot senza ricordare comandi a mano.
In una sessione Claude Code su questo repo, scrivi `/<nome>` (es. `/stato`).

| Skill | A cosa serve | Dove gira |
|---|---|---|
| `/stato` | Come va il bot (Up/Restarting, log, errori) | genera comandi per il VPS |
| `/deploy` | Installa o aggiorna il bot sul VPS (dry-run) | genera comandi per il VPS |
| `/cambia-strategia` | Passa TREND ⇄ ENSEMBLE (compra basso/vende alto) | genera comandi per il VPS |
| `/telefono` | Apri la dashboard/grafico da telefono o PC | genera comandi (tunnel SSH / Telegram) |
| `/backtest` | Backtest onesto su dati reali SOL (rend, DD, Calmar, OOS) | gira nell'ambiente Claude |
| `/deep-ml` | Addestra una rete neurale (LSTM/Transformer) come meta-labeler, con leva controllata; adotta solo se batte la baseline OOS | training sul PC/VPS (serve `torch`) |

## Perché alcune "generano comandi" invece di eseguire
L'ambiente Claude raggiunge **GitHub** ma **non** il VPS né gli exchange. Le skill di
analisi (`/backtest`) girano qui al 100%; quelle che toccano il VPS preparano il
**comando esatto pronto da incollare** nella finestra SSH (una riga, zero errori).

> Upgrade possibile: installare un agente Claude **sul VPS** per far eseguire
> `/deploy` e `/stato` direttamente lì. Più potente, un po' di setup.

## Costanti del progetto (usate dalle skill)
- VPS: `root@162.55.51.250` — Docker, dry-run, 24/7.
- Bot TREND: `docker-compose-sol.yml` · Bot ENSEMBLE: `docker-compose-ensemble.yml` (porta 8080, uno alla volta).
- Dashboard: tunnel SSH → http://127.0.0.1:8080 (login `freqtrader` / `solbot123`).

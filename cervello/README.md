# 🧠 cervello/ — il motore di TradeDesk OS

Qui vive il **motore**: la matematica la fa il **codice**, non l'occhio. Gli script sono in Python
**standard library** (nessuna dipendenza esterna), così girano ovunque.

## Script
| File | Cosa fa | Uso rapido |
|---|---|---|
| `diario.py` | Giornale dei trade (PAPER) + metriche precise (PnL, win-rate, profit factor, expectancy, Sharpe, Sortino, max drawdown). Libro mastro append-only in `Bot-Vault/90-Memoria-AI/diario-trade.jsonl`. | `python cervello/diario.py metriche` |
| `news.py` | Ingestion notizie crypto da fonti free (RSS CoinDesk/Cointelegraph, CryptoPanic, Fear&Greed, CoinGecko trending) → log datato in `Bot-Vault/90-Memoria-AI/news/`. Degrada con grazia se offline. | `python cervello/news.py` |

### diario.py — comandi
```bash
python cervello/diario.py aggiungi '{"pair":"SOL/EUR","side":"long","entry":150,"exit":156,"size":20,"fee":0.08}'
python cervello/diario.py metriche      # metriche in JSON
python cervello/diario.py report 30g    # report (ultimi 30 giorni) → salva in consegne/
python cervello/diario.py posizioni     # trade aperti (senza exit)
python cervello/diario.py reset         # azzera il libro mastro (chiede conferma 'SI')
```
Il PnL si calcola da `entry/exit/size/side` meno `fee`, oppure si passa direttamente `pnl`.
Tutti i trade sono **PAPER** (campo `paper:true`). Niente soldi veri qui.

### news.py — comandi
```bash
python cervello/news.py            # scarica e appende il log dell'ora
python cervello/news.py --stdout   # stampa soltanto (non scrive il file)
```
Eventuali chiavi (es. `CRYPTOPANIC_TOKEN`) stanno in `.env`, **mai committate**.

## I prompt dei rituali (non sono codice: sono istruzioni per il desk)
| File | A cosa serve |
|---|---|
| `giro.md` | "fai un giro": briefing completo + aggiornamento STATO. |
| `polso-orario.md` | Il polso orario: news-intelligence + risk-manager. |
| `ritmo.md` | Le cadenze (orario / giorno / settimana / mese). |
| `sentinelle.md` | Le allerte automatiche e cosa fare quando scattano. |

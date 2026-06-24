# 🕐 Polso orario — il battito del desk (crypto è 24/7)

Ogni ora il desk fa un mini-giro leggero. Protagonisti: **news-intelligence** + **risk-manager**.

## Passi (leggero, ~automatico)
1. `python cervello/news.py` ha già scritto il log dell'ora in `Bot-Vault/90-Memoria-AI/news/`.
   (In CI lo fa il cron `.github/workflows/intel-orario.yml`.)
2. **news-intelligence** legge il log e SINTETIZZA: ci sono catalizzatori veri?
   (listing, hack/exploit, regolamenti, eventi macro, narrativa che cambia.)
3. **risk-manager** controlla le sentinelle di rischio: drawdown, volatilità, funding/OI estremi,
   exchange outage. Se una scatta:
   - 🟢 agisci nei limiti reversibili e annota;
   - 🔴 prepara l'azione e accodala in `AZIONI-IN-ATTESA.md`, allerta Nicola.
4. Se non c'è nulla di rilevante: una riga in `SALA-OPERATIVA.md` ("polso ore HH: nulla di nuovo")
   e stop. Non svegliare tutta la squadra se non serve (efficienza).

## Regola d'oro
Il polso porta **segnali**, non muove capitale. Ogni azione su soldi veri resta 🔴.

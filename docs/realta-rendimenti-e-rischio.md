# Realtà dei rendimenti e del rischio — SOL bot (lettura onesta)

> Documento di "verità a verbale". Serve a **non farti ingannare** da un backtest
> stellare — incluso uno trovato in questa stessa sessione. Leggilo prima di toccare
> la leva o di credere a qualunque numero a tre/quattro zeri.

## 1. La domanda di partenza: "+10.000% con drawdown −50%"

Obiettivo legittimo, ma la risposta onesta dei **tuoi** dati (SOL 1h 2021–2026) è:
**non esiste un modo robusto di ottenerlo.** Chi te lo promette sta usando, quasi
sempre senza accorgersene, informazione dal futuro (*lookahead*) o curve-fitting.

## 2. La trappola del lookahead (successa davvero, qui)

Cercando di alzare il rendimento ho provato un filtro di regime: "stai long su SOL
solo quando BTC è sopra la sua media a 200". Il backtest ha sparato:

| Variante | rend (intero periodo) | max DD | Calmar |
|----------|----------------------:|-------:|-------:|
| regime BTC **[con lookahead]** | **+94.687%** | −33% | 7.75 |
| regime BTC **[corretto, ritardo 1 candela]** | **+1.137%** | −51% | 1.16 |

Il "miracolo" usava la chiusura della candela **prima che fosse finita**. Ritardando
il segnale di **una sola candela** (cioè usando solo ciò che era davvero noto in quel
momento), il guadagno **è evaporato**, finendo persino *sotto* la versione base. Il
gate giornaliero faceva lo stesso: +12.806% → +746% una volta corretto.

> **Lezione (Feynman, in `mentalita-esperti.md`): "Il primo principio è non ingannare
> te stesso — e tu sei la persona più facile da ingannare."**

E c'è di peggio: con ~47.000 candele e abbastanza tentativi, trovi *sempre* un
backtest da +100.000%. È statistica (multiple testing), non bravura. Per questo
"analizzare all'infinito finché esce il numero più alto" è **il modo migliore per
costruire un bot che in reale ti azzera il conto.**

Lo script `scripts/backtest_sol_robust.py` **riproduce** questa dimostrazione, così
resta verificabile.

## 3. La realtà: in-sample vs fuori campione

| Variante (solo-long, costi Kraken Futures) | rend FULL | max DD | Calmar | **rend OOS 2024–26** |
|---|---:|---:|---:|---:|
| Baseline (trailing fisso) | +2.182% | −68% | 1.15 | **+5%** |
| **Chandelier 3×ATR (scelta)** | **+1.829%** | **−53%** | **1.38** | **+11%** |

Il **grosso del +2.182% viene dal 2021–2023** (il lancio di SOL, irripetibile). **Fuori
campione (2024–2026) la strategia fa +5/+11%**, con drawdown ~−53%. L'edge esiste, ma
è in buona parte legato a quel regime storico e **può decadere** (*alpha decay*).

## 4. Perché niente leva alta e niente diversificazione "classica"

- **Leva:** oltre ~1.5x il rendimento composto *peggiora* (leverage decay: i crolli
  amplificati distruggono la capitalizzazione). Per un drawdown −50% serve semmai
  *de-leverage* (~0.9x), non più leva.

  | Leva | rend | max DD |
  |---|---:|---:|
  | 1.0x | +2.182% | −68% |
  | 1.5x | +3.663% | −84% |
  | 2.0x | +2.955% | −92% |
  | 3.0x | +136% | −99% |

- **Diversificare su BTC/ETH peggiora:** la stessa strategia trend-following su BTC
  rende **−35%** e su ETH **+32%** (peggio del comprare e tenere). L'edge è *specifico
  di SOL*. Mischiare abbassa il Calmar invece di alzarlo.
- **Vol-targeting ingenuo** riduce il drawdown ma uccide il rialzo di SOL (i guadagni
  migliori arrivano proprio nei periodi più volatili) → Calmar più basso.

## 5. La bussola giusta: il Calmar, non il rendimento grezzo

A parità di drawdown-obiettivo (−50%), **più Calmar = più soldi**. La scelta robusta è
quindi il **Chandelier 3×ATR** (Calmar 1.38, DD −53%). Calibrando la leva a −50% di DD
si ottiene ~+1.612% in-sample (leva 0.93x) — onesto, non mirabolante.

## 6. Cosa sposta davvero l'ago (in ordine di affidabilità)

1. **Gestione del rischio / sizing al drawdown-obiettivo** — fatto: Chandelier 3×ATR + leva ~1x.
2. **Il PAC €500/mese** — probabilmente la **leva più grande** sul patrimonio finale, e
   non richiede nessuna magia di backtest (media dei prezzi + compounding).
3. **Costi bassi** — ordini maker/post-only: pochi % gratis, ripetuti su molti trade.
4. **Filtro ML "meta-labeling"** — *ricerca*, non promessa. Vedi
   `docs/ricerca-ml-meta-labeling.md`: si adotta **solo se** batte la versione semplice
   **fuori campione** (gate rigoroso). Potrebbe aiutare un po', o niente.

## 7. Aspettative oneste

- Win rate del trend-following **~28%** (poche vincite grandi). "Vincere sempre" è impossibile.
- Drawdown **~−50%** è il prezzo da pagare per i rendimenti alti su un solo asset volatile.
  Va sostenuto **senza spegnere il bot** nel punto peggiore.
- **Avvia SEMPRE in dry-run.** Nessun numero qui è una previsione di profitto: è la
  misura di un'ipotesi su dati passati.

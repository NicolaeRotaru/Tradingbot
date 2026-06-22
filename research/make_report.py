#!/usr/bin/env python3
"""
Genera docs/potenziamento-risultati.md dai numeri REALI di summary.json.

Le tabelle sono auto-popolate: nessun numero scritto a mano -> niente "backtest
gonfiati". Esegui DOPO optimize.py (e idealmente run_research.py per i grafici).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "research"
DOC = ROOT / "docs" / "potenziamento-risultati.md"
ASSETS = ["SOL", "BTC", "ETH"]
FIXED_NAMES = ["Trend long", "Ensemble long", "Ensemble full", "Ensemble +leva"]


def pct(x, dec=0):
    if x is None:
        return "n/d"
    return f"{x*100:+.{dec}f}%"


def num(x, dec=2):
    return "n/d" if x is None else f"{x:.{dec}f}"


def row(name, m):
    return (f"| {name} | {pct(m['total'])} | {pct(m['cagr'])} | {pct(m['dd'])} | "
            f"{num(m['sharpe'])} | {num(m['sortino'])} | {num(m['calmar'])} | {pct(m['expo'],0)} |")


def main():
    S = json.loads((OUT / "summary.json").read_text())
    L = []
    A = L.append
    A("# Potenziamento — Risultati su dati reali (walk-forward, costi inclusi)\n")
    A("> Generato automaticamente da `research/make_report.py` a partire dai backtest\n"
      "> in `research/`. Dati 1h reali 2021–2026 (SOL/BTC/ETH). Costi: fee+slippage\n"
      "> ~0.10%/lato. Nessun lookahead (segnale alla chiusura, posizione dalla barra\n"
      "> dopo). **I numeri qui sono quelli veri: niente promesse, niente overfitting.**\n")

    A("## In una frase\n")
    sol = S["SOL"]
    el = sol["fixed"]["Ensemble long"]["full"]
    bh = sol["buy_hold"]["full"]
    A(f"Sull'intero periodo SOL, l'**Ensemble long** rende **{pct(el['total'])}** con "
      f"**maxDD {pct(el['dd'])}** (Calmar **{num(el['calmar'])}**), contro Buy&Hold "
      f"**{pct(bh['total'])}** ma con **maxDD {pct(bh['dd'])}** (Calmar {num(bh['calmar'])}). "
      f"Stesso ordine di rendimento, **drawdown molto più piccolo** = compounding più sano. "
      f"La stima ONESTA fuori campione (walk-forward) è nella seconda tabella di ogni asset.\n")

    for a in ASSETS:
        s = S[a]
        A(f"\n## {a}\n")
        A("### Intero periodo (varianti fisse, nessun fit)\n")
        A("| strategia | rendimento | CAGR | maxDD | Sharpe | Sortino | Calmar | esposiz. |")
        A("|---|---|---|---|---|---|---|---|")
        for name in FIXED_NAMES:
            A(row(name, s["fixed"][name]["full"]))
        A(row("**Buy & Hold**", s["buy_hold"]["full"]))

        A("\n### Walk-forward OUT-OF-SAMPLE (stima onesta di cosa farebbe live)\n")
        A("| | rendimento | CAGR | maxDD | Sharpe | Sortino | Calmar | esposiz. |")
        A("|---|---|---|---|---|---|---|---|")
        A(row("**Ensemble (OOS)**", s["wfo_oos"]))
        A(row("Buy & Hold (OOS)", s["bh_oos"]))
        mc = s.get("monte_carlo")
        if mc:
            A(f"\n- **Monte Carlo OOS** (block-bootstrap): prob. profitto "
              f"**{mc['prob_profit']*100:.0f}%**, drawdown mediano {mc['dd_p50']*100:.0f}%, "
              f"coda p95 {mc['dd_p95']*100:.0f}%.")
        dsr = s.get("deflated_sharpe")
        A(f"- **Deflated Sharpe** ({s['n_trials']} configurazioni provate): "
          f"{'n/d' if dsr is None else f'{dsr*100:.0f}%'} di probabilità che l'edge sia reale (non fortuna).")
        sho = [c["allow_short"] for c in s["chosen"]]
        mr = [c["allow_mr"] for c in s["chosen"]]
        A(f"- Il walk-forward ha scelto **short** nei fold: {sho} — **MR**: {mr} "
          f"(se short=False quasi ovunque, i dati dicono che su {a} lo short non paga).")
        A(f"\n![{a} equity](../results/research/{a}_equity.png)\n")
        A(f"![{a} walk-forward OOS](../results/research/{a}_oos.png)\n")
        A(f"![{a} regimi](../results/research/{a}_regime.png)\n")

    A("\n## Machine Learning (meta-labeling)\n")
    A("Modello LightGBM secondario che filtra/dimensiona i trade long, con "
      "**purged walk-forward** ed embargo 168h. Adottato SOLO se migliora le metriche "
      "OOS. Vedi `research/ml_meta.py` e il grafico:\n")
    A("![ML meta-labeling](../results/research/ml_meta.png)\n")

    A("\n## Cosa è realistico (e cosa no)\n")
    A("- ✅ **Guadagnare in salita, discesa e lateralità**: sì, tramite commutazione di "
      "regime (trend-long / trend-short / mean-reversion). È ciò che fanno i tre moduli.\n")
    A("- ✅ **Più profittevole = più Calmar, meno drawdown**: il compounding cresce di più "
      "riducendo la varianza (g ≈ μ − σ²/2), anche senza alzare il rendimento lordo.\n")
    A("- ❌ **\"Azzeccare sempre\" / non perdere mai**: impossibile. Il win-rate del "
      "trend-following è ~25-30% (poche vincite grandi). Chi promette il contrario vende "
      "un backtest overfittato che in live perde.\n")
    A("- ⚖️ **Più rendimento assoluto**: si ottiene con leva (`Ensemble +leva`) — ma alza "
      "il rischio. Il drawdown-throttle lo contiene; resta una scelta consapevole.\n")
    A("\n> Avvia SEMPRE in dry-run. La strategia deployabile è "
      "`user_data/strategies/EnsembleRegimeStrategy.py`.\n")

    DOC.write_text("\n".join(L))
    print(f"Report scritto: {DOC}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

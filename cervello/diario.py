#!/usr/bin/env python3
"""
diario.py — Il giornale dei trade di TradeDesk OS + metriche PRECISE.

La matematica la fa il CODICE, non l'occhio. Questo modulo tiene un libro mastro
append-only (JSONL) dei trade in PAPER e calcola metriche oneste:
PnL, win-rate, profit factor, expectancy, Sharpe, Sortino, max drawdown, Calmar.

Solo Python standard library (nessuna dipendenza esterna).

USO (da riga di comando):
  python cervello/diario.py aggiungi '{"pair":"SOL/EUR","side":"long","entry":150,"exit":156,"size":20,"fee":0.08}'
  python cervello/diario.py report            # report completo -> stdout + consegne/
  python cervello/diario.py report 30g        # ultimi 30 giorni
  python cervello/diario.py metriche          # solo le metriche (JSON)
  python cervello/diario.py posizioni         # trade ancora aperti (senza exit)
  python cervello/diario.py reset             # azzera il libro mastro (con conferma)

Note:
- Tutti i trade sono PAPER (campo "paper": true di default). Niente soldi veri qui.
- pnl: se non fornito, viene calcolato da entry/exit/size/side meno le fee.
- Il libro mastro vive in: Bot-Vault/90-Memoria-AI/diario-trade.jsonl
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ---- percorsi (relativi alla radice del repo, indipendenti dalla cwd) ----
ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "Bot-Vault" / "90-Memoria-AI" / "diario-trade.jsonl"
CONSEGNE = ROOT / "consegne"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_paths() -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    CONSEGNE.mkdir(parents=True, exist_ok=True)


def _calc_pnl(t: dict) -> float | None:
    """PnL in valuta dello stake. None se mancano dati (trade aperto)."""
    if t.get("pnl") is not None:
        return float(t["pnl"])
    entry, exit_, size = t.get("entry"), t.get("exit"), t.get("size")
    if entry is None or exit_ is None or size is None:
        return None
    entry, exit_, size = float(entry), float(exit_), float(size)
    if entry <= 0:
        return None
    qty = size / entry  # quantità acquistata con lo stake
    if str(t.get("side", "long")).lower() in ("short", "sell"):
        gross = (entry - exit_) * qty
    else:
        gross = (exit_ - entry) * qty
    fee = float(t.get("fee", 0.0) or 0.0)
    return round(gross - fee, 6)


def aggiungi(raw_json: str) -> None:
    _ensure_paths()
    try:
        t = json.loads(raw_json)
    except json.JSONDecodeError as e:
        print(f"❌ JSON non valido: {e}")
        sys.exit(1)
    t.setdefault("ts", _now_iso())
    t.setdefault("paper", True)
    t.setdefault("side", "long")
    pnl = _calc_pnl(t)
    if pnl is not None:
        t["pnl"] = pnl
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(t, ensure_ascii=False) + "\n")
    stato = "APERTO (no exit)" if pnl is None else f"PnL {pnl:+.2f}"
    print(f"✅ Trade registrato: {t.get('pair','?')} {t.get('side')} · {stato}")


def _load(periodo: str | None = None) -> list[dict]:
    if not LEDGER.exists():
        return []
    rows = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if periodo:
        days = _parse_periodo(periodo)
        if days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            rows = [r for r in rows if _ts(r) and _ts(r) >= cutoff]
    return rows


def _parse_periodo(periodo: str) -> int | None:
    p = periodo.strip().lower().rstrip("g").rstrip("d")
    try:
        return int(p)
    except ValueError:
        return None


def _ts(r: dict):
    try:
        return datetime.fromisoformat(r["ts"])
    except (KeyError, ValueError):
        return None


def _stdev(xs: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    m = sum(xs) / n
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    return math.sqrt(var)


def metriche(rows: list[dict] | None = None) -> dict:
    """Calcola le metriche oneste sui trade CHIUSI (con pnl)."""
    if rows is None:
        rows = _load()
    chiusi = [r for r in rows if r.get("pnl") is not None]
    aperti = [r for r in rows if r.get("pnl") is None]
    pnls = [float(r["pnl"]) for r in chiusi]
    n = len(pnls)
    if n == 0:
        return {"trade_chiusi": 0, "trade_aperti": len(aperti),
                "nota": "Nessun trade chiuso: metriche non calcolabili."}

    vinte = [p for p in pnls if p > 0]
    perse = [p for p in pnls if p < 0]
    pnl_tot = sum(pnls)
    gross_win = sum(vinte)
    gross_loss = abs(sum(perse))
    win_rate = len(vinte) / n
    avg_win = (gross_win / len(vinte)) if vinte else 0.0
    avg_loss = (gross_loss / len(perse)) if perse else 0.0
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else (float("inf") if gross_win > 0 else 0.0)
    expectancy = pnl_tot / n  # PnL medio atteso per trade

    # Sharpe / Sortino sui PnL per-trade (non annualizzati: misura di consistenza)
    sd = _stdev(pnls)
    sharpe = (expectancy / sd) if sd > 0 else 0.0
    downside = _stdev([min(0.0, p) for p in pnls])
    sortino = (expectancy / downside) if downside > 0 else 0.0

    # Max drawdown sulla curva di equity cumulata (in valuta)
    equity, peak, max_dd = 0.0, 0.0, 0.0
    for p in pnls:
        equity += p
        peak = max(peak, equity)
        max_dd = min(max_dd, equity - peak)

    return {
        "trade_chiusi": n,
        "trade_aperti": len(aperti),
        "pnl_totale": round(pnl_tot, 2),
        "win_rate": round(win_rate, 4),
        "profit_factor": (round(profit_factor, 3) if profit_factor != float("inf") else "inf"),
        "expectancy_per_trade": round(expectancy, 4),
        "avg_win": round(avg_win, 4),
        "avg_loss": round(avg_loss, 4),
        "gross_win": round(gross_win, 2),
        "gross_loss": round(gross_loss, 2),
        "sharpe_per_trade": round(sharpe, 3),
        "sortino_per_trade": round(sortino, 3),
        "max_drawdown_valuta": round(max_dd, 2),
    }


def posizioni() -> None:
    aperti = [r for r in _load() if r.get("pnl") is None]
    if not aperti:
        print("Nessuna posizione aperta nel diario.")
        return
    print(f"Posizioni aperte ({len(aperti)}):")
    for r in aperti:
        print(f"  · {r.get('pair','?')} {r.get('side')} entry={r.get('entry')} size={r.get('size')} @ {r.get('ts')}")


def report(periodo: str | None = None) -> None:
    _ensure_paths()
    rows = _load(periodo)
    m = metriche(rows)
    titolo = f"periodo: ultimi {periodo}" if periodo else "periodo: tutto lo storico"
    lines = []
    lines.append(f"# 📒 Report diario trade (PAPER) — {titolo}")
    lines.append(f"Generato: {_now_iso()}")
    lines.append("")
    if m.get("trade_chiusi", 0) == 0:
        lines.append("> Nessun trade chiuso nel periodo. Aggiungi trade con `aggiungi`.")
    else:
        lines.append("| Metrica | Valore |")
        lines.append("|---|---|")
        for k, v in m.items():
            lines.append(f"| {k} | {v} |")
    out = "\n".join(lines) + "\n"
    print(out)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dest = CONSEGNE / f"{stamp}-report-diario.md"
    dest.write_text(out, encoding="utf-8")
    print(f"💾 Report salvato in: {dest.relative_to(ROOT)}")


def reset() -> None:
    if not LEDGER.exists():
        print("Libro mastro già vuoto.")
        return
    risposta = input(f"⚠️  Azzerare {LEDGER.name}? Scrivi 'SI' per confermare: ")
    if risposta.strip() == "SI":
        LEDGER.unlink()
        print("🗑️  Libro mastro azzerato.")
    else:
        print("Annullato.")


def _usage() -> None:
    print(__doc__)


def main(argv: list[str]) -> None:
    if not argv:
        _usage()
        return
    cmd = argv[0]
    if cmd == "aggiungi":
        if len(argv) < 2:
            print("Uso: aggiungi '<json del trade>'")
            sys.exit(1)
        aggiungi(argv[1])
    elif cmd == "report":
        report(argv[1] if len(argv) > 1 else None)
    elif cmd == "metriche":
        print(json.dumps(metriche(), ensure_ascii=False, indent=2))
    elif cmd == "posizioni":
        posizioni()
    elif cmd == "reset":
        reset()
    else:
        print(f"Comando sconosciuto: {cmd}")
        _usage()
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])

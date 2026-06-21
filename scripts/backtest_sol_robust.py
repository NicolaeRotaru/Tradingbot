#!/usr/bin/env python3
"""
Backtest ROBUSTO e ONESTO della strategia SOL solo-long (1h, dati reali).

Scopo: documentare in modo riproducibile DUE cose.

1) La scelta robusta = CHANDELIER 3xATR (miglior Calmar, drawdown ~-53% ≈ obiettivo
   -50%), con confronto in-sample vs FUORI CAMPIONE (2024-2026) e calibrazione della
   leva per centrare un drawdown-obiettivo.

2) La DIMOSTRAZIONE DEL LOOKAHEAD: un filtro "regime BTC>EMA200" sembra dare +94.687%,
   ma e' solo perche' usa la candela non ancora chiusa (informazione dal futuro).
   Ritardando il segnale di 1 sola candela il guadagno EVAPORA (sotto il baseline).
   Questo e' il peccato n.1 di docs/mentalita-esperti.md: serve a non farsi ingannare.

Riusa l'API di scripts/backtest_sol_longshort.py (load, gen, simulate, COST, WU).
Niente lookahead nei segnali "corretti": decisione alla chiusura, posizione dal bar dopo.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import talib.abstract as ta

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import backtest_sol_longshort as bt   # noqa: E402

COST, WU, BY = bt.COST, bt.WU, bt.BARS_YEAR
SPLIT = pd.Timestamp("2024-01-01", tz="UTC")


def load_btc_regime(dates: pd.Series) -> np.ndarray:
    """Regime risk-on di BTC (close > EMA200) allineato alle date di SOL, gia' LAGGATO
    di 1 candela (noto alla barra precedente = nessun lookahead)."""
    p = ROOT / "user_data" / "data_sources" / "BTC_USDT-1h.csv"
    btc = pd.read_csv(p, parse_dates=["date"]).sort_values("date")
    btc["e200"] = ta.EMA(btc, timeperiod=200)
    btc["on"] = btc["close"] > btc["e200"]
    merged = pd.DataFrame({"date": dates}).merge(btc[["date", "on"]], on="date", how="left")
    on = merged["on"].ffill().fillna(False).to_numpy().astype(float)
    return on


def metrics(expo: np.ndarray, ret: np.ndarray, dates: pd.Series, mask: np.ndarray) -> dict:
    """Metriche su un'esposizione continua (gia' shiftata). Costi su variazione di esposizione."""
    idx = mask & (np.arange(len(expo)) >= WU)
    chg = np.abs(np.diff(np.concatenate([[0.0], expo])))
    net = expo * ret - chg * COST
    sub = net[idx]
    eq = np.cumprod(1.0 + sub)
    dd = (eq / np.maximum.accumulate(eq) - 1.0).min()
    d = dates.to_numpy()[idx]
    years = (d[-1] - d[0]) / np.timedelta64(365, "D")
    total = eq[-1] - 1.0
    cagr = eq[-1] ** (1.0 / years) - 1.0 if years > 0 else np.nan
    r = np.diff(eq) / eq[:-1]
    sharpe = r.mean() / r.std() * np.sqrt(BY) if r.std() > 0 else np.nan
    calmar = cagr / abs(dd) if dd < 0 else np.nan
    expo_pct = (expo[idx] != 0).mean()
    return dict(total=total, cagr=cagr, dd=dd, sharpe=sharpe, calmar=calmar, expo=expo_pct)


def lever_to_dd(expo: np.ndarray, ret: np.ndarray, dates: pd.Series,
                target: float = -0.50, cap: float = 8.0) -> tuple[float, dict]:
    """Trova la leva scalare che porta il max drawdown ~ target, e ritorna le metriche."""
    full = np.ones(len(expo), bool)
    lo, hi = 0.0, cap
    for _ in range(60):
        mid = (lo + hi) / 2.0
        dd = metrics(expo * mid, ret, dates, full)["dd"]
        if dd < target:
            hi = mid
        else:
            lo = mid
    L = (lo + hi) / 2.0
    return L, metrics(expo * L, ret, dates, full)


def line(name: str, m_full: dict, m_oos: dict) -> None:
    print(f" {name:<30}{m_full['total']*100:>10.0f}%{m_full['dd']*100:>6.0f}%"
          f"{m_full['calmar']:>7.2f}  |{m_oos['total']*100:>9.0f}%{m_oos['dd']*100:>6.0f}%"
          f"{m_oos['calmar']:>7.2f}")


def main() -> int:
    df = bt.load()
    dates = pd.to_datetime(df["date"])
    ret = df["close"].pct_change().fillna(0).to_numpy()
    full = np.ones(len(df), bool)
    oos = (dates >= SPLIT).to_numpy()

    def expo_of(**kw):
        return pd.Series(bt.gen(df, allow_short=False, **kw)).shift(1).fillna(0).to_numpy()

    print("=" * 80)
    print(" SOL 1h 2021-2026 — solo-long, costi Kraken Futures inclusi")
    print(" (FULL = intero periodo;  OOS = fuori campione 2024-2026)")
    print("=" * 80)
    print(f" {'variante':<30}{'FULL rend':>11}{'DD':>6}{'Calmar':>7}  |"
          f"{'OOS rend':>9}{'DD':>6}{'Calmar':>7}")
    print(" " + "-" * 78)

    ep_base = expo_of()                  # default chand_long=6.0 ≈ baseline
    line("Baseline (chand 6xATR)", metrics(ep_base, ret, dates, full),
         metrics(ep_base, ret, dates, oos))
    for cl in (3.0, 4.0, 5.0):
        ep = expo_of(chand_long=cl)
        tag = "  <-- SCELTA" if cl == 3.0 else ""
        line(f"Chandelier {cl:.0f}xATR{tag}", metrics(ep, ret, dates, full),
             metrics(ep, ret, dates, oos))

    print("\n CALIBRAZIONE LEVA al drawdown-obiettivo -50% (Chandelier 3xATR):")
    L, m = lever_to_dd(expo_of(chand_long=3.0), ret, dates, target=-0.50)
    print(f"   leva {L:.2f}x  ->  rendimento {m['total']*100:+.0f}%   maxDD {m['dd']*100:.0f}%"
          f"   Calmar {m['calmar']:.2f}")

    # ----- DIMOSTRAZIONE LOOKAHEAD -----
    print("\n" + "=" * 80)
    print(" DIMOSTRAZIONE LOOKAHEAD — il 'miracolo' del filtro di regime e' falso")
    print("=" * 80)
    ep3 = expo_of(chand_long=3.0)
    btc_on = load_btc_regime(dates)              # gia' allineato
    btc_on_lag = np.concatenate([[0.0], btc_on[:-1]])   # noto alla barra precedente (corretto)
    print(f" {'variante':<30}{'FULL rend':>11}{'DD':>6}{'Calmar':>7}  |"
          f"{'OOS rend':>9}{'DD':>6}{'Calmar':>7}")
    print(" " + "-" * 78)
    # NON laggato = usa la candela corrente (sbircia il futuro) -> numero gonfiato/falso
    line("regime BTC [LOOKAHEAD]", metrics(ep3 * btc_on, ret, dates, full),
         metrics(ep3 * btc_on, ret, dates, oos))
    # Laggato di 1 candela = onesto -> il guadagno svanisce
    line("regime BTC [corretto/laggato]", metrics(ep3 * btc_on_lag, ret, dates, full),
         metrics(ep3 * btc_on_lag, ret, dates, oos))
    print("\n Lezione: con +47.000 candele e abbastanza tentativi trovi SEMPRE un backtest")
    print(" stellare; quasi sempre e' lookahead/overfitting. Conta il Calmar ROBUSTO (OOS).")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

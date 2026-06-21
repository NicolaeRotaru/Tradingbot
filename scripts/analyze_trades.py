#!/usr/bin/env python3
"""
ANATOMIA DELLE OPERAZIONI — come sono fatti i trade della strategia SOL robusta.

Ricostruisce il LIBRO DEI TRADE (entry/exit/durata/movimento di mercato) della
strategia DEPLOYATA (solo-long, uscita Chandelier 3xATR) sui dati reali SOL 1h, e
traduce tutto in SOLDI partendo dal portafoglio di 500 (size piena = ~tutto il saldo
per trade, come in config: stake 'unlimited', 1 trade alla volta).

Mostra in particolare i TRADE VINCENTI: quanto si tiene la posizione, di quanto si
muove il mercato (MFE), come finiscono (rottura trend vs trailing), i piu' grossi.

Onesto: i numeri "intero periodo" sono dominati dal 2021-2023 (lancio di SOL); la
sezione FUORI CAMPIONE (2024-2026) mostra la realta' piu' recente, sempre in soldi.

Output: stampa a video + grafici in results/ (equity in EUR, durate, esempi di trade).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import backtest_sol_longshort as bt   # noqa: E402

COST, WU = bt.COST, bt.WU
OUTDIR = ROOT / "results"
START_CASH = 500.0
SPLIT = pd.Timestamp("2024-01-01", tz="UTC")
CHAND = 3.0   # Chandelier 3xATR = strategia deployata


def build_ledger(df: pd.DataFrame) -> pd.DataFrame:
    """Libro dei trade dalla macchina a stati (solo-long, Chandelier 3xATR).
    entry = close della candela-segnale; exit = close della candela in cui si chiude.
    Coerente con la P&L del backtest (prod dei rendimenti ~ +1829%)."""
    pos = bt.gen(df, allow_short=False, chand_long=CHAND)
    c = df["close"].to_numpy(); high = df["high"].to_numpy(); low = df["low"].to_numpy()
    e200 = df["ema200"].to_numpy(); atr = df["atr"].to_numpy()
    dates = pd.to_datetime(df["date"]).to_numpy()
    n = len(df)
    trades = []
    i = 0
    while i < n:
        if pos[i] == 1 and (i == 0 or pos[i - 1] != 1):
            a = i
            b = a + 1
            while b < n and pos[b] == 1:
                b += 1
            if b >= n:
                break                      # trade ancora aperto a fine dati: scartato
            entry, exit_ = c[a], c[b]
            seg_hi = high[a + 1:b + 1]; seg_lo = low[a + 1:b + 1]
            mfe = (seg_hi.max() / entry - 1.0) if len(seg_hi) else 0.0
            mae = (seg_lo.min() / entry - 1.0) if len(seg_lo) else 0.0
            net = exit_ / entry - 1.0 - 2 * COST
            reason = "rottura EMA200 (trend)" if c[b] < e200[b] else "Chandelier 3xATR (trailing)"
            trades.append(dict(
                entry_idx=a, exit_idx=b,
                entry_date=dates[a], exit_date=dates[b],
                entry_price=entry, exit_price=exit_,
                dur_h=(dates[b] - dates[a]) / np.timedelta64(1, "h"),
                gross=exit_ / entry - 1.0, net=net,
                mfe=mfe, mae=mae, reason=reason))
            i = b
        else:
            i += 1
    led = pd.DataFrame(trades)
    led["dur_d"] = led["dur_h"] / 24.0
    return led


def money_curve(led: pd.DataFrame, start=START_CASH):
    """Saldo composto in EUR (size piena: ogni trade moltiplica il saldo per (1+net))."""
    bal = start
    rows = []
    for _, t in led.iterrows():
        before = bal
        bal = bal * (1.0 + t["net"])
        rows.append(dict(exit_date=t["exit_date"], before=before, after=bal,
                         pnl_eur=bal - before, net=t["net"]))
    return pd.DataFrame(rows)


def summarize(led: pd.DataFrame, label: str):
    if led.empty:
        print(f"\n[{label}] nessun trade."); return
    win = led[led["net"] > 0]; los = led[led["net"] <= 0]
    mc = money_curve(led)
    final = mc["after"].iloc[-1]
    gross_win = win["net"].sum(); gross_los = -los["net"].sum()
    pf = gross_win / gross_los if gross_los > 0 else float("inf")
    print(f"\n{'='*78}\n {label}\n{'='*78}")
    print(f" Trade totali: {len(led)}   vincenti: {len(win)} ({len(win)/len(led)*100:.0f}%)"
          f"   perdenti: {len(los)} ({len(los)/len(led)*100:.0f}%)")
    print(f" SOLDI: da {START_CASH:.0f} EUR  ->  {final:,.0f} EUR   "
          f"(x{final/START_CASH:.1f},  {(final/START_CASH-1)*100:+,.0f}%)")
    print(f" Profit factor: {pf:.2f}   (somma vincite / somma perdite)")
    print(f"\n VINCENTI — come sono fatte le operazioni che guadagnano:")
    print(f"   guadagno medio: {win['net'].mean()*100:+.1f}%   mediano: {win['net'].median()*100:+.1f}%"
          f"   migliore: {win['net'].max()*100:+.0f}%")
    print(f"   durata media tenuta: {win['dur_d'].mean():.1f} giorni"
          f"   (mediana {win['dur_d'].median():.1f} g, max {win['dur_d'].max():.0f} g)")
    print(f"   il mercato durante il trade sale in media fino a +{win['mfe'].mean()*100:.0f}%"
          f" (MFE), max +{win['mfe'].max()*100:.0f}%")
    print(f"   come finiscono: " + ", ".join(
        f"{k} {v}" for k, v in win['reason'].value_counts().items()))
    print(f"\n PERDENTI — vengono tagliate corte (trend-following):")
    print(f"   perdita media: {los['net'].mean()*100:.1f}%   durata media: {los['dur_d'].mean():.1f} giorni")
    # tempo in CONTANTI tra un trade e l'altro (quanto si aspetta fuori dal mercato)
    gaps = (led["entry_date"].values[1:] - led["exit_date"].values[:-1]) / np.timedelta64(1, "D")
    print(f"\n ATTESA fuori dal mercato (in contanti) tra un trade e l'altro:"
          f" media {gaps.mean():.1f} g, mediana {np.median(gaps):.1f} g")
    return mc


def top_winners(led: pd.DataFrame, k=10):
    win = led[led["net"] > 0].sort_values("net", ascending=False).head(k)
    print(f"\n TOP {k} TRADE VINCENTI (intero periodo):")
    print(f" {'#':>2} {'ingresso':<12}{'uscita':<12}{'giorni':>7}{'prezzo in->out':>20}"
          f"{'guad.':>8}{'MFE':>7}  uscita")
    print(" " + "-" * 92)
    bal = START_CASH
    # ricostruisco il saldo cronologico per stimare il PnL in EUR di ciascun top trade
    money = money_curve(led).set_index(led.index)
    for r, (idx, t) in enumerate(win.iterrows(), 1):
        ed = pd.Timestamp(t["entry_date"]).strftime("%Y-%m-%d")
        xd = pd.Timestamp(t["exit_date"]).strftime("%Y-%m-%d")
        pnl = money.loc[idx, "pnl_eur"]
        print(f" {r:>2} {ed:<12}{xd:<12}{t['dur_d']:>6.0f}g"
              f"   {t['entry_price']:>7.2f} -> {t['exit_price']:>7.2f}"
              f"{t['net']*100:>7.0f}%{t['mfe']*100:>6.0f}%  {t['reason']}")


def make_charts(df: pd.DataFrame, led: pd.DataFrame):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except Exception as e:
        print(f"\n(grafici saltati: {e})"); return []
    saved = []
    win = led[led["net"] > 0]; los = led[led["net"] <= 0]

    # 1) equity in EUR
    mc = money_curve(led)
    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.plot(pd.to_datetime(mc["exit_date"]), mc["after"], lw=1.8, color="#1f77b4")
    ax.axhline(START_CASH, color="grey", ls="--", lw=1, alpha=0.7)
    ax.set_yscale("log"); ax.set_ylabel("Saldo (EUR, scala log)")
    ax.set_title(f"Crescita del capitale — da {START_CASH:.0f}€ a {mc['after'].iloc[-1]:,.0f}€ "
                 f"(solo-long SOL, Chandelier 3xATR)")
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout(); p = OUTDIR / "trade_equity_eur.png"; fig.savefig(p, dpi=120); saved.append(p); plt.close(fig)

    # 2) istogramma durate dei VINCENTI
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(win["dur_d"], bins=30, color="#2ca02c", alpha=0.85)
    ax.axvline(win["dur_d"].median(), color="black", ls="--", lw=1.5,
               label=f"mediana {win['dur_d'].median():.1f} g")
    ax.set_xlabel("Giorni di tenuta (trade vincenti)"); ax.set_ylabel("numero di trade")
    ax.set_title("Quanto si tiene una posizione VINCENTE"); ax.legend(); ax.grid(True, alpha=0.3)
    fig.tight_layout(); p = OUTDIR / "trade_win_durations.png"; fig.savefig(p, dpi=120); saved.append(p); plt.close(fig)

    # 3) durata vs rendimento (winners run, losers cut)
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.scatter(los["dur_d"], los["net"] * 100, s=22, color="#d62728", alpha=0.6, label="perdenti")
    ax.scatter(win["dur_d"], win["net"] * 100, s=22, color="#2ca02c", alpha=0.7, label="vincenti")
    ax.axhline(0, color="grey", lw=1)
    ax.set_xlabel("Durata del trade (giorni)"); ax.set_ylabel("Rendimento del trade (%)")
    ax.set_title("Le vincenti corrono a lungo, le perdenti vengono tagliate corte")
    ax.legend(); ax.grid(True, alpha=0.3)
    fig.tight_layout(); p = OUTDIR / "trade_duration_vs_return.png"; fig.savefig(p, dpi=120); saved.append(p); plt.close(fig)

    # 4) esempi: il piu' grosso vincente e uno "tipico" (mediano)
    def plot_trade(t, fname, title):
        a, b = int(t["entry_idx"]), int(t["exit_idx"])
        pad = max(24, (b - a) // 4)
        s, e = max(0, a - pad), min(len(df) - 1, b + pad)
        sub = df.iloc[s:e + 1]
        dts = pd.to_datetime(sub["date"])
        fig, ax = plt.subplots(figsize=(11, 5.5))
        ax.plot(dts, sub["close"], color="black", lw=1.3, label="prezzo SOL")
        ax.plot(dts, sub["ema50"], color="#ff7f0e", lw=1, alpha=0.8, label="EMA50")
        ax.plot(dts, sub["ema200"], color="#1f77b4", lw=1, alpha=0.8, label="EMA200")
        ax.axvspan(pd.to_datetime(t["entry_date"]), pd.to_datetime(t["exit_date"]),
                   color="#2ca02c", alpha=0.10)
        ax.scatter([pd.to_datetime(t["entry_date"])], [t["entry_price"]], marker="^",
                   s=140, color="green", zorder=5, label="ENTRATA")
        ax.scatter([pd.to_datetime(t["exit_date"])], [t["exit_price"]], marker="v",
                   s=140, color="red", zorder=5, label="USCITA")
        ax.set_title(title); ax.set_ylabel("prezzo SOL (USD)")
        ax.legend(fontsize=8); ax.grid(True, alpha=0.3)
        fig.autofmt_xdate()
        fig.tight_layout(); fig.savefig(OUTDIR / fname, dpi=120); plt.close(fig)
        return OUTDIR / fname

    big = led.loc[led["net"].idxmax()]
    saved.append(plot_trade(
        big, "trade_example_big.png",
        f"Esempio: il trade vincente piu' grosso — entrato {pd.Timestamp(big['entry_date']).date()} "
        f"a {big['entry_price']:.1f} USD, uscito a {big['exit_price']:.1f} USD dopo "
        f"{big['dur_d']:.0f} giorni ({big['net']*100:+.0f}%)"))
    wsorted = led[led["net"] > 0].sort_values("net").reset_index(drop=True)
    typ = wsorted.iloc[len(wsorted) // 2]
    saved.append(plot_trade(
        typ, "trade_example_typical.png",
        f"Esempio: un trade vincente TIPICO — {pd.Timestamp(typ['entry_date']).date()} "
        f"a {typ['entry_price']:.1f} -> {typ['exit_price']:.1f} USD, {typ['dur_d']:.0f} giorni "
        f"({typ['net']*100:+.0f}%)"))
    return saved


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    df = bt.load()
    led = build_ledger(df)
    # sanity: la P&L composta deve avvicinarsi al backtest (+1829% per chand 3)
    comp = (1 + led["net"]).prod() - 1
    print(f"(check P&L composta libro trade: {comp*100:+.0f}%  ~  backtest +1829%)")

    summarize(led, "INTERO PERIODO 2021-2026 (in-sample, dominato dal lancio SOL)")
    top_winners(led, 10)

    led_oos = led[pd.to_datetime(led["entry_date"]) >= SPLIT].reset_index(drop=True)
    summarize(led_oos, "FUORI CAMPIONE 2024-2026 (la realta' piu' recente, ONESTA)")

    saved = make_charts(df, led)
    if saved:
        print("\n Grafici salvati:")
        for p in saved:
            print(f"   {p.relative_to(ROOT)}")
    led.assign(
        entry_date=led["entry_date"], exit_date=led["exit_date"]
    ).to_csv(OUTDIR / "trade_ledger.csv", index=False)
    print(f"\n Libro trade completo: results/trade_ledger.csv ({len(led)} righe)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

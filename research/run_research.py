#!/usr/bin/env python3
"""
Genera i GRAFICI su dati reali a partire dagli artefatti di optimize.py.

Produce in results/research/:
  {asset}_equity.png   confronto equity (varianti fisse vs buy&hold), scala log
  {asset}_oos.png      walk-forward OUT-OF-SAMPLE: ensemble vs buy&hold + drawdown
  {asset}_regime.png   prezzo con sfondo per regime (trend-up / range / trend-down)
  dashboard.png        riepilogo multi-asset
Esegui DOPO optimize.py.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "research"
ASSETS = ["SOL", "BTC", "ETH"]
FIXED_NAMES = ["Trend long", "Ensemble long", "Ensemble full", "Ensemble +leva"]
COLORS = {"Trend long": "#1f77b4", "Ensemble long": "#2ca02c",
          "Ensemble full": "#d62728", "Ensemble +leva": "#9467bd"}


def eq_from_step(step):
    return np.cumprod(1.0 + np.nan_to_num(step))


def load_npz(asset):
    z = np.load(OUT / f"{asset}.npz", allow_pickle=True)
    dates = pd.to_datetime(z["dates"])
    return z, dates


def plot_equity(asset):
    z, dates = load_npz(asset)
    fig, ax = plt.subplots(figsize=(12, 6))
    for name in FIXED_NAMES:
        key = f"step__{name}"
        if key not in z:
            continue
        eq = eq_from_step(z[key]) * 1000
        ax.plot(dates, eq, lw=1.5, color=COLORS[name],
                label=f"{name}  ({(eq[-1]/1000-1)*100:+.0f}%)")
    bh = eq_from_step(z["bh_step"]) * 1000
    ax.plot(dates, bh, lw=1.2, color="black", alpha=0.55,
            label=f"Buy & Hold  ({(bh[-1]/1000-1)*100:+.0f}%)")
    ax.set_yscale("log")
    ax.set_ylabel("Equity da 1000€ (scala log)")
    ax.set_title(f"{asset} 1h — Ensemble a regime vs Buy&Hold  (2021–2026, costi reali, no lookahead)")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend(fontsize=9, loc="upper left")
    fig.tight_layout()
    fig.savefig(OUT / f"{asset}_equity.png", dpi=115)
    plt.close(fig)


def plot_oos(asset, split="2024-01-01"):
    z, dates = load_npz(asset)
    test_idx = z["test_idx"]
    order = np.argsort(test_idx)
    ti = test_idx[order]
    d = dates[ti]
    ens = eq_from_step(z["oos_step"][ti]) * 1000
    bh = eq_from_step(z["bh_step"][ti]) * 1000

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), height_ratios=[2.4, 1], sharex=True)
    ax1.plot(d, ens, lw=1.8, color="#2ca02c", label=f"Ensemble WFO (OOS)  ({(ens[-1]/1000-1)*100:+.0f}%)")
    ax1.plot(d, bh, lw=1.3, color="black", alpha=0.55, label=f"Buy & Hold (OOS)  ({(bh[-1]/1000-1)*100:+.0f}%)")
    ax1.set_yscale("log"); ax1.set_ylabel("Equity da 1000€ (log)")
    ax1.set_title(f"{asset} 1h — WALK-FORWARD OUT-OF-SAMPLE: config scelta sul passato, testata sul futuro")
    ax1.grid(True, which="both", alpha=0.25); ax1.legend(fontsize=9, loc="upper left")

    dd = ens / np.maximum.accumulate(ens) - 1.0
    ddb = bh / np.maximum.accumulate(bh) - 1.0
    ax2.fill_between(d, dd * 100, 0, color="#2ca02c", alpha=0.45, label="Ensemble drawdown")
    ax2.plot(d, ddb * 100, color="black", alpha=0.5, lw=1.0, label="Buy&Hold drawdown")
    ax2.set_ylabel("Drawdown %"); ax2.grid(True, alpha=0.25); ax2.legend(fontsize=8, loc="lower left")
    fig.tight_layout()
    fig.savefig(OUT / f"{asset}_oos.png", dpi=115)
    plt.close(fig)


def plot_regime(asset):
    z, dates = load_npz(asset)
    close = z["close"]; reg = z["regime"]
    fig, ax = plt.subplots(figsize=(12, 5.5))
    ax.plot(dates, close, lw=0.8, color="black")
    ax.set_yscale("log")
    ymin, ymax = np.nanmin(close[400:]) * 0.8, np.nanmax(close) * 1.2
    ax.fill_between(dates, ymin, ymax, where=(reg == 1), color="#2ca02c", alpha=0.13, step="mid", label="trend-up (long)")
    ax.fill_between(dates, ymin, ymax, where=(reg == -1), color="#d62728", alpha=0.13, step="mid", label="trend-down (short)")
    ax.fill_between(dates, ymin, ymax, where=(reg == 0), color="#7f7f7f", alpha=0.08, step="mid", label="range (mean-reversion)")
    ax.set_ylim(ymin, ymax)
    ax.set_ylabel(f"{asset} prezzo (log)")
    ax.set_title(f"{asset} 1h — Regime detection: il bot accende il modulo giusto per ogni fase di mercato")
    ax.legend(fontsize=9, loc="upper left", framealpha=0.9)
    ax.grid(True, which="both", alpha=0.2)
    fig.tight_layout()
    fig.savefig(OUT / f"{asset}_regime.png", dpi=115)
    plt.close(fig)


def plot_dashboard():
    summary = json.loads((OUT / "summary.json").read_text())
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    for j, asset in enumerate(ASSETS):
        z, dates = load_npz(asset)
        # riga 0: equity full ensemble long vs buy&hold
        ax = axes[0, j]
        el = eq_from_step(z["step__Ensemble long"]) * 1000
        bh = eq_from_step(z["bh_step"]) * 1000
        ax.plot(dates, el, color="#2ca02c", lw=1.3, label="Ensemble long")
        ax.plot(dates, bh, color="black", alpha=0.5, lw=1.0, label="Buy&Hold")
        ax.set_yscale("log"); ax.set_title(f"{asset} — full period"); ax.grid(True, which="both", alpha=0.2)
        if j == 0:
            ax.legend(fontsize=8); ax.set_ylabel("Equity 1000€ (log)")
        # riga 1: OOS ensemble vs buy&hold
        ax = axes[1, j]
        ti = np.sort(z["test_idx"])
        ens = eq_from_step(z["oos_step"][ti]) * 1000
        bo = eq_from_step(z["bh_step"][ti]) * 1000
        ax.plot(dates[ti], ens, color="#2ca02c", lw=1.4, label="Ensemble OOS")
        ax.plot(dates[ti], bo, color="black", alpha=0.5, lw=1.0, label="Buy&Hold OOS")
        ax.set_yscale("log"); ax.set_title(f"{asset} — walk-forward OOS"); ax.grid(True, which="both", alpha=0.2)
        m = summary[asset]["wfo_oos"]; mb = summary[asset]["bh_oos"]
        ax.set_xlabel(f"ens DD {m['dd']*100:.0f}% Calmar {m['calmar']:.2f} | BH DD {mb['dd']*100:.0f}%")
        if j == 0:
            ax.legend(fontsize=8); ax.set_ylabel("Equity 1000€ (log)")
    fig.suptitle("Trading bot potenziato — Ensemble a regime vs Buy&Hold (dati reali 1h, costi inclusi)", fontsize=13)
    fig.tight_layout()
    fig.savefig(OUT / "dashboard.png", dpi=115)
    plt.close(fig)


def main():
    for asset in ASSETS:
        plot_equity(asset)
        plot_oos(asset)
        plot_regime(asset)
        print(f" {asset}: grafici salvati")
    plot_dashboard()
    print(" dashboard.png salvato")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

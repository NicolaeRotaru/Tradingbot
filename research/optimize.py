#!/usr/bin/env python3
"""
Ricerca su MIGLIAIA di configurazioni con WALK-FORWARD OUT-OF-SAMPLE + artefatti.

Per ogni asset:
  1. valuta varianti FISSE (default, niente sbirciate) per il confronto onesto;
  2. campiona N configurazioni e fa WALK-FORWARD: sceglie la migliore sul TRAIN
     (Sharpe vincolato) e ne misura la performance sul TEST mai visto -> equity OOS;
  3. classifica i regimi, lancia Monte Carlo e calcola il Deflated Sharpe;
  4. salva tutto in results/research/{asset}.npz + summary.json per i grafici.

"Infiniti backtest" fatti BENE: non si tiene la migliore in-sample (overfitting),
si misura quella scelta su dati futuri, con costi realistici e niente lookahead.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from data import load
from strategies import Params, generate, classify_regime
from engine import (RiskConfig, simulate, metrics, buy_hold,
                    walk_forward_splits, monte_carlo, deflated_sharpe)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "research"
SPLIT = pd.Timestamp("2024-01-01", tz="UTC")
ASSETS = ["SOL", "BTC", "ETH"]

GRID = dict(
    adx_trend=[18, 20, 22, 25, 28],
    er_trend=[0.25, 0.30, 0.35, 0.40],
    chand_long=[3.0, 4.0, 5.0, 6.0, 8.0],
    chand_short=[2.5, 3.0, 3.5, 5.0],
    mr_rsi=[(30, 70), (32, 68), (35, 65), (25, 75)],
    mr_stop=[0.04, 0.06, 0.08],
    allow_short=[False, True],
    allow_mr=[False, True],
)
RGRID = dict(
    target_vol=[0.40, 0.50, 0.60, 0.80],
    max_leverage=[1.0, 1.5, 2.0],
    dd_throttle=[0.15, 0.20, 0.25],
    kelly_frac=[0.5, 0.7, 1.0],
)

# varianti FISSE per il confronto (nessun fit): direzione e moduli, rischio default
FIXED = {
    "Trend long":     (Params(allow_short=False, allow_mr=False), RiskConfig()),
    "Ensemble long":  (Params(allow_short=False, allow_mr=True),  RiskConfig()),
    "Ensemble full":  (Params(allow_short=True,  allow_mr=True),  RiskConfig()),
    "Ensemble +leva": (Params(allow_short=False, allow_mr=True),  RiskConfig(max_leverage=1.5)),
}


def sample_config(rng):
    mr_lo, mr_hi = GRID["mr_rsi"][rng.integers(len(GRID["mr_rsi"]))]
    p = Params(
        adx_trend=float(rng.choice(GRID["adx_trend"])),
        er_trend=float(rng.choice(GRID["er_trend"])),
        chand_long=float(rng.choice(GRID["chand_long"])),
        chand_short=float(rng.choice(GRID["chand_short"])),
        mr_rsi_lo=float(mr_lo), mr_rsi_hi=float(mr_hi),
        mr_stop=float(rng.choice(GRID["mr_stop"])),
        allow_short=bool(rng.choice(GRID["allow_short"])),
        allow_mr=bool(rng.choice(GRID["allow_mr"])),
    )
    rc = RiskConfig(
        target_vol=float(rng.choice(RGRID["target_vol"])),
        max_leverage=float(rng.choice(RGRID["max_leverage"])),
        dd_throttle=float(rng.choice(RGRID["dd_throttle"])),
        kelly_frac=float(rng.choice(RGRID["kelly_frac"])),
    )
    return p, rc


def run(df, p, rc):
    pos, mode, reg = generate(df, p)
    return simulate(df, pos, rc)


def fmt(m):
    return (f"{m['total']*100:>8.0f}%{m['cagr']*100:>7.0f}%{m['dd']*100:>7.0f}%"
            f"{m['sharpe']:>7.2f}{m['sortino']:>8.2f}{m['calmar']:>7.2f}{m['expo']*100:>6.0f}%")


def analyze_asset(asset, n_samples=400, n_folds=6, seed=11):
    df = load(asset)
    n = len(df)
    rng = np.random.default_rng(seed)
    folds = walk_forward_splits(df, n_folds=n_folds, embargo=168)

    # ---- varianti FISSE: metriche full / in-sample / OOS + equity full ----
    fixed_res = {}
    fixed_steps = {}
    for name, (p, rc) in FIXED.items():
        res = run(df, p, rc)
        fixed_res[name] = dict(
            full=metrics(res, df),
            ins=metrics(res, df, hi=SPLIT),
            oos=metrics(res, df, lo=SPLIT),
        )
        fixed_steps[name] = res["ret_step"]

    bh = buy_hold(df)
    bh_block = dict(full=metrics(bh, df), ins=metrics(bh, df, hi=SPLIT), oos=metrics(bh, df, lo=SPLIT))

    # ---- WALK-FORWARD: scelta sul train, misura sul test ----
    configs = [sample_config(rng) for _ in range(n_samples)]
    cache = []     # per config: (res, [(mt,ms) per fold])
    for (p, rc) in configs:
        res = run(df, p, rc)
        rows = [(metrics(res, df, idx=tr), metrics(res, df, idx=te)) for (tr, te) in folds]
        cache.append((res, rows))

    oos_steps = np.zeros(n)
    oos_weff = np.zeros(n)
    chosen = []
    for f, (tr, te) in enumerate(folds):
        best, best_score = None, -1e9
        for ci, (p, rc) in enumerate(configs):
            mt, ms = cache[ci][1][f]
            if mt["trades"] < 15 or not np.isfinite(mt["sharpe"]) or mt["dd"] < -0.55:
                continue
            score = mt["sharpe"] + 0.3 * (mt["calmar"] if np.isfinite(mt["calmar"]) else 0.0)
            if score > best_score:
                best_score, best = score, ci
        if best is None:
            continue
        res = cache[best][0]
        oos_steps[te] = res["ret_step"][te]
        oos_weff[te] = res["w_eff"][te]
        p, rc = configs[best]
        chosen.append(dict(fold=f, params=asdict(p), risk=asdict(rc),
                           test=cache[best][1][f][1]))

    test_idx = np.concatenate([te for (_, te) in folds])
    oos_res = dict(equity=None, ret_step=oos_steps, w_eff=oos_weff, start=400)
    m_oos = metrics(oos_res, df, idx=test_idx)
    m_bh_oos = metrics(bh, df, idx=test_idx)
    mc = monte_carlo(oos_steps[test_idx])
    n_obs = int((oos_steps[test_idx] != 0).sum())
    dsr = deflated_sharpe(m_oos["sharpe"], n_trials=n_samples, n_obs=max(n_obs, 30))

    # regimi (per il grafico overlay), dalla config ensemble_full default
    reg = classify_regime(df, FIXED["Ensemble full"][0])

    # ---- salvataggio artefatti ----
    OUT.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        OUT / f"{asset}.npz",
        dates=df["date"].values.astype("datetime64[ns]").astype("int64"),  # ns stabile
        close=df["close"].to_numpy(),
        regime=reg,
        bh_step=bh["ret_step"],
        oos_step=oos_steps, oos_weff=oos_weff, test_idx=test_idx,
        **{f"step__{k}": v for k, v in fixed_steps.items()},
    )

    def clean(m):
        return {k: (None if isinstance(v, float) and not np.isfinite(v) else
                    (float(v) if isinstance(v, (int, float, np.floating)) else None))
                for k, v in m.items() if k != "eq"}

    summary = dict(
        asset=asset,
        fixed={name: {k: clean(v) for k, v in blk.items()} for name, blk in fixed_res.items()},
        buy_hold={k: clean(v) for k, v in bh_block.items()},
        wfo_oos=clean(m_oos), bh_oos=clean(m_bh_oos),
        monte_carlo={k: float(v) for k, v in mc.items()} if mc else None,
        deflated_sharpe=None if dsr is None or not np.isfinite(dsr) else float(dsr),
        n_trials=n_samples, n_folds=len(folds),
        chosen=[{"fold": c["fold"],
                 "allow_short": c["params"]["allow_short"],
                 "allow_mr": c["params"]["allow_mr"],
                 "max_leverage": c["risk"]["max_leverage"],
                 "test_sharpe": clean(c["test"])["sharpe"],
                 "test_total": clean(c["test"])["total"]} for c in chosen],
    )
    return df, summary


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    all_summary = {}
    for asset in ASSETS:
        df, summary = analyze_asset(asset)
        all_summary[asset] = summary

        print("\n" + "=" * 86)
        print(f" {asset}  —  CONFRONTO (costi reali, niente lookahead)")
        print("=" * 86)
        hdr = f" {'strategia':<18}{'rend':>9}{'CAGR':>7}{'maxDD':>7}{'Shrp':>7}{'Sortino':>8}{'Calmar':>7}{'espos':>6}"
        print(hdr); print(" " + "-" * 84)
        for name, blk in summary["fixed"].items():
            print(f" {name:<18}{fmt(blk['full'])}")
        print(f" {'Buy & Hold':<18}{fmt(summary['buy_hold']['full'])}")
        print(" " + "-" * 84)
        print(f" {'WFO OOS ensemble':<18}{fmt(summary['wfo_oos'])}    <-- stima ONESTA (fuori campione)")
        print(f" {'Buy&Hold (OOS)':<18}{fmt(summary['bh_oos'])}")
        mc = summary["monte_carlo"]
        if mc:
            print(f"   Monte Carlo OOS: prob.profitto {mc['prob_profit']*100:.0f}% | "
                  f"DD mediano {mc['dd_p50']*100:.0f}% | DD p95 {mc['dd_p95']*100:.0f}%")
        dsr = summary["deflated_sharpe"]
        dsr_s = "n/d" if dsr is None else f"{dsr*100:.0f}%"
        print(f"   Deflated Sharpe (prob. edge reale, {summary['n_trials']} prove): {dsr_s}")
        sho = [c["allow_short"] for c in summary["chosen"]]
        mr = [c["allow_mr"] for c in summary["chosen"]]
        print(f"   WFO ha scelto short nei fold: {sho} | MR nei fold: {mr}")

    (OUT / "summary.json").write_text(json.dumps(all_summary, indent=2))
    print(f"\n Artefatti + summary salvati in {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

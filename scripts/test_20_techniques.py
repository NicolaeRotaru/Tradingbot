#!/usr/bin/env python3
"""
20 TECNICHE NUOVE su SOL — sweep esaustivo oltre le 10 strategie base.

Diverse da test_10_strategies.py: qui indicatori/tecniche avanzate.
TREND:    Supertrend, Hull MA, TEMA, Ichimoku, Parabolic SAR, Vortex
MOMENTUM: Stocastico, CCI, Williams %R, ROC, Awesome Osc, MACD-hist
MEAN-REV: RSI2 Connors, Bollinger %B, Z-score, Williams Vix Fix
VOLUME:   OBV trend, Chaikin Money Flow
OVERLAY:  Volatility targeting, Ensemble multi-timeframe, Donchian+filtro, Heikin-Ashi

Mostra IS / OOS / FULL insieme (niente scarto cieco sull'OOS), vs Buy&Hold,
rischio-aggiustato. NB MULTIPLE-TESTING: con 20 prove, ~1 sembra buona per caso.
Conta solo: logica economica + positivo in PIÙ anni + batte B&H. Fee 0.06%/lato.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research"))
from indicators import ema, rsi, atr, bollinger  # noqa: E402

DATA15 = ROOT / "user_data" / "data_sources" / "SOL_USDT-15m.csv"
SPLIT = pd.Timestamp("2024-01-01", tz="UTC")
WARMUP = 300
FEE_SIDE = 0.0006


# ============ indicatori ausiliari ============
def sma(s, n): return pd.Series(s).rolling(n).mean()
def wma(s, n):
    w = np.arange(1, n + 1)
    return pd.Series(s).rolling(n).apply(lambda x: np.dot(x, w) / w.sum(), raw=True)
def hma(s, n):
    return wma(2 * wma(s, n // 2) - wma(s, n), int(np.sqrt(n)))
def tema(s, n):
    e1 = ema(pd.Series(s), n); e2 = ema(e1, n); e3 = ema(e2, n)
    return 3 * e1 - 3 * e2 + e3
def roll_max(s, n): return pd.Series(s).rolling(n).max()
def roll_min(s, n): return pd.Series(s).rolling(n).min()


def _hyst(up, dn):
    """Entra su up, esce su dn, mantiene in mezzo (isteresi)."""
    n = len(up); pos = np.zeros(n, dtype=float); cur = 0
    for i in range(n):
        if cur == 0 and up[i]:
            cur = 1
        elif cur == 1 and dn[i]:
            cur = 0
        pos[i] = cur
    return pos


# ============ 20 TECNICHE (ritornano pos desiderata a fine t, no lookahead via shift nel motore) ============
def t_supertrend(d, period=10, mult=3.0):
    h = d["high"].to_numpy(); l = d["low"].to_numpy(); c = d["close"].to_numpy()
    a = atr(d, period).to_numpy()
    hl2 = (h + l) / 2.0
    upper = hl2 + mult * a; lower = hl2 - mult * a
    n = len(c); st = np.zeros(n); dir_ = np.ones(n)
    fu = upper.copy(); fl = lower.copy()
    for i in range(1, n):
        fu[i] = upper[i] if (upper[i] < fu[i-1] or c[i-1] > fu[i-1]) else fu[i-1]
        fl[i] = lower[i] if (lower[i] > fl[i-1] or c[i-1] < fl[i-1]) else fl[i-1]
        if c[i] > fu[i-1]:
            dir_[i] = 1
        elif c[i] < fl[i-1]:
            dir_[i] = -1
        else:
            dir_[i] = dir_[i-1]
    return (dir_ > 0).astype(float)


def t_hma(d, fast=20, slow=50):
    return (hma(d["close"].to_numpy(), fast) > hma(d["close"].to_numpy(), slow)).astype(float).to_numpy()


def t_tema(d, fast=20, slow=50):
    return (tema(d["close"].to_numpy(), fast) > tema(d["close"].to_numpy(), slow)).astype(float).to_numpy()


def t_ichimoku(d):
    h, l, c = d["high"].to_numpy(), d["low"].to_numpy(), d["close"].to_numpy()
    tenkan = (roll_max(h, 9) + roll_min(l, 9)) / 2
    kijun = (roll_max(h, 26) + roll_min(l, 26)) / 2
    spanA = ((tenkan + kijun) / 2).shift(26)         # nuvola spostata avanti = usa dati passati
    spanB = ((roll_max(h, 52) + roll_min(l, 52)) / 2).shift(26)
    cloud_top = np.maximum(spanA.to_numpy(), spanB.to_numpy())
    sig = c > cloud_top
    return np.where(np.isfinite(cloud_top), sig, 0).astype(float)


def t_psar(d, af0=0.02, afmax=0.2):
    h = d["high"].to_numpy(); l = d["low"].to_numpy()
    n = len(h); pos = np.zeros(n)
    bull = True; af = af0; ep = h[0]; sar = l[0]
    for i in range(1, n):
        sar = sar + af * (ep - sar)
        if bull:
            if l[i] < sar:
                bull = False; sar = ep; ep = l[i]; af = af0
            else:
                if h[i] > ep:
                    ep = h[i]; af = min(af + af0, afmax)
        else:
            if h[i] > sar:
                bull = True; sar = ep; ep = h[i]; af = af0
            else:
                if l[i] < ep:
                    ep = l[i]; af = min(af + af0, afmax)
        pos[i] = 1.0 if bull else 0.0
    return pos


def t_vortex(d, n=14):
    h, l, c = d["high"].to_numpy(), d["low"].to_numpy(), d["close"].to_numpy()
    tr = np.maximum(h[1:], c[:-1]) - np.minimum(l[1:], c[:-1])
    vmp = np.abs(h[1:] - l[:-1]); vmm = np.abs(l[1:] - h[:-1])
    tr = np.concatenate([[np.nan], tr]); vmp = np.concatenate([[np.nan], vmp]); vmm = np.concatenate([[np.nan], vmm])
    str_ = pd.Series(tr).rolling(n).sum(); svmp = pd.Series(vmp).rolling(n).sum(); svmm = pd.Series(vmm).rolling(n).sum()
    vip = svmp / str_; vim = svmm / str_
    return (vip > vim).astype(float).to_numpy()


def t_stochastic(d, k=14, dperiod=3):
    h, l, c = d["high"].to_numpy(), d["low"].to_numpy(), d["close"].to_numpy()
    ll = roll_min(l, k); hh = roll_max(h, k)
    pk = 100 * (c - ll) / (hh - ll + 1e-9)
    pd_ = pk.rolling(dperiod).mean()
    up = (pk > pd_).to_numpy(); dn = (pk < pd_).to_numpy()
    up = np.where(np.isfinite(pk.to_numpy()), up, False); dn = np.where(np.isfinite(pd_.to_numpy()), dn, False)
    return _hyst(up, dn)


def t_cci(d, n=20):
    h, l, c = d["high"].to_numpy(), d["low"].to_numpy(), d["close"].to_numpy()
    tp = (h + l + c) / 3.0
    ma = pd.Series(tp).rolling(n).mean()
    md = pd.Series(tp).rolling(n).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
    cci = (tp - ma) / (0.015 * md + 1e-9)
    return (cci > 0).astype(float).to_numpy()


def t_williams_r(d, n=14):
    h, l, c = d["high"].to_numpy(), d["low"].to_numpy(), d["close"].to_numpy()
    hh = roll_max(h, n); ll = roll_min(l, n)
    wr = -100 * (hh - c) / (hh - ll + 1e-9)
    return (wr > -50).astype(float).to_numpy()   # metà superiore = momentum


def t_roc(d, n=24):
    c = d["close"].to_numpy()
    roc = pd.Series(c) / pd.Series(c).shift(n) - 1.0
    return (roc > 0).astype(float).to_numpy()


def t_awesome(d):
    median = ((d["high"] + d["low"]) / 2).to_numpy()
    ao = sma(median, 5) - sma(median, 34)
    return (ao > 0).astype(float).to_numpy()


def t_macd_hist(d):
    ef, es = ema(d["close"], 12), ema(d["close"], 26)
    macd = ef - es; sig = ema(macd, 9); hist = macd - sig
    return (hist > hist.shift(1)).astype(float).to_numpy()   # istogramma in salita


def t_rsi2_connors(d):
    c = d["close"]; r2 = rsi(c, 2); sma200 = c.rolling(200).mean()
    up = ((r2 < 10) & (c > sma200)).to_numpy()
    dn = ((r2 > 70) | (c < sma200)).to_numpy()
    return _hyst(np.nan_to_num(up), np.nan_to_num(dn))


def t_bollinger_pctb(d):
    bl, bm, bu = bollinger(d["close"], 20, 2.0)
    pctb = (d["close"] - bl) / (bu - bl + 1e-9)
    up = (pctb < 0.05).to_numpy(); dn = (pctb > 0.5).to_numpy()
    up = np.where(np.isfinite(pctb.to_numpy()), up, False); dn = np.where(np.isfinite(pctb.to_numpy()), dn, False)
    return _hyst(up, dn)


def t_zscore(d, n=50):
    c = d["close"]; z = (c - c.rolling(n).mean()) / (c.rolling(n).std() + 1e-9)
    up = (z < -2).to_numpy(); dn = (z > 0).to_numpy()
    up = np.where(np.isfinite(z.to_numpy()), up, False); dn = np.where(np.isfinite(z.to_numpy()), dn, False)
    return _hyst(up, dn)


def t_vixfix(d):
    c = d["close"]; l = d["low"]
    wvf = (c.rolling(22).max() - l) / (c.rolling(22).max() + 1e-9) * 100
    bb_up = wvf.rolling(22).mean() + 2 * wvf.rolling(22).std()
    up = (wvf > bb_up).to_numpy()                 # picco di paura = entra long (reversal)
    dn = (wvf < wvf.rolling(22).mean()).to_numpy()
    up = np.where(np.isfinite(bb_up.to_numpy()), up, False); dn = np.where(np.isfinite(wvf.to_numpy()), dn, False)
    return _hyst(up, dn)


def t_obv(d):
    c = d["close"].to_numpy(); v = d["volume"].to_numpy()
    sign = np.sign(np.diff(c, prepend=c[0]))
    obv = np.cumsum(sign * v)
    obv_ema = ema(pd.Series(obv), 20).to_numpy()
    return (obv > obv_ema).astype(float)


def t_cmf(d, n=20):
    h, l, c, v = d["high"].to_numpy(), d["low"].to_numpy(), d["close"].to_numpy(), d["volume"].to_numpy()
    mfm = ((c - l) - (h - c)) / (h - l + 1e-9)
    mfv = mfm * v
    cmf = pd.Series(mfv).rolling(n).sum() / (pd.Series(v).rolling(n).sum() + 1e-9)
    return (cmf > 0).astype(float).to_numpy()


def t_voltarget(d):
    """Volatility targeting: dentro solo in uptrend (close>EMA50), size ∝ 1/vol (0..1)."""
    c = d["close"]; e50 = ema(c, 50)
    ret = c.pct_change()
    rv = ret.rolling(20).std() * np.sqrt(96)       # vol giornaliera approx (su 4h: scala diversa ma relativa)
    target = 0.04
    size = (target / (rv + 1e-9)).clip(0, 1)
    pos = np.where((c > e50).to_numpy(), size.to_numpy(), 0.0)
    return np.nan_to_num(pos)


def t_ensemble_mtf(d):
    """Long solo se trend 4h (EMA20>50) E trend lento (EMA100>200) concordano."""
    c = d["close"]
    fast_ok = (ema(c, 20) > ema(c, 50)).to_numpy()
    slow_ok = (ema(c, 100) > ema(c, 200)).to_numpy()
    return (fast_ok & slow_ok).astype(float)


def t_donchian_filter(d, entry=20, exit_=10):
    h, l, c = d["high"].to_numpy(), d["low"].to_numpy(), d["close"].to_numpy()
    hh = pd.Series(h).shift(1).rolling(entry).max().to_numpy()
    ll = pd.Series(l).shift(1).rolling(exit_).min().to_numpy()
    e200 = ema(d["close"], 200).to_numpy()
    up = (c > hh) & (c > e200)
    dn = c < ll
    up = np.where(np.isfinite(hh) & np.isfinite(e200), up, False)
    dn = np.where(np.isfinite(ll), dn, False)
    return _hyst(up, dn)


def t_heikin_ashi(d):
    o, h, l, c = d["open"].to_numpy(), d["high"].to_numpy(), d["low"].to_numpy(), d["close"].to_numpy()
    ha_c = (o + h + l + c) / 4.0
    ha_o = np.zeros(len(c)); ha_o[0] = (o[0] + c[0]) / 2
    for i in range(1, len(c)):
        ha_o[i] = (ha_o[i-1] + ha_c[i-1]) / 2
    green = ha_c > ha_o
    return green.astype(float)


TECHNIQUES = [
    ("1. Supertrend 10/3",      t_supertrend),
    ("2. Hull MA 20/50",        t_hma),
    ("3. TEMA 20/50",           t_tema),
    ("4. Ichimoku cloud",       t_ichimoku),
    ("5. Parabolic SAR",        t_psar),
    ("6. Vortex 14",            t_vortex),
    ("7. Stocastico %K/%D",     t_stochastic),
    ("8. CCI 20",               t_cci),
    ("9. Williams %R",          t_williams_r),
    ("10. ROC 24",              t_roc),
    ("11. Awesome Oscillator",  t_awesome),
    ("12. MACD histogram",      t_macd_hist),
    ("13. RSI2 Connors",        t_rsi2_connors),
    ("14. Bollinger %B MR",     t_bollinger_pctb),
    ("15. Z-score MR",          t_zscore),
    ("16. Williams Vix Fix",    t_vixfix),
    ("17. OBV trend",           t_obv),
    ("18. Chaikin Money Flow",  t_cmf),
    ("19. Volatility targeting", t_voltarget),
    ("20. Ensemble multi-TF",   t_ensemble_mtf),
    ("21. Donchian+filtro EMA200", t_donchian_filter),
    ("22. Heikin-Ashi trend",   t_heikin_ashi),
]


# ============ motore long/flat (pos frazionarie ammesse) ============
def met(close, sig, bpy, fee=FEE_SIDE):
    bar = np.zeros(len(close)); bar[1:] = close[1:] / close[:-1] - 1.0
    eff = np.zeros(len(close)); eff[1:] = sig[:-1]
    turn = np.zeros(len(close)); turn[1:] = np.abs(eff[1:] - eff[:-1])
    sr = eff * bar - turn * fee
    eq = np.cumprod(1 + sr)
    years = len(eq) / bpy
    cagr = eq[-1] ** (1 / years) - 1 if eq[-1] > 0 else -1
    peak = np.maximum.accumulate(eq); dd = (eq / peak - 1).min()
    sd = sr.std(); sharpe = sr.mean() / sd * np.sqrt(bpy) if sd > 0 else np.nan
    calmar = cagr / abs(dd) if dd < 0 else np.nan
    ntr = int(np.sum((eff[1:] > 0) & (eff[:-1] == 0)))
    return dict(total=eq[-1] - 1, cagr=cagr, dd=dd, sharpe=sharpe, calmar=calmar, n=ntr)


def resample(d, rule):
    s = d.set_index("date")
    return pd.DataFrame({
        "open": s["open"].resample(rule).first(), "high": s["high"].resample(rule).max(),
        "low": s["low"].resample(rule).min(), "close": s["close"].resample(rule).last(),
        "volume": s["volume"].resample(rule).sum()}).dropna().reset_index()


def test_tf(d, name, bpy):
    d = d.iloc[WARMUP:].reset_index(drop=True)
    split = int((d["date"] < SPLIT).sum())
    close = d["close"].to_numpy(); n = len(d)
    bh = met(close, np.ones(n), bpy)
    bh_oos = met(close[split:], np.ones(n - split), bpy)
    bh_is = met(close[:split], np.ones(split), bpy)

    print("\n" + "#" * 100)
    print(f"# {name}  ({n} candele) — Buy&Hold: full Sharpe {bh['sharpe']:.2f} | "
          f"IS Sharpe {bh_is['sharpe']:.2f} | OOS Sharpe {bh_oos['sharpe']:.2f} (ret {bh_oos['total']*100:+.0f}%)")
    print("#" * 100)
    print(f"  {'tecnica':<28}{'IS Shrp':>8}{'OOS Shrp':>9}{'FULL Shrp':>10}{'OOS ret':>9}"
          f"{'FULL ret':>10}{'MaxDD':>8}{'#tr':>6}  verdetto")
    print("  " + "-" * 116)

    out = []
    for nm, fn in TECHNIQUES:
        try:
            sig = np.nan_to_num(fn(d))
        except Exception as e:
            print(f"  {nm:<28}  ERR {e}")
            continue
        full = met(close, sig, bpy); is_ = met(close[:split], sig[:split], bpy); oos = met(close[split:], sig[split:], bpy)
        robust = (is_["sharpe"] > 0) and (oos["sharpe"] > 0)
        beat = (oos["sharpe"] > bh_oos["sharpe"]) and (oos["calmar"] > bh_oos["calmar"])
        v = "✅ batte B&H" if (robust and beat) else ("~ robusto" if robust and oos["total"] > 0 else "❌")
        print(f"  {nm:<28}{is_['sharpe']:>8.2f}{oos['sharpe']:>9.2f}{full['sharpe']:>10.2f}"
              f"{oos['total']*100:>+8.0f}%{full['total']*100:>+9.0f}%{full['dd']*100:>7.0f}%{full['n']:>6}  {v}")
        out.append((nm, fn, is_, oos, full))
    return out, bh_oos


def per_year(d, name, bpy, names):
    d = d.iloc[WARMUP:].reset_index(drop=True)
    close = d["close"].to_numpy()
    d2 = d.copy(); d2["year"] = pd.to_datetime(d2["date"]).dt.year
    print(f"\n  --- {name}: Sharpe per anno (candidati robusti) ---")
    for nm, fn in TECHNIQUES:
        if nm not in names:
            continue
        sig = np.nan_to_num(fn(d)); line = f"  {nm:<28}"
        for yr in sorted(d2["year"].unique()):
            idx = np.where(d2["year"].to_numpy() == yr)[0]
            if len(idx) < 40:
                continue
            m = met(close[idx[0]:idx[-1]+1], sig[idx[0]:idx[-1]+1], bpy)
            mk = "+" if (m["sharpe"] and m["sharpe"] > 0) else "-"
            line += f" {yr}:{m['sharpe']:>5.1f}{mk}"
        print(line)


def main():
    df = pd.read_csv(DATA15, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    print("=" * 100)
    print(" 20+ TECNICHE NUOVE su SOL — sweep esaustivo, IS/OOS/FULL trasparente vs Buy&Hold")
    print(" ⚠ MULTIPLE-TESTING: con 22 prove ~1 sembra buona per CASO. Conta solo: logica +")
    print("   positivo in PIÙ anni + batte B&H. '✅' isolato su un solo TF = sospetto, non oro.")
    print("=" * 100)

    d4 = resample(df, "4h"); d1 = resample(df, "1D")
    r4, bh4 = test_tf(d4, "TIMEFRAME 4h", 6 * 365)
    r1, bh1 = test_tf(d1, "TIMEFRAME 1d", 365)

    def top(r, k=4):
        return [x[0] for x in sorted(r, key=lambda z: -(z[3]["sharpe"] if np.isfinite(z[3]["sharpe"]) else -9))[:k]]
    per_year(d4, "4h", 6 * 365, top(r4))
    per_year(d1, "1d", 365, top(r1))

    print("\n" + "=" * 100)
    print(" Conclusione attesa: i TREND-FOLLOWING (Supertrend/Hull/TEMA/Ichimoku/Donchian-filtro)")
    print(" si comportano come il già trovato EMA-cross 4h (difensivi, battono B&H risk-adjusted).")
    print(" I mean-reversion e oscillatori restano deboli/negativi. NESSUNO avvicina +10%/sett.")
    print("=" * 100)


if __name__ == "__main__":
    main()

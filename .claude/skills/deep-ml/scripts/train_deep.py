#!/usr/bin/env python3
"""
Rete neurale (LSTM / Transformer) per il bot — META-LABELING ONESTO.

La strategia primaria (ensemble long, research/strategies.py) decide la DIREZIONE.
Una rete neurale legge la SEQUENZA delle ultime L barre di feature all'ingresso e
decide SE FIDARSI del trade e QUANTO scommettere (confidenza -> sizing).

Disciplina anti-overfitting (identica al ramo LightGBM, ma con rete neurale):
  - feature note SOLO fino alla barra d'ingresso (niente lookahead);
  - label tripla-barriera (TP/SL = +-k*ATR, orizzonte temporale);
  - WALK-FORWARD PURGED con EMBARGO (niente leakage tra train e test);
  - scaler stimato SOLO sul train di ciascun fold;
  - VERDETTO: si adotta SOLO se migliora ret medio E Calmar-proxy OUT-OF-SAMPLE.

Leva: il sizing resta vol-targeting con TETTO. Lo script stampa la distanza di
liquidazione per la leva scelta e RIFIUTA leve assurde senza conferma esplicita.

Uso:
  python3 train_deep.py --asset SOL --model lstm --leverage 3
  python3 train_deep.py --asset ETH --model transformer --leverage 2

Richiede: torch, numpy, pandas, scikit-learn, matplotlib.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# --------------------------- aggancio al progetto ---------------------------
def find_root(start: Path) -> Path:
    for q in [start.resolve(), *start.resolve().parents]:
        if (q / "research" / "data.py").exists() and (q / "user_data").exists():
            return q
    raise SystemExit("ERRORE: root del progetto non trovata (manca research/data.py).")


ROOT = find_root(Path(__file__).parent)
sys.path.insert(0, str(ROOT / "research"))
from data import load                       # noqa: E402
from strategies import Params, generate, WU  # noqa: E402

OUT = ROOT / "results" / "research"
OUT.mkdir(parents=True, exist_ok=True)

TP_MULT = SL_MULT = 2.0   # tripla barriera = +-2*ATR
HORIZON = 168             # orizzonte massimo del trade (ore)
EMBARGO = 168             # purga anti-leakage tra train e test (ore)


# --------------------------- feature per barra ---------------------------
def feature_matrix(df: pd.DataFrame) -> np.ndarray:
    """Matrice [n, k] di feature note alla barra i (niente lookahead)."""
    c = df["close"].to_numpy(float)
    e50 = df["ema50"].to_numpy(float); e200 = df["ema200"].to_numpy(float)
    e400 = df["ema400"].to_numpy(float)
    adx = df["adx"].to_numpy(float); atr = df["atr"].to_numpy(float)
    rsi = df["rsi"].to_numpy(float); er = df["er"].to_numpy(float)
    rvol = df["rvol"].to_numpy(float)
    bb_low = df["bb_low"].to_numpy(float); bb_up = df["bb_up"].to_numpy(float)
    mom24 = (df["close"] - df["close"].shift(24)).to_numpy(float)
    return np.column_stack([
        c / e50 - 1.0, e50 / e200 - 1.0, c / e200 - 1.0, e200 / e400 - 1.0,
        adx / 50.0, er, atr / c, (rsi - 50.0) / 50.0,
        mom24 / c, rvol, (c - bb_low) / (bb_up - bb_low + 1e-9),
    ])


def build_entries(df: pd.DataFrame, feats: np.ndarray, seq_len: int):
    """Per ogni ingresso long della strategia primaria: finestra di feature + label tripla-barriera."""
    p = Params(allow_short=False, allow_mr=True)
    pos, _, _ = generate(df, p)
    raw = np.where((pos == 1) & (np.concatenate([[0], pos[:-1]]) == 0))[0]

    c = df["close"].to_numpy(float); high = df["high"].to_numpy(float); low = df["low"].to_numpy(float)
    atr = df["atr"].to_numpy(float)
    dates = pd.to_datetime(df["date"]).to_numpy()
    n = len(df)

    items = []
    for i in raw:
        if i - seq_len + 1 < WU or i + 1 >= n:
            continue
        if np.isnan(feats[i - seq_len + 1:i + 1]).any() or np.isnan(atr[i]):
            continue
        entry = c[i]; a = atr[i]
        up = entry + TP_MULT * a; dn = entry - SL_MULT * a
        end = min(i + HORIZON, n - 1)
        label = ret = None
        for j in range(i + 1, end + 1):
            if high[j] >= up:
                label, ret = 1, up / entry - 1.0; break
            if low[j] <= dn:
                label, ret = 0, dn / entry - 1.0; break
        if label is None:
            ret = c[end] / entry - 1.0; label = int(ret > 0)
        items.append(dict(bar=int(i), date=dates[i], label=int(label), ret=float(ret)))
    items.sort(key=lambda d: d["bar"])
    return items, pos


# --------------------------- modelli (torch) ---------------------------
def get_torch():
    try:
        import torch
        import torch.nn as nn
        return torch, nn
    except ImportError:
        raise SystemExit("ERRORE: serve PyTorch. Installa con:  pip install torch scikit-learn")


def build_model(kind: str, n_feat: int, seq_len: int):
    torch, nn = get_torch()

    class SeqLSTM(nn.Module):
        def __init__(self):
            super().__init__()
            self.lstm = nn.LSTM(n_feat, 32, batch_first=True)
            self.head = nn.Sequential(nn.Dropout(0.2), nn.Linear(32, 1))

        def forward(self, x):
            out, _ = self.lstm(x)
            return self.head(out[:, -1, :]).squeeze(-1)

    class SeqTransformer(nn.Module):
        def __init__(self):
            super().__init__()
            self.proj = nn.Linear(n_feat, 32)
            self.pos = nn.Parameter(torch.zeros(1, seq_len, 32))
            enc = nn.TransformerEncoderLayer(32, 4, dim_feedforward=64,
                                             dropout=0.2, batch_first=True)
            self.enc = nn.TransformerEncoder(enc, 2)
            self.head = nn.Sequential(nn.LayerNorm(32), nn.Dropout(0.2), nn.Linear(32, 1))

        def forward(self, x):
            h = self.proj(x) + self.pos[:, :x.size(1)]
            return self.head(self.enc(h)[:, -1, :]).squeeze(-1)

    return (SeqLSTM() if kind == "lstm" else SeqTransformer())


def train_one(kind, Xtr, ytr, n_feat, seq_len, epochs=40, seed=7):
    torch, nn = get_torch()
    torch.manual_seed(seed); np.random.seed(seed)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = build_model(kind, n_feat, seq_len).to(dev)
    Xt = torch.tensor(Xtr, dtype=torch.float32, device=dev)
    yt = torch.tensor(ytr, dtype=torch.float32, device=dev)
    pos = max(float(ytr.sum()), 1.0); neg = max(float(len(ytr) - ytr.sum()), 1.0)
    lossf = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([neg / pos], device=dev))
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    n, bs = len(Xtr), 128
    model.train()
    for _ in range(epochs):
        perm = torch.randperm(n, device=dev)
        for s in range(0, n, bs):
            idx = perm[s:s + bs]
            opt.zero_grad()
            lossf(model(Xt[idx]), yt[idx]).backward()
            opt.step()
    return model, dev


def predict(model, dev, X):
    torch, _ = get_torch()
    model.eval()
    with torch.no_grad():
        out = model(torch.tensor(X, dtype=torch.float32, device=dev))
        return torch.sigmoid(out).cpu().numpy()


# --------------------------- walk-forward purged ---------------------------
def windows(feats_std, bars, seq_len):
    return np.stack([feats_std[b - seq_len + 1:b + 1] for b in bars]).astype(np.float32)


def purged_wf(feats, items, kind, seq_len, n_folds=5):
    from sklearn.metrics import roc_auc_score
    bars = np.array([d["bar"] for d in items])
    y = np.array([d["label"] for d in items])
    n = len(items)
    fold = n // (n_folds + 1)
    proba = np.full(n, np.nan)
    aucs = []
    n_feat = feats.shape[1]

    for k in range(1, n_folds + 1):
        tr_end = fold * k
        te_lo, te_hi = fold * k, fold * (k + 1)
        if te_hi <= te_lo:
            continue
        te_start_bar = bars[tr_end]
        train_bar_max = te_start_bar - EMBARGO
        tr_idx = np.where((np.arange(n) < tr_end) & (bars < train_bar_max))[0]
        te_idx = np.arange(te_lo, min(te_hi, n))
        if len(tr_idx) < 50 or len(te_idx) < 10:
            continue

        # scaler stimato SOLO sulle barre di training (niente leakage)
        rows = feats[WU:train_bar_max]
        rows = rows[~np.isnan(rows).any(axis=1)]
        mu = rows.mean(axis=0); sd = rows.std(axis=0); sd[sd == 0] = 1.0
        feats_std = (feats - mu) / sd

        Xtr = windows(feats_std, bars[tr_idx], seq_len)
        Xte = windows(feats_std, bars[te_idx], seq_len)
        model, dev = train_one(kind, Xtr, y[tr_idx], n_feat, seq_len)
        proba[te_idx] = predict(model, dev, Xte)
        if len(np.unique(y[te_idx])) > 1:
            aucs.append(roc_auc_score(y[te_idx], proba[te_idx]))
    return proba, aucs


# --------------------------- verdetto economico ---------------------------
def calmar_proxy(rets: np.ndarray):
    eq = np.cumprod(1.0 + rets)
    dd = (eq / np.maximum.accumulate(eq) - 1.0).min()
    total = eq[-1] - 1.0
    return total, dd, (total / abs(dd) if dd < 0 else np.nan)


def liquidation_note(lev: float) -> str:
    move = 1.0 / lev * 100.0          # approssimazione: leva L -> ~ -1/L liquida (maint. margin a parte)
    return f"leva {lev:g}x -> ti liquida circa un -{move:.1f}% (su SOL puo' accadere in un giorno)."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", default="SOL")
    ap.add_argument("--model", default="lstm", choices=["lstm", "transformer"])
    ap.add_argument("--leverage", type=float, default=3.0)
    ap.add_argument("--seq-len", type=int, default=32)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--i-understand-liquidation", action="store_true",
                    help="richiesto per leva > 5x")
    a = ap.parse_args()

    print(f"\n== RETE NEURALE ({a.model.upper()}) su {a.asset} ==")
    print("Rischio:", liquidation_note(a.leverage))
    if a.leverage > 5 and not a.i_understand_liquidation:
        raise SystemExit("STOP: leva > 5x. Tetto consigliato 3x. Per forzare: "
                         "--i-understand-liquidation (e sappi che rischi la liquidazione).")
    if a.leverage > 10:
        raise SystemExit("STOP: leva > 10x rifiutata. Non e' rendimento, e' liquidazione.")

    df = load(a.asset)
    feats = feature_matrix(df)
    items, _ = build_entries(df, feats, a.seq_len)
    if len(items) < 120:
        raise SystemExit(f"Troppi pochi ingressi ({len(items)}) per addestrare in modo onesto.")
    y = np.array([d["label"] for d in items])
    ret = np.array([d["ret"] for d in items])
    dates = np.array([d["date"] for d in items])
    print(f"Dataset: {len(items)} ingressi long | buoni (label=1): {y.mean()*100:.1f}%")

    proba, aucs = purged_wf(feats, items, a.model, a.seq_len, a.folds)
    ok = ~np.isnan(proba)
    print(f"Walk-forward purged: {ok.sum()} trade OOS | AUC medio {np.mean(aucs):.3f} (0.5 = caso)")

    # valore economico: filtrare i trade a bassa confidenza migliora ret medio E Calmar OOS?
    pr, rr, yy, dd = proba[ok], ret[ok], y[ok], dates[ok]
    order = np.argsort(dd)
    pr, rr, yy = pr[order], rr[order], yy[order]
    thr = float(np.median(pr))
    keep = pr >= thr
    t_all = calmar_proxy(rr); t_keep = calmar_proxy(rr[keep])
    print("\nVALORE ECONOMICO (rendimento tripla-barriera per trade, OOS):")
    print(f"  tutti      : n={len(rr):4d}  ret medio {rr.mean()*100:+.2f}%  hit {yy.mean()*100:.0f}%  "
          f"somma {t_all[0]*100:+.0f}%  Calmar~{t_all[2]:.2f}")
    print(f"  rete (top%) : n={keep.sum():4d}  ret medio {rr[keep].mean()*100:+.2f}%  "
          f"hit {yy[keep].mean()*100:.0f}%  somma {t_keep[0]*100:+.0f}%  Calmar~{t_keep[2]:.2f}")

    improve = (rr[keep].mean() > rr.mean() and yy[keep].mean() > yy.mean()
               and (np.isnan(t_all[2]) or t_keep[2] >= t_all[2]))
    verdict = ("ADOTTARE: la rete migliora ret medio, hit-rate E Calmar OOS."
               if improve else
               "NON adottare: nessun miglioramento robusto OOS -> tieni la strategia semplice. "
               "NON alzare la leva per compensare.")
    print(f"\nVERDETTO: {verdict}")

    # grafico: distribuzione confidenza + PnL cumulato per-trade (tutti vs rete)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    ax1.hist(pr, bins=30, color="#1f77b4"); ax1.axvline(thr, color="red", ls="--", label=f"soglia {thr:.2f}")
    ax1.set_title("Confidenza della rete (OOS)"); ax1.legend(); ax1.grid(alpha=0.3)
    ax2.plot(np.cumprod(1 + rr), color="black", label="tutti (no rete)")
    eqk = np.full(len(rr), np.nan); eqk[keep] = np.cumprod(1 + rr[keep])
    ax2.plot(np.where(keep)[0], np.cumprod(1 + rr[keep]), color="#2ca02c", lw=1.8, label="con filtro rete")
    ax2.set_yscale("log"); ax2.set_title("PnL cumulato per-trade OOS"); ax2.legend(); ax2.grid(which="both", alpha=0.3)
    png = OUT / f"deep_{a.asset}_{a.model}.png"
    fig.tight_layout(); fig.savefig(png, dpi=115); plt.close(fig)
    print(f"Grafico: {png}")

    # se adottato: riaddestra su TUTTO e salva modello+scaler per il wiring in Freqtrade
    meta = dict(asset=a.asset, model=a.model, seq_len=a.seq_len, leverage=a.leverage,
                threshold=thr, auc=float(np.mean(aucs)), adopted=bool(improve),
                verdict=verdict)
    if improve:
        torch, _ = get_torch()
        bars = np.array([d["bar"] for d in items])
        rows = feats[WU:][~np.isnan(feats[WU:]).any(axis=1)]
        mu = rows.mean(axis=0); sd = rows.std(axis=0); sd[sd == 0] = 1.0
        Xall = windows((feats - mu) / sd, bars, a.seq_len)
        model, dev = train_one(a.model, Xall, y, feats.shape[1], a.seq_len)
        ckpt = OUT / f"deep_{a.asset}_{a.model}.pt"
        torch.save(dict(state=model.state_dict(), mu=mu, sd=sd, **meta), ckpt)
        print(f"Modello salvato: {ckpt}  (usa la confidenza come moltiplicatore di size/leva)")
    (OUT / f"deep_{a.asset}_{a.model}.json").write_text(json.dumps(meta, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

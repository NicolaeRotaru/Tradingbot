#!/usr/bin/env python3
"""
news.py — Ingestion oraria delle notizie crypto per TradeDesk OS.

Scarica notizie e segnali da fonti FREE e APPENDE un log datato in
`Bot-Vault/90-Memoria-AI/news/AAAA-MM-GG.md`. Il senior `news-intelligence` poi
legge e SINTETIZZA i catalizzatori e fa scattare le sentinelle.

Fonti (tutte gratuite, senza chiave obbligatoria):
- RSS CoinDesk           (https://www.coindesk.com/arc/outboundfeeds/rss/)
- RSS Cointelegraph      (https://cointelegraph.com/rss)
- CryptoPanic (free API) (https://cryptopanic.com/api/v1/posts/) — opz. CRYPTOPANIC_TOKEN
- Fear & Greed Index     (https://api.alternative.me/fng/)
- CoinGecko trending     (https://api.coingecko.com/api/v3/search/trending)

Design:
- SOLO Python standard library (urllib + parser RSS minimale via regex/XML stdlib).
- Degrada con grazia: se una fonte è offline/bloccata, lo segnala e continua.
- Non scrive MAI segreti nel log. Eventuali chiavi stanno in .env (CRYPTOPANIC_TOKEN).

USO:
  python cervello/news.py            # scarica tutte le fonti e appende il log di oggi
  python cervello/news.py --stdout   # stampa soltanto, non scrive il file
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
NEWS_DIR = ROOT / "Bot-Vault" / "90-Memoria-AI" / "news"

UA = "TradeDeskOS/1.0 (+https://github.com; news-intelligence)"
TIMEOUT = 15
MAX_ITEMS_RSS = 8  # quante notizie per fonte RSS

RSS_FEEDS = {
    "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "Cointelegraph": "https://cointelegraph.com/rss",
}


def _fetch(url: str) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
        print(f"  ⚠️  offline/bloccato: {url} ({e})", file=sys.stderr)
        return None


def _parse_rss(raw: bytes, limit: int = MAX_ITEMS_RSS) -> list[dict]:
    """Parser RSS/Atom minimale via stdlib. Ritorna [{title, link, date}]."""
    out: list[dict] = []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return out
    # RSS 2.0: channel/item ; Atom: entry
    items = root.findall(".//item") or root.findall(
        ".//{http://www.w3.org/2005/Atom}entry"
    )
    for it in items[:limit]:
        title = it.findtext("title") or it.findtext(
            "{http://www.w3.org/2005/Atom}title"
        ) or "(senza titolo)"
        link = it.findtext("link") or ""
        if not link:
            le = it.find("{http://www.w3.org/2005/Atom}link")
            if le is not None:
                link = le.get("href", "")
        date = (
            it.findtext("pubDate")
            or it.findtext("{http://www.w3.org/2005/Atom}updated")
            or ""
        )
        out.append({"title": title.strip(), "link": link.strip(), "date": date.strip()})
    return out


def fetch_rss_sources() -> dict[str, list[dict]]:
    res: dict[str, list[dict]] = {}
    for name, url in RSS_FEEDS.items():
        raw = _fetch(url)
        res[name] = _parse_rss(raw) if raw else []
    return res


def fetch_cryptopanic() -> list[dict]:
    token = os.environ.get("CRYPTOPANIC_TOKEN", "").strip()
    base = "https://cryptopanic.com/api/v1/posts/?public=true&kind=news"
    url = f"{base}&auth_token={token}" if token else base
    raw = _fetch(url)
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    out = []
    for p in (data.get("results") or [])[:8]:
        out.append({"title": p.get("title", ""), "link": p.get("url", ""),
                    "date": p.get("published_at", "")})
    return out


def fetch_fng() -> dict | None:
    raw = _fetch("https://api.alternative.me/fng/")
    if not raw:
        return None
    try:
        data = json.loads(raw)
        d = (data.get("data") or [{}])[0]
        return {"value": d.get("value"), "classification": d.get("value_classification")}
    except (json.JSONDecodeError, IndexError):
        return None


def fetch_trending() -> list[str]:
    raw = _fetch("https://api.coingecko.com/api/v3/search/trending")
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return [c["item"]["symbol"].upper() for c in (data.get("coins") or [])][:10]
    except (json.JSONDecodeError, KeyError):
        return []


def build_report() -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%d %H:%M UTC")
    rss = fetch_rss_sources()
    cp = fetch_cryptopanic()
    fng = fetch_fng()
    trending = fetch_trending()

    n_news = sum(len(v) for v in rss.values()) + len(cp)

    L = [f"## 🕐 Polso news — {stamp}", ""]

    if fng:
        L.append(f"**Fear & Greed Index:** {fng.get('value','?')} "
                 f"({fng.get('classification','?')})")
    else:
        L.append("**Fear & Greed Index:** non disponibile (fonte offline).")
    if trending:
        L.append(f"**CoinGecko trending:** {', '.join(trending)}")
    else:
        L.append("**CoinGecko trending:** non disponibile (fonte offline).")
    L.append("")

    for name, items in rss.items():
        L.append(f"### {name}")
        if not items:
            L.append("- _(nessuna notizia — fonte offline o bloccata)_")
        for it in items:
            L.append(f"- [{it['title']}]({it['link']}) — {it['date']}")
        L.append("")

    L.append("### CryptoPanic")
    if not cp:
        L.append("- _(nessuna notizia — fonte offline o senza token)_")
    for it in cp:
        L.append(f"- [{it['title']}]({it['link']}) — {it['date']}")
    L.append("")
    L.append("> 🤖 Da sintetizzare da `news-intelligence`: catalizzatori, impatto sul book, "
             "sentinelle da far scattare.")
    L.append("")
    L.append("---")
    L.append("")
    return "\n".join(L), n_news


def main(argv: list[str]) -> None:
    report, n = build_report()
    only_stdout = "--stdout" in argv
    if only_stdout:
        print(report)
        return
    NEWS_DIR.mkdir(parents=True, exist_ok=True)
    dest = NEWS_DIR / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.md"
    header_needed = not dest.exists()
    with dest.open("a", encoding="utf-8") as f:
        if header_needed:
            f.write(f"# 📰 Log notizie — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n\n")
        f.write(report)
    if n == 0:
        print(f"⚠️  Nessuna notizia scaricata (rete bloccata?). Log scritto comunque: "
              f"{dest.relative_to(ROOT)}")
    else:
        print(f"✅ {n} notizie + indici scritti in: {dest.relative_to(ROOT)}")


if __name__ == "__main__":
    main(sys.argv[1:])

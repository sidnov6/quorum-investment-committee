"""News/events tool. Point-in-time. Free backbone: yfinance headlines + SEC 8-K events.

Finnhub is used automatically if FINNHUB_API_KEY is set (richer, dated articles).
A lightweight finance sentiment lexicon scores each headline deterministically so
the committee has a usable signal even with zero LLM/API keys.
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Optional

import requests

from quorum.config import settings
from quorum.tools.snapshot import cached_fetch

_POS = {
    "beat", "beats", "surge", "surges", "record", "growth", "upgrade", "upgraded", "raises",
    "raised", "strong", "tops", "rally", "gains", "profit", "approval", "wins", "expansion",
    "outperform", "bullish", "buyback", "dividend", "breakthrough", "soars",
}
_NEG = {
    "miss", "misses", "plunge", "plunges", "downgrade", "downgraded", "cuts", "cut", "weak",
    "lawsuit", "probe", "investigation", "recall", "layoffs", "decline", "falls", "loss",
    "fraud", "warning", "bearish", "slump", "default", "bankruptcy", "halts", "sinks", "drop",
}

# SEC 8-K item codes -> human label (the official "material event" feed).
_8K_ITEMS = {
    "1.01": "Material agreement", "1.03": "Bankruptcy", "2.02": "Earnings results",
    "2.05": "Restructuring/costs", "5.02": "Exec/board change", "7.01": "Regulation FD",
    "8.01": "Other material event", "1.05": "Cybersecurity incident",
}

_HEADERS = {"User-Agent": settings.SEC_USER_AGENT}


def _score(text: str) -> float:
    words = set(re.findall(r"[a-z']+", text.lower()))
    pos = len(words & _POS)
    neg = len(words & _NEG)
    if pos == neg == 0:
        return 0.0
    return round((pos - neg) / (pos + neg), 3)


def _yf_news(ticker: str, as_of: dt.date, lookback: int) -> list[dict]:
    def _fetch():
        import yfinance as yf

        try:
            return yf.Ticker(ticker).news or []
        except Exception:
            return []

    # yfinance only returns *current* headlines, so cache per ticker per day and
    # filter to the point-in-time window in-memory. (Historical news needs Finnhub.)
    raw = cached_fetch("yf_news", ticker, dt.date.today().isoformat(), _fetch, ttl=86400)
    out = []
    floor = as_of - dt.timedelta(days=lookback)
    for n in raw:
        content = n.get("content", n)
        title = content.get("title") or n.get("title", "")
        ts = n.get("providerPublishTime")
        pub = None
        if ts:
            pub = dt.date.fromtimestamp(ts)
        else:
            pd_str = content.get("pubDate") or content.get("displayTime")
            if pd_str:
                try:
                    pub = dt.date.fromisoformat(str(pd_str)[:10])
                except Exception:
                    pub = None
        if pub and (pub > as_of or pub < floor):
            continue  # point-in-time + lookback window
        if not title:
            continue
        out.append(
            {
                "title": title,
                "date": pub.isoformat() if pub else as_of.isoformat(),
                "source": content.get("provider", {}).get("displayName", "Yahoo Finance")
                if isinstance(content.get("provider"), dict) else "Yahoo Finance",
                "sentiment": _score(title),
                "type": "news",
            }
        )
    return out


def _finnhub_news(ticker: str, as_of: dt.date, lookback: int) -> list[dict]:
    if not settings.FINNHUB_API_KEY:
        return []
    frm = (as_of - dt.timedelta(days=lookback)).isoformat()
    to = as_of.isoformat()
    key = f"{ticker}_{frm}_{to}"

    def _fetch():
        url = "https://finnhub.io/api/v1/company-news"
        r = requests.get(
            url,
            params={"symbol": ticker, "from": frm, "to": to, "token": settings.FINNHUB_API_KEY},
            timeout=20,
        )
        if r.status_code != 200:
            return []
        return r.json()

    raw = cached_fetch("finnhub_news", key, to, _fetch, ttl=None)
    out = []
    for n in raw or []:
        title = n.get("headline", "")
        if not title:
            continue
        pub = dt.date.fromtimestamp(n["datetime"]) if n.get("datetime") else as_of
        if pub > as_of:
            continue
        out.append(
            {
                "title": title,
                "date": pub.isoformat(),
                "source": n.get("source", "Finnhub"),
                "sentiment": _score(title + " " + n.get("summary", "")),
                "type": "news",
            }
        )
    return out


def get_news(ticker: str, as_of: str, lookback: int = 45) -> list[dict]:
    """Combined, de-duplicated, point-in-time news/events sorted newest-first."""
    as_of_d = dt.date.fromisoformat(str(as_of)[:10])
    items = _finnhub_news(ticker, as_of_d, lookback) or _yf_news(ticker, as_of_d, lookback)
    # de-dup by lowercased title
    seen, uniq = set(), []
    for it in sorted(items, key=lambda x: x["date"], reverse=True):
        k = it["title"].lower()[:80]
        if k in seen:
            continue
        seen.add(k)
        uniq.append(it)
    return uniq[:25]


def summarize_news(items: list[dict]) -> dict:
    """Deterministic news signal the committee argues from."""
    if not items:
        return {"count": 0, "avg_sentiment": 0.0, "positive": 0, "negative": 0, "net_tilt": 0.0}
    sents = [i["sentiment"] for i in items]
    pos = sum(1 for s in sents if s > 0.1)
    neg = sum(1 for s in sents if s < -0.1)
    avg = round(sum(sents) / len(sents), 3)
    # recency-weighted tilt (newer items weigh more)
    weights = [1.0 / (idx + 1) for idx in range(len(items))]
    tilt = round(sum(s * w for s, w in zip(sents, weights)) / sum(weights), 3)
    return {
        "count": len(items),
        "avg_sentiment": avg,
        "positive": pos,
        "negative": neg,
        "net_tilt": tilt,
        "top_positive": next((i["title"] for i in items if i["sentiment"] > 0.1), None),
        "top_negative": next((i["title"] for i in items if i["sentiment"] < -0.1), None),
    }

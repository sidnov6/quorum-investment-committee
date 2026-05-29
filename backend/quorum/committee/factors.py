"""Deterministic factor engine — the numbers behind every argument.

Produces a transparent, source-traced score per ticker from four pillars:
quality (fundamentals), momentum (price), sentiment (news), value.
The LLM agents narrate these; they never invent the scores. This is the
determinism boundary that makes the committee trustworthy.
"""
from __future__ import annotations

from typing import Optional

from quorum.schemas import Citation
from quorum.tools.fundamentals import get_fundamentals
from quorum.tools.news import get_news, summarize_news
from quorum.tools.prices import get_quote


def _clamp(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def compute_factors(ticker: str, as_of: str) -> dict:
    """Return per-ticker factor scores in [-1, 1] plus the citations behind them."""
    fund = get_fundamentals(ticker, as_of)
    quote = get_quote(ticker, as_of) or {}
    news_items = get_news(ticker, as_of)
    news = summarize_news(news_items)

    citations: list[Citation] = []
    pillars: dict[str, Optional[float]] = {}

    # --- Quality pillar (fundamentals) ---
    q = []
    if fund.get("available"):
        nm = fund.get("net_margin")
        if nm is not None:
            q.append(_clamp(nm * 4))  # 25% margin -> +1
            citations.append(Citation(source="SEC EDGAR", field="net_margin", value=nm, as_of=as_of))
        roe = fund.get("roe")
        if roe is not None:
            q.append(_clamp(roe * 2.5))
            citations.append(Citation(source="SEC EDGAR", field="roe", value=roe, as_of=as_of))
        de = fund.get("debt_to_equity")
        if de is not None:
            q.append(_clamp(0.5 - de))  # low leverage good
            citations.append(Citation(source="SEC EDGAR", field="debt_to_equity", value=de, as_of=as_of))
    pillars["quality"] = round(sum(q) / len(q), 3) if q else None

    # --- Momentum pillar (price) ---
    m = []
    for n, w in (("ret_3m_pct", 0.4), ("ret_6m_pct", 0.35), ("ret_12m_pct", 0.25)):
        v = quote.get(n)
        if v is not None:
            m.append(_clamp(v / 25.0) * w)  # +25% over window -> strong
            citations.append(Citation(source="yfinance", field=n, value=v, as_of=as_of, unit="%"))
    mom = sum(m) if m else None
    if quote.get("above_sma_200") is not None:
        trend = 0.15 if quote["above_sma_200"] else -0.15
        mom = (mom or 0) + trend
        citations.append(Citation(source="yfinance", field="above_sma_200",
                                  value=str(quote["above_sma_200"]), as_of=as_of))
    pillars["momentum"] = round(_clamp(mom), 3) if mom is not None else None

    # --- Sentiment pillar (news) ---
    if news["count"] > 0:
        pillars["sentiment"] = round(_clamp(news["net_tilt"] * 1.5), 3)
        citations.append(Citation(source="news", field="net_tilt", value=news["net_tilt"], as_of=as_of))
    else:
        pillars["sentiment"] = None

    # --- Value pillar (earnings yield proxy) ---
    val = None
    eps = fund.get("eps")
    px = quote.get("close")
    if eps and px:
        ey = (eps / px)  # crude trailing earnings yield
        val = _clamp((ey - 0.03) * 12)  # >3% yield positive
        citations.append(Citation(source="derived", field="earnings_yield", value=round(ey, 4), as_of=as_of))
    pillars["value"] = round(val, 3) if val is not None else None

    # --- Composite ---
    weights = {"quality": 0.30, "momentum": 0.35, "sentiment": 0.20, "value": 0.15}
    num, den = 0.0, 0.0
    for k, w in weights.items():
        if pillars.get(k) is not None:
            num += pillars[k] * w
            den += w
    composite = round(num / den, 3) if den else 0.0

    return {
        "ticker": ticker,
        "as_of": as_of,
        "pillars": pillars,
        "composite": composite,
        "fundamentals": fund,
        "quote": quote,
        "news_summary": news,
        "news_items": news_items[:8],
        "citations": [c.model_dump() for c in citations],
    }

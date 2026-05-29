"""Research Analyst Agent — assemble the neutral evidence brief (no opinions)."""
from __future__ import annotations

from quorum.committee.factors import compute_factors
from quorum.schemas import Citation, EvidenceBrief


def build_brief(ticker: str, as_of: str, factors: dict) -> EvidenceBrief:
    fund = factors["fundamentals"]
    quote = factors["quote"]
    price_summary = {
        "close": quote.get("close"),
        "ret_3m_pct": quote.get("ret_3m_pct"),
        "ret_12m_pct": quote.get("ret_12m_pct"),
        "above_sma_200": quote.get("above_sma_200"),
    }
    fundamentals = {
        k: fund.get(k)
        for k in ("revenue", "net_income", "net_margin", "gross_margin", "roe",
                  "debt_to_equity", "eps")
        if fund.get(k) is not None
    }
    citations = [Citation(**c) for c in factors["citations"]]
    return EvidenceBrief(
        ticker=ticker,
        as_of=as_of,
        fundamentals=fundamentals,
        price_summary=price_summary,
        news=factors["news_items"],
        citations=citations,
    )

"""Fundamentals tool: SEC EDGAR CompanyFacts, point-in-time (only facts filed <= as_of)."""
from __future__ import annotations

import datetime as dt
from typing import Optional

import requests

from quorum.config import settings
from quorum.tools.snapshot import cached_fetch

_HEADERS = {"User-Agent": settings.SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"}
_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

# Concepts we care about, in priority order (us-gaap taxonomy).
_CONCEPTS = {
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"],
    "net_income": ["NetIncomeLoss"],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "assets": ["Assets"],
    "liabilities": ["Liabilities"],
    "equity": ["StockholdersEquity"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue"],
    "shares": ["CommonStockSharesOutstanding", "EntityCommonStockSharesOutstanding"],
    "eps": ["EarningsPerShareDiluted", "EarningsPerShareBasic"],
    "long_term_debt": ["LongTermDebtNoncurrent", "LongTermDebt"],
}


def _ticker_to_cik(ticker: str) -> Optional[int]:
    def _fetch():
        r = requests.get(_TICKER_MAP_URL, headers=_HEADERS, timeout=20)
        r.raise_for_status()
        return r.json()

    data = cached_fetch("sec_tickermap", "all", "static", _fetch, ttl=None)
    t = ticker.upper()
    for row in data.values():
        if row.get("ticker", "").upper() == t:
            return int(row["cik_str"])
    return None


def _facts(cik: int, as_of: str) -> dict:
    # CompanyFacts is a full history; cache by CIK + fetch-day only (point-in-time
    # filtering happens in-memory in _latest_value). Refreshed once per day.
    fetch_day = dt.date.today().isoformat()

    def _fetch():
        r = requests.get(_FACTS_URL.format(cik=cik), headers=_HEADERS, timeout=30)
        if r.status_code != 200:
            return {}
        return r.json()

    return cached_fetch("sec_companyfacts", str(cik), fetch_day, _fetch, ttl=None)


def _latest_value(facts: dict, concept_names: list[str], as_of: dt.date):
    """Most recent reported value for a concept, filed on/before as_of (no lookahead)."""
    gaap = facts.get("facts", {}).get("us-gaap", {})
    dei = facts.get("facts", {}).get("dei", {})
    best = None
    for name in concept_names:
        node = gaap.get(name) or dei.get(name)
        if not node:
            continue
        for unit_vals in node.get("units", {}).values():
            for item in unit_vals:
                filed = item.get("filed")
                end = item.get("end")
                if not filed:
                    continue
                try:
                    filed_d = dt.date.fromisoformat(filed)
                except Exception:
                    continue
                if filed_d > as_of:
                    continue  # point-in-time guard: not yet known
                key_date = end or filed
                if best is None or key_date > best[1]:
                    best = (item.get("val"), key_date, name, filed)
        if best:  # first matching concept wins
            break
    return best  # (value, end_date, concept, filed_date) or None


def get_fundamentals(ticker: str, as_of: str) -> dict:
    """Point-in-time fundamentals + a few derived ratios. Empty dict if unavailable."""
    as_of_d = dt.date.fromisoformat(str(as_of)[:10])
    cik = _ticker_to_cik(ticker)
    if cik is None:
        return {"ticker": ticker, "as_of": as_of, "available": False, "reason": "no CIK"}
    facts = _facts(cik, as_of)
    if not facts:
        return {"ticker": ticker, "as_of": as_of, "available": False, "reason": "no facts"}

    out: dict = {"ticker": ticker, "as_of": as_of, "available": True, "raw": {}}
    for label, names in _CONCEPTS.items():
        hit = _latest_value(facts, names, as_of_d)
        if hit:
            out[label] = hit[0]
            out["raw"][label] = {"value": hit[0], "as_of": hit[1], "concept": hit[2], "filed": hit[3]}

    # Derived ratios (deterministic; LLM never computes these).
    def _safe(a, b):
        try:
            return round(a / b, 4) if a is not None and b else None
        except Exception:
            return None

    out["net_margin"] = _safe(out.get("net_income"), out.get("revenue"))
    out["gross_margin"] = _safe(out.get("gross_profit"), out.get("revenue"))
    out["roe"] = _safe(out.get("net_income"), out.get("equity"))
    out["debt_to_equity"] = _safe(out.get("long_term_debt"), out.get("equity"))
    out["current_ratio"] = _safe(out.get("assets"), out.get("liabilities"))
    return out

"""Live paper portfolio — the daily-run track record.

Each step: convene the committee (point-in-time, as_of the run date), mark current
holdings to market, rebalance toward the committee's target weights (with trading
costs), and persist a snapshot. Designed to be called once per trading day by a
scheduler/cron, building an honest, auditable $10k paper track record over time.

No real capital is ever touched — this is decision-support, paper only.
"""
from __future__ import annotations

import datetime as dt

from quorum.committee.committee import run_committee
from quorum.config import settings
from quorum.schemas import Mandate
from quorum.store import db
from quorum.tools.prices import get_price_history, get_quote
from quorum.universe import info, tickers


def _shares(holdings: dict) -> dict:
    """Holdings may be stored as {t: shares} (legacy) or {t: {shares,price,value}}."""
    out = {}
    for t, v in holdings.items():
        out[t] = v["shares"] if isinstance(v, dict) else v
    return out


def _value_of(holdings: dict, prices: dict) -> float:
    return sum(sh * prices.get(t, 0.0) for t, sh in _shares(holdings).items())


def run_daily_step(as_of_date: str | None = None) -> dict:
    """Advance the paper portfolio by one committee meeting. Idempotent per date."""
    as_of = as_of_date or dt.date.today().isoformat()

    # Don't double-run the same date.
    hist = db.paper_history()
    if any(h["run_date"] == as_of for h in hist):
        return {"skipped": True, "reason": f"already ran for {as_of}", "snapshot": snapshot()}

    prev = hist[-1] if hist else None
    cash = prev["cash"] if prev else settings.STARTING_CASH
    holdings = prev["holdings"] if prev else {}

    # Current prices (point-in-time).
    cand = tickers()
    prices = {}
    for t in set(list(holdings.keys()) + cand):
        q = get_quote(t, as_of)
        if q:
            prices[t] = q["close"]

    port_val = cash + _value_of(holdings, prices)
    if port_val <= 0:
        port_val = settings.STARTING_CASH
        cash, holdings = port_val, {}

    # Convene the committee.
    mandate = Mandate(candidates=cand, as_of_date=as_of)
    result = run_committee(mandate)
    target = {p.ticker: p.target_weight for p in result.decision.positions if p.target_weight > 0}

    # Rebalance with turnover cost.
    prev_weights = {t: (sh * prices.get(t, 0) / port_val if port_val else 0)
                    for t, sh in _shares(holdings).items()}
    turnover = sum(abs(target.get(t, 0) - prev_weights.get(t, 0))
                   for t in set(target) | set(prev_weights))
    cost = port_val * turnover * (settings.TRADING_COST_BPS / 10000.0)
    port_val -= cost

    new_holdings, invested = {}, 0.0
    for t, w in target.items():
        px = prices.get(t)
        if px and w > 0:
            dollars = port_val * w
            new_holdings[t] = {"shares": dollars / px, "price": px, "value": round(dollars, 2)}
            invested += dollars
    cash = port_val - invested

    # Store shares + the execution price/value per holding so the displayed table
    # always reconciles with the total (no live re-fetch that can fail/zero out).
    db.record_paper_snapshot(as_of, round(port_val, 2), round(cash, 2),
                             new_holdings, result.decision.model_dump())
    return {
        "skipped": False,
        "as_of": as_of,
        "value": round(port_val, 2),
        "cost": round(cost, 2),
        "turnover": round(turnover, 3),
        "decision": result.decision.model_dump(),
        "status": result.status,
        "snapshot": snapshot(),
    }


def snapshot() -> dict:
    """Current paper-portfolio state + the equity curve for charting."""
    hist = db.paper_history()
    if not hist:
        return {"value": settings.STARTING_CASH, "starting_cash": settings.STARTING_CASH,
                "holdings": [], "curve": [], "total_return": 0.0}
    latest = hist[-1]
    # Use the execution price/value stored at snapshot time. Only re-fetch a price
    # if it's missing (legacy rows), and never let a failed fetch zero a holding.
    holdings = []
    for t, v in latest["holdings"].items():
        if isinstance(v, dict):
            sh, px, val = v.get("shares", 0), v.get("price", 0), v.get("value", 0)
        else:  # legacy {ticker: shares} — recover a price, fall back to last close
            sh = v
            q = get_quote(t, latest["run_date"])
            px = q["close"] if q else 0
            if not px:
                hp = get_price_history(t, latest["run_date"])
                px = float(hp["close"].iloc[-1]) if not hp.empty else 0
            val = round(sh * px, 2)
        holdings.append({"ticker": t, "name": info(t)[0], "sector": info(t)[1],
                         "shares": round(sh, 4), "price": round(px, 2), "value": round(val, 2)})
    holdings.sort(key=lambda x: x["value"], reverse=True)

    # Hard invariant: reported value == sum(holdings) + cash.
    holdings_total = round(sum(h["value"] for h in holdings), 2)
    cash = round(latest["cash"], 2)
    value = round(holdings_total + cash, 2)

    curve = [{"date": h["run_date"], "value": h["value"]} for h in hist]
    start = settings.STARTING_CASH
    return {
        "value": value,
        "cash": cash,
        "starting_cash": start,
        "total_return": round(value / start - 1, 4),
        "holdings": holdings,
        "curve": curve,
        "last_run": latest["run_date"],
        "last_decision": latest.get("decision"),
    }

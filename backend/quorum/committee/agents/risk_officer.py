"""Quant / Risk Officer Agent — deterministic metrics, hard constraints, and a veto.

The agent INTERPRETS numbers; it never computes them (compute_risk_metrics does).
It owns a non-negotiable veto when a proposed book breaches limits.
"""
from __future__ import annotations

from quorum.config import settings
from quorum.schemas import Citation, RiskAssessment
from quorum.tools.risk import compute_risk_metrics


def assess(tickers: list[str], proposed_weights: dict[str, float], as_of: str,
           benchmark: str = "SPY") -> RiskAssessment:
    metrics = compute_risk_metrics(tickers, proposed_weights, as_of, benchmark,
                                   conf=settings.VAR_CONFIDENCE)
    per = metrics["per_ticker"]
    port = metrics["portfolio"]

    constraints = {
        "max_position_weight": settings.MAX_POSITION_WEIGHT,
        "max_portfolio_vol": settings.MAX_PORTFOLIO_VOL,
        "max_drawdown_limit": settings.MAX_DRAWDOWN_LIMIT,
    }

    veto, reasons = False, []
    # Concentration limit
    for t, w in proposed_weights.items():
        if w > settings.MAX_POSITION_WEIGHT + 1e-6:
            veto = True
            reasons.append(f"{t} weight {w:.0%} exceeds max position {settings.MAX_POSITION_WEIGHT:.0%}")
    # Portfolio vol limit
    pv = port.get("annualized_vol")
    if pv is not None and pv > settings.MAX_PORTFOLIO_VOL:
        veto = True
        reasons.append(f"Portfolio vol {pv:.0%} exceeds limit {settings.MAX_PORTFOLIO_VOL:.0%}")

    citations = []
    for t, r in per.items():
        if r.get("available"):
            citations.append(Citation(source="risk_engine", field=f"{t}.annualized_vol",
                                      value=r["annualized_vol"], as_of=as_of))

    return RiskAssessment(
        per_ticker=per,
        portfolio=port,
        constraints=constraints,
        veto=veto,
        veto_reason="; ".join(reasons),
        citations=citations,
    )

"""Point-in-time backtest: grow a $10,000 portfolio by convening the committee
on a schedule and holding its recommended weights until the next meeting.

Honest by construction: on each rebalance date the committee only sees data up to
that date (point-in-time tools), trades incur costs, and we mark-to-market daily.
This is decision-support evaluation, NOT an alpha claim.
"""
from __future__ import annotations

import datetime as dt
from typing import Callable, Optional

import pandas as pd

from quorum.committee.committee import run_committee
from quorum.config import settings
from quorum.schemas import Mandate
from quorum.tools.prices import get_prices


def _business_days(start: str, end: str) -> list[str]:
    rng = pd.bdate_range(start=start, end=end)
    return [d.strftime("%Y-%m-%d") for d in rng]


def _price_panel(tickers: list[str], start: str, end: str) -> pd.DataFrame:
    cols = {}
    pad_start = (dt.date.fromisoformat(start) - dt.timedelta(days=10)).isoformat()
    for t in tickers:
        df = get_prices(t, pad_start, end)
        if not df.empty:
            cols[t] = df["close"]
    if not cols:
        return pd.DataFrame()
    panel = pd.concat(cols, axis=1).ffill()
    return panel


def run_backtest(
    candidates: list[str],
    start: str,
    end: str,
    starting_cash: float = None,
    rebalance_days: int = None,
    horizon_days: int = 60,
    benchmark: str = "SPY",
    progress: Optional[Callable[[dict], None]] = None,
) -> dict:
    starting_cash = starting_cash or settings.STARTING_CASH
    rebalance_days = rebalance_days or settings.REBALANCE_EVERY_DAYS

    panel = _price_panel(candidates + [benchmark], start, end)
    if panel.empty:
        return {"error": "no price data"}
    panel = panel[panel.index >= pd.Timestamp(start)]
    dates = list(panel.index)

    cost_rate = settings.TRADING_COST_BPS / 10000.0

    cash = starting_cash
    shares: dict[str, float] = {}
    equity_curve: list[dict] = []
    meetings: list[dict] = []
    prev_weights: dict[str, float] = {}

    last_rebalance_idx = -10**9
    for i, date in enumerate(dates):
        d = date.strftime("%Y-%m-%d")
        prices = {t: float(panel[t].loc[date]) for t in candidates if t in panel and not pd.isna(panel[t].loc[date])}

        # Rebalance?
        if i - last_rebalance_idx >= rebalance_days:
            last_rebalance_idx = i
            mandate = Mandate(candidates=candidates, as_of_date=d, horizon_days=horizon_days,
                              benchmark=benchmark)
            result = run_committee(mandate)
            target = {p.ticker: p.target_weight for p in result.decision.positions}

            # current portfolio value
            port_val = cash + sum(shares.get(t, 0) * prices.get(t, 0) for t in candidates)
            # turnover cost
            turnover = sum(abs(target.get(t, 0) - prev_weights.get(t, 0)) for t in set(target) | set(prev_weights))
            cost = port_val * turnover * cost_rate
            port_val -= cost

            # set new share holdings
            new_shares = {}
            invested = 0.0
            for t, w in target.items():
                px = prices.get(t)
                if px and w > 0:
                    dollars = port_val * w
                    new_shares[t] = dollars / px
                    invested += dollars
            shares = new_shares
            cash = port_val - invested
            prev_weights = target

            meetings.append({
                "date": d,
                "decision": result.decision.model_dump(),
                "macro": result.macro_view.regime if result.macro_view else None,
                "status": result.status,
                "confidence": result.decision.confidence,
                "rounds": result.rounds_run,
                "port_value_before": round(port_val + cost, 2),
                "turnover": round(turnover, 3),
                "cost": round(cost, 2),
            })
            if progress:
                progress({"type": "meeting", "date": d, "value": round(port_val, 2),
                          "weights": target})

        # mark-to-market
        port_val = cash + sum(shares.get(t, 0) * prices.get(t, 0) for t in candidates)
        equity_curve.append({"date": d, "value": round(port_val, 2),
                             "benchmark": float(panel[benchmark].loc[date]) if benchmark in panel else None})

    # Normalize benchmark to same starting capital
    if equity_curve and equity_curve[0]["benchmark"]:
        b0 = equity_curve[0]["benchmark"]
        for e in equity_curve:
            if e["benchmark"]:
                e["benchmark"] = round(starting_cash * e["benchmark"] / b0, 2)

    metrics = _performance(equity_curve, starting_cash)
    return {
        "candidates": candidates,
        "benchmark": benchmark,
        "start": start,
        "end": end,
        "starting_cash": starting_cash,
        "final_value": equity_curve[-1]["value"] if equity_curve else starting_cash,
        "equity_curve": equity_curve,
        "meetings": meetings,
        "metrics": metrics,
    }


def _performance(curve: list[dict], starting_cash: float) -> dict:
    if len(curve) < 2:
        return {}
    s = pd.Series([c["value"] for c in curve],
                  index=pd.to_datetime([c["date"] for c in curve]))
    rets = s.pct_change().dropna()
    # Measure return against the actual starting capital so it reconciles with
    # final_value / starting_cash shown in the UI (fixes display mismatch).
    base = starting_cash if starting_cash else s.iloc[0]
    total_return = s.iloc[-1] / base - 1
    years = len(s) / 252
    cagr = (s.iloc[-1] / base) ** (1 / years) - 1 if years > 0 else 0
    vol = rets.std() * (252 ** 0.5) if len(rets) > 1 else 0
    sharpe = (rets.mean() / rets.std() * (252 ** 0.5)) if rets.std() else 0
    cummax = s.cummax()
    max_dd = ((s - cummax) / cummax).min()

    bench_metrics = {}
    if curve[0].get("benchmark"):
        b = pd.Series([c["benchmark"] for c in curve if c.get("benchmark")])
        if len(b) > 1:
            bench_metrics = {
                "total_return": round(b.iloc[-1] / b.iloc[0] - 1, 4),
                "final_value": round(b.iloc[-1], 2),
            }
    return {
        "total_return": round(total_return, 4),
        "cagr": round(cagr, 4),
        "annualized_vol": round(vol, 4),
        "sharpe": round(sharpe, 3),
        "max_drawdown": round(max_dd, 4),
        "benchmark": bench_metrics,
        "alpha_vs_benchmark": round(total_return - bench_metrics.get("total_return", 0), 4)
        if bench_metrics else None,
    }

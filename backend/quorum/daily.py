"""Daily committee job — the autonomous heartbeat.

Each run:
  1. Convene the committee on the full universe (point-in-time as of today) and
     advance the paper portfolio (rebalance toward the new target weights).
  2. Scan the held names for sudden risk: large single-day/recent drops or a sharply
     negative news cluster that may warrant emergency restructuring — surfaced as alerts.
  3. Email the portfolio status + changes + alerts to all subscribers.

Designed to be invoked once per trading day by GitHub Actions (free cron) or any
scheduler hitting POST /api/daily/run.
"""
from __future__ import annotations

import datetime as dt

from quorum import email_report, paper
from quorum.committee.factors import compute_factors
from quorum.store import db
from quorum.tools.prices import get_price_history

# Thresholds for the "sudden drop / news shock" detector.
DROP_1D = -0.06       # -6% in a day on a held name
DROP_5D = -0.12       # -12% over a week
NEWS_TILT_ALERT = -0.4


def _recent_returns(ticker: str, as_of: str) -> dict:
    px = get_price_history(ticker, as_of, lookback_days=20)
    if px.empty or len(px) < 6:
        return {}
    close = px["close"]
    return {
        "ret_1d": float(close.iloc[-1] / close.iloc[-2] - 1) if len(close) >= 2 else 0.0,
        "ret_5d": float(close.iloc[-1] / close.iloc[-6] - 1) if len(close) >= 6 else 0.0,
    }


def scan_alerts(as_of: str, holdings: list[dict]) -> list[str]:
    alerts: list[str] = []
    for h in holdings:
        t = h["ticker"]
        rr = _recent_returns(t, as_of)
        if rr.get("ret_1d", 0) <= DROP_1D:
            alerts.append(f"{t} dropped {rr['ret_1d']*100:.1f}% today — committee flagged for review.")
        elif rr.get("ret_5d", 0) <= DROP_5D:
            alerts.append(f"{t} is down {rr['ret_5d']*100:.1f}% over 5 days — momentum deteriorating.")
        # news shock
        f = compute_factors(t, as_of)
        ns = f.get("news_summary", {})
        if ns.get("count", 0) >= 2 and ns.get("net_tilt", 0) <= NEWS_TILT_ALERT:
            top = ns.get("top_negative") or "negative news cluster"
            alerts.append(f'{t} hit by negative news (tilt {ns["net_tilt"]}): "{top}".')
    return alerts


def run_daily(as_of: str | None = None, send_email: bool = True) -> dict:
    as_of = as_of or dt.date.today().isoformat()
    db.init_db()

    # 1. Advance the portfolio (the committee restructures within risk limits).
    daily = paper.run_daily_step(as_of)
    snapshot = paper.snapshot()

    # 2. Risk/news scan on what we now hold.
    alerts = scan_alerts(as_of, snapshot.get("holdings", []))

    # 3. Email subscribers.
    subject, html = email_report.render_report(snapshot, daily, alerts)
    email_result = {"ok": False, "reason": "email disabled"}
    recipients = db.list_subscribers()
    if send_email and recipients:
        email_result = email_report.send_report(recipients, subject, html)

    return {
        "as_of": as_of,
        "portfolio_value": snapshot.get("value"),
        "total_return": snapshot.get("total_return"),
        "rebalanced": not daily.get("skipped", False),
        "alerts": alerts,
        "recipients": recipients,
        "email": email_result,
        "subject": subject,
    }

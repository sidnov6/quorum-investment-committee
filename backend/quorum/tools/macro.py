"""Macro tool: FRED economic series, point-in-time. Degrades to a neutral regime if no key.

Free FRED API key (fred.stlouisfed.org). Without it, returns a neutral macro view so
the committee still runs end-to-end.
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

import requests

from quorum.config import settings
from quorum.tools.snapshot import cached_fetch

# Series that define the regime.
_SERIES = {
    "DGS10": "10Y Treasury yield",
    "DGS2": "2Y Treasury yield",
    "CPIAUCSL": "CPI (inflation)",
    "UNRATE": "Unemployment rate",
    "FEDFUNDS": "Fed funds rate",
    "T10Y2Y": "10Y-2Y spread (recession signal)",
}


def _fred_latest(series: str, as_of: dt.date) -> Optional[dict]:
    if not settings.FRED_API_KEY:
        return None
    key = f"{series}_{as_of.isoformat()}"

    def _fetch():
        url = "https://api.stlouisfed.org/fred/series/observations"
        r = requests.get(
            url,
            params={
                "series_id": series,
                "api_key": settings.FRED_API_KEY,
                "file_type": "json",
                "observation_end": as_of.isoformat(),
                "sort_order": "desc",
                "limit": 13,
            },
            timeout=20,
        )
        if r.status_code != 200:
            return {}
        return r.json()

    data = cached_fetch("fred", key, as_of.isoformat(), _fetch, ttl=None)
    obs = [o for o in data.get("observations", []) if o.get("value") not in (".", None)]
    if not obs:
        return None
    latest = obs[0]
    prior = obs[min(12, len(obs) - 1)]
    try:
        val = float(latest["value"])
        prev = float(prior["value"])
    except Exception:
        return None
    return {"value": val, "date": latest["date"], "change_yoy": round(val - prev, 3)}


def get_macro(as_of: str) -> dict:
    """Point-in-time macro snapshot + a derived regime label and risk tilt."""
    as_of_d = dt.date.fromisoformat(str(as_of)[:10])
    signals: dict = {}
    citations = []
    for sid, label in _SERIES.items():
        v = _fred_latest(sid, as_of_d)
        if v:
            signals[sid] = {"label": label, **v}
            citations.append({"source": "FRED", "field": sid, "value": v["value"], "as_of": v["date"]})

    if not signals:
        # Clean, user-facing fallback — no internal/dev messaging leaks to the UI.
        return {
            "available": False,
            "regime": "neutral",
            "tilt": 0.0,
            "summary": "Macro signals unavailable; the committee weighs the single-name and price "
                       "evidence without a regime tilt.",
            "signals": {},
            "citations": [],
        }

    # Deterministic regime logic.
    tilt = 0.0
    notes = []
    spread = signals.get("T10Y2Y", {}).get("value")
    if spread is not None:
        if spread < 0:
            tilt -= 0.4
            notes.append(f"Inverted yield curve ({spread:.2f}) — recession signal, risk-off.")
        else:
            tilt += 0.1
            notes.append(f"Positive yield curve ({spread:.2f}).")
    unrate = signals.get("UNRATE", {})
    if unrate.get("change_yoy", 0) > 0.5:
        tilt -= 0.2
        notes.append("Unemployment rising YoY — slowing economy.")
    ff = signals.get("FEDFUNDS", {})
    if ff.get("change_yoy", 0) > 1.0:
        tilt -= 0.2
        notes.append("Fed funds rising sharply — tightening regime.")
    elif ff.get("change_yoy", 0) < -0.5:
        tilt += 0.2
        notes.append("Fed easing — supportive for risk assets.")

    tilt = max(-1.0, min(1.0, round(tilt, 2)))
    regime = "risk-off" if tilt < -0.2 else "risk-on" if tilt > 0.2 else "neutral"
    return {
        "available": True,
        "regime": regime,
        "tilt": tilt,
        "summary": " ".join(notes) or "Mixed macro signals; neutral regime.",
        "signals": signals,
        "citations": citations,
    }

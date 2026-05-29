"""Bull & Bear agents. Mandated opposing stances, grounded in the factor evidence.

Deterministic core builds claims from real numbers (so grounding always passes).
If an LLM is available, it rewrites the claims as sharper prose WITHOUT changing the
numbers (the determinism boundary). Rebuttals attack the other side's weakest pillar.
"""
from __future__ import annotations

from quorum.committee.factors import compute_factors  # noqa: F401 (re-export convenience)
from quorum.models.router import NoLLMAvailable, complete
from quorum.schemas import Argument, Citation


def _cite(factors: dict, field: str) -> list[Citation]:
    return [Citation(**c) for c in factors["citations"] if c["field"] == field]


def _news_cite(factors: dict, positive: bool) -> tuple[str, list[Citation]]:
    """Find the strongest positive/negative real headline and cite it (with date+source)."""
    items = factors.get("news_items", [])
    pool = [n for n in items if (n.get("sentiment", 0) > 0.1) == positive and
            (n.get("sentiment", 0) > 0.1 or n.get("sentiment", 0) < -0.1)]
    if not pool:
        return "", []
    best = max(pool, key=lambda n: abs(n.get("sentiment", 0)))
    cite = Citation(source=best.get("source", "news"), field="headline",
                    value=best["title"], as_of=best.get("date", factors["as_of"]))
    return best["title"], [cite]


def bull_case(ticker: str, factors: dict) -> list[Argument]:
    p = factors["pillars"]
    f = factors["fundamentals"]
    q = factors["quote"]
    news = factors["news_summary"]
    args: list[Argument] = []

    if f.get("net_margin") is not None and f["net_margin"] > 0.12:
        args.append(Argument(agent="bull", stance="bull",
            claim=f"{ticker} runs a high net margin of {f['net_margin']}, evidence of pricing power and durable profitability.",
            evidence=_cite(factors, "net_margin"), confidence=0.7))
    if f.get("roe") is not None and f["roe"] > 0.15:
        args.append(Argument(agent="bull", stance="bull",
            claim=f"Return on equity of {f['roe']} shows management compounds shareholder capital efficiently.",
            evidence=_cite(factors, "roe"), confidence=0.68))
    if q.get("ret_3m_pct") is not None and q["ret_3m_pct"] > 0:
        args.append(Argument(agent="bull", stance="bull",
            claim=f"Positive 3-month momentum of {q['ret_3m_pct']}% confirms the market is rewarding the story.",
            evidence=_cite(factors, "ret_3m_pct"), confidence=0.6))
    if q.get("above_sma_200"):
        args.append(Argument(agent="bull", stance="bull",
            claim=f"{ticker} trades above its 200-day average — a constructive long-term trend.",
            evidence=_cite(factors, "above_sma_200"), confidence=0.55))
    headline, ncite = _news_cite(factors, positive=True)
    if headline:
        args.append(Argument(agent="bull", stance="bull",
            claim=f"Recent catalyst supports the thesis — news flow: \"{headline}\".",
            evidence=ncite, confidence=0.5))
    if not args:
        args.append(Argument(agent="bull", stance="bull",
            claim=f"The bull case for {ticker} is thin on current evidence; at best a contrarian value bet.",
            evidence=[], confidence=0.35))
    return _maybe_narrate("bull", ticker, args)


def bear_case(ticker: str, factors: dict) -> list[Argument]:
    p = factors["pillars"]
    f = factors["fundamentals"]
    q = factors["quote"]
    news = factors["news_summary"]
    args: list[Argument] = []

    if f.get("debt_to_equity") is not None and f["debt_to_equity"] > 0.8:
        args.append(Argument(agent="bear", stance="bear",
            claim=f"Leverage is elevated: debt-to-equity of {f['debt_to_equity']} raises downside risk in a tightening regime.",
            evidence=_cite(factors, "debt_to_equity"), confidence=0.65))
    if f.get("net_margin") is not None and f["net_margin"] < 0.05:
        args.append(Argument(agent="bear", stance="bear",
            claim=f"Thin net margin of {f['net_margin']} leaves no cushion if costs rise or demand softens.",
            evidence=_cite(factors, "net_margin"), confidence=0.6))
    if q.get("ret_3m_pct") is not None and q["ret_3m_pct"] < 0:
        args.append(Argument(agent="bear", stance="bear",
            claim=f"Negative 3-month momentum of {q['ret_3m_pct']}% signals the market is repricing the name lower.",
            evidence=_cite(factors, "ret_3m_pct"), confidence=0.62))
    if q.get("above_sma_200") is False:
        args.append(Argument(agent="bear", stance="bear",
            claim=f"{ticker} trades below its 200-day average — a broken long-term trend.",
            evidence=_cite(factors, "above_sma_200"), confidence=0.58))
    headline, ncite = _news_cite(factors, positive=False)
    if headline:
        args.append(Argument(agent="bear", stance="bear",
            claim=f"A red flag in the news flow: \"{headline}\".",
            evidence=ncite, confidence=0.55))
    if news.get("negative", 0) > news.get("positive", 0):
        args.append(Argument(agent="bear", stance="bear",
            claim=f"Net news flow skews negative ({news['negative']} negative vs {news['positive']} positive headlines).",
            evidence=[], confidence=0.5))
    if not args:
        args.append(Argument(agent="bear", stance="bear",
            claim=f"The bear case for {ticker} is limited; valuation/froth risk is the main concern to monitor.",
            evidence=[], confidence=0.35))
    return _maybe_narrate("bear", ticker, args)


def rebuttals(ticker: str, factors: dict, bull: list[Argument], bear: list[Argument]) -> list[Argument]:
    """Each side attacks the other's weakest claim — surfaces real signal."""
    out: list[Argument] = []
    comp = factors["composite"]
    if bull:
        weakest = min(bull, key=lambda a: a.confidence)
        out.append(Argument(agent="bear", stance="bear",
            claim=f"Bear rebuttal: the bull leans on \"{weakest.claim[:60]}...\" but the blended evidence score is only {comp}, hardly a slam-dunk long.",
            evidence=[], confidence=0.5))
    if bear:
        weakest = min(bear, key=lambda a: a.confidence)
        out.append(Argument(agent="bull", stance="bull",
            claim=f"Bull rebuttal: the bear's \"{weakest.claim[:60]}...\" is a known risk already reflected in the {comp} composite; it is not a new disqualifier.",
            evidence=[], confidence=0.5))
    return out


def _maybe_narrate(side: str, ticker: str, args: list[Argument]) -> list[Argument]:
    """Optionally sharpen prose with an LLM. Numbers are preserved verbatim."""
    try:
        claims = "\n".join(f"- {a.claim}" for a in args)
        sys = (
            f"You are the {side.upper()} analyst on an investment committee. Rewrite each bullet "
            "as one punchy sentence. You MUST keep every number EXACTLY as given. Do not add new "
            "numbers. Return the same count of bullets, one per line, starting with '- '."
        )
        text, _ = complete(sys, f"Ticker {ticker}. Bullets:\n{claims}")
        lines = [ln.strip()[2:].strip() for ln in text.splitlines() if ln.strip().startswith("- ")]
        if len(lines) == len(args):
            for a, ln in zip(args, lines):
                a.claim = ln
    except NoLLMAvailable:
        pass
    except Exception:
        pass
    return args

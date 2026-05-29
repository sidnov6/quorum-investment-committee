"""Portfolio Assistant — a conversational helper that explains the committee's
decisions and answers questions about stocks in the universe.

Grounded: it pulls the same real factors/risk the committee used, and (when an LLM
key is set) narrates them. With no key it returns a deterministic, data-backed
answer. It NEVER invents numbers — every figure comes from the tools.
"""
from __future__ import annotations

import datetime as dt
import re

from quorum.committee.factors import compute_factors
from quorum.models.router import NoLLMAvailable, complete
from quorum.store import db
from quorum.tools.risk import ticker_risk
from quorum.universe import UNIVERSE, info, tickers

_TICKER_RE = re.compile(r"\b([A-Z]{1,5}(?:-[A-Z])?)\b")

_SYSTEM = (
    "You are the QUORUM Portfolio Assistant — a friendly, sharp investment-committee aide. "
    "You explain how the committee (bull, bear, macro strategist, quant risk officer, portfolio "
    "manager, critic) reached its decisions, and you answer questions about stocks in plain English. "
    "RULES: (1) Only use the numbers in the CONTEXT block — never invent figures. If a number isn't "
    "given, say you don't have it. (2) Be concise (2-5 sentences unless asked for more). (3) Always "
    "remind, when giving any view, that this is decision-support, not financial advice. (4) Refer to "
    "the agents by role to make the committee feel real."
)


def _detect_tickers(text: str) -> list[str]:
    uni = set(tickers())
    found = []
    for m in _TICKER_RE.findall(text.upper()):
        if m in uni and m not in found:
            found.append(m)
    # also match by company name
    for t, (name, _) in UNIVERSE.items():
        if name.lower().split()[0] in text.lower() and t not in found:
            found.append(t)
    return found[:4]


def _ticker_context(t: str, as_of: str) -> str:
    f = compute_factors(t, as_of)
    r = ticker_risk(t, as_of)
    name, sector = info(t)
    p = f["pillars"]
    q = f["quote"]
    fund = f["fundamentals"]
    news = f["news_summary"]
    lines = [
        f"{t} ({name}, {sector}) as of {as_of}:",
        f"  composite score: {f['composite']} (range -1..+1)",
        f"  pillars: quality={p.get('quality')}, momentum={p.get('momentum')}, "
        f"sentiment={p.get('sentiment')}, value={p.get('value')}",
    ]
    if q.get("close") is not None:
        lines.append(f"  price: ${q.get('close'):.2f}; 3m return: {q.get('ret_3m_pct')}%; "
                     f"12m return: {q.get('ret_12m_pct')}%; above 200d avg: {q.get('above_sma_200')}")
    if fund.get("net_margin") is not None:
        lines.append(f"  fundamentals: net_margin={fund.get('net_margin')}, roe={fund.get('roe')}, "
                     f"debt/equity={fund.get('debt_to_equity')}")
    if r.get("available"):
        lines.append(f"  risk: annual_vol={r['annualized_vol']}, beta={r.get('beta')}, "
                     f"max_drawdown={r['max_drawdown']}, 1d_VaR(95%)={r['var_1d_hist']}, sharpe={r['sharpe']}")
    if news.get("count"):
        lines.append(f"  news: {news['count']} items, net tilt {news.get('net_tilt')}, "
                     f"top +: {news.get('top_positive')}, top -: {news.get('top_negative')}")
    return "\n".join(lines)


def _last_decision_context() -> str:
    runs = db.list_committee_runs(limit=1)
    if not runs:
        return "No committee decision has been recorded yet."
    full = db.get_committee_run(runs[0]["id"])
    if not full or not full.get("decision"):
        return "No committee decision available."
    d = full["decision"]
    lines = [f"Most recent committee decision (as of {full['mandate']['as_of_date']}, "
             f"status {full['status']}, confidence {d['confidence']}):"]
    for p in d["positions"]:
        if p["target_weight"] > 0:
            lines.append(f"  {p['ticker']}: {p['action']} {p['target_weight']*100:.1f}% "
                         f"(conf {p['confidence']}) — {p['rationale']}")
    lines.append(f"  cash: {d['cash_weight']*100:.1f}%")
    lines.append(f"  PM rationale: {d['rationale']}")
    if d.get("surviving_counterargument"):
        lines.append(f"  strongest dissent: {d['surviving_counterargument']}")
    if full.get("macro_view"):
        lines.append(f"  macro regime: {full['macro_view']['regime']} (tilt {full['macro_view']['tilt']})")
    return "\n".join(lines)


def _portfolio_context() -> str:
    from quorum import paper
    snap = paper.snapshot()
    if not snap.get("curve"):
        return "The paper portfolio has no track record yet."
    lines = [f"Paper portfolio: value ${snap['value']:,.2f} "
             f"({snap['total_return']*100:+.1f}% since inception), cash ${snap.get('cash',0):,.2f}."]
    for h in snap.get("holdings", [])[:8]:
        lines.append(f"  holds {h['ticker']} ({h['sector']}): ${h['value']:,.2f}")
    return "\n".join(lines)


def _deterministic_answer(question: str, tickers_found: list[str], as_of: str) -> str:
    """Fallback reply when no LLM key is configured — still data-grounded."""
    parts = []
    if "decision" in question.lower() or "why" in question.lower() or "memo" in question.lower():
        parts.append(_last_decision_context())
    if "portfolio" in question.lower() or "holding" in question.lower():
        parts.append(_portfolio_context())
    for t in tickers_found:
        parts.append(_ticker_context(t, as_of))
    if not parts:
        parts.append("I can explain the committee's latest decision, your paper portfolio, or any "
                     "stock in the 51-name universe. Try asking 'Why did the committee pick NVDA?' "
                     "or 'How risky is XOM?'")
    parts.append("\n(Decision-support only — not financial advice.)")
    return "\n\n".join(parts)


def chat(question: str, history: list[dict] | None = None, as_of: str | None = None) -> dict:
    as_of = as_of or dt.date.today().isoformat()
    found = _detect_tickers(question)

    # Assemble grounded context.
    ctx_blocks = [_last_decision_context()]
    ql = question.lower()
    if "portfolio" in ql or "holding" in ql or "my " in ql:
        ctx_blocks.append(_portfolio_context())
    for t in found:
        ctx_blocks.append(_ticker_context(t, as_of))
    context = "\n\n".join(ctx_blocks)

    # Build the prompt with short history.
    convo = ""
    for turn in (history or [])[-6:]:
        role = "User" if turn.get("role") == "user" else "Assistant"
        convo += f"{role}: {turn.get('content','')}\n"

    prompt = (f"CONTEXT (the only facts you may cite):\n{context}\n\n"
              f"{convo}User: {question}\nAssistant:")

    try:
        text, model = complete(_SYSTEM, prompt)
        return {"answer": text.strip(), "model": model, "tickers": found, "grounded_on": context}
    except NoLLMAvailable:
        return {"answer": _deterministic_answer(question, found, as_of),
                "model": "deterministic", "tickers": found, "grounded_on": context}
    except Exception as e:
        return {"answer": _deterministic_answer(question, found, as_of),
                "model": f"fallback ({type(e).__name__})", "tickers": found, "grounded_on": context}

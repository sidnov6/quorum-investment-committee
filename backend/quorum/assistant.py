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
    "You are the QUORUM Portfolio Assistant — a sharp investment-committee aide. You do two things: "
    "(A) explain how the committee (bull, bear, macro strategist, quant risk officer, portfolio "
    "manager, critic) reached its decisions, and (B) reason about market SCENARIOS the user poses "
    "(e.g. geopolitical conflict, rate shocks, oil spikes) to suggest which names/sectors in the "
    "universe would likely benefit (buy candidates) vs. suffer (sell/avoid candidates).\n"
    "RULES:\n"
    "1. NUMBERS must come only from the CONTEXT block — never invent a figure, price, or return. If a "
    "specific number isn't in context, speak qualitatively instead.\n"
    "2. For SCENARIO questions, you MAY reason with general, well-established market cause-and-effect "
    "(e.g. 'conflict with China would pressure companies with heavy China revenue or supply chains "
    "like semiconductors and consumer electronics, while defense, domestic energy, and gold miners "
    "often benefit'). Map that reasoning onto the ACTUAL tickers in the UNIVERSE context, naming "
    "concrete BUY candidates and SELL/AVOID candidates by ticker and sector.\n"
    "3. Be structured for scenarios: a one-line thesis, then a short 'Lean into' list and a 'Reduce/avoid' "
    "list with one reason each. Otherwise be concise (2-5 sentences).\n"
    "4. ALWAYS end with a one-line reminder that this is decision-support, not financial advice, and "
    "that scenario views are hypothetical reasoning, not predictions.\n"
    "5. Refer to the committee agents by role to make it feel like a real desk."
)

# Lightweight scenario tags → which sectors tend to benefit / suffer. These are
# qualitative priors that orient the LLM; it still names concrete tickers from the universe.
_SCENARIO_HINTS = {
    "china|taiwan|trade war|tariff|conflict|war|invade|attack|geopolit": {
        "benefit": ["Energy", "Materials", "Utilities", "Consumer Staples"],
        "suffer": ["Information Technology", "Consumer Discretionary"],
        "note": "China-exposed tech/semis and consumer hardware face supply-chain and revenue risk; "
                "domestic energy, miners (incl. gold), defense-like industrials and staples are more defensive.",
    },
    "rate|interest|fed|hike|inflation|cpi": {
        "benefit": ["Financials", "Energy"],
        "suffer": ["Information Technology", "Real Estate", "Utilities"],
        "note": "Higher rates pressure long-duration growth/tech, REITs and rate-sensitive utilities; "
                "banks can benefit from wider margins.",
    },
    "oil|energy crisis|opec|crude": {
        "benefit": ["Energy", "Materials"],
        "suffer": ["Consumer Discretionary", "Industrials"],
        "note": "An oil spike helps energy producers but squeezes transport-heavy and discretionary names.",
    },
    "recession|slowdown|downturn|crash": {
        "benefit": ["Consumer Staples", "Utilities", "Health Care"],
        "suffer": ["Consumer Discretionary", "Financials", "Materials"],
        "note": "Defensives (staples, utilities, healthcare) hold up; cyclicals and discretionary suffer.",
    },
}


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


def _detect_scenario(question: str) -> dict | None:
    """Return the matching scenario hint (sectors that benefit/suffer) if the question
    is a 'what if X happens' style query."""
    import re as _re
    ql = question.lower()
    for pattern, hint in _SCENARIO_HINTS.items():
        if _re.search(pattern, ql):
            return hint
    # generic scenario trigger words even if no specific hint matched
    if _re.search(r"\bif\b|\bwhat if\b|\bscenario\b|\bhappens\b|\bwould\b|buy vs sell|which stock", ql):
        return {"benefit": [], "suffer": [], "note": "General scenario — reason from sector exposure."}
    return None


def _universe_context() -> str:
    """Full universe grouped by sector — lets the assistant map a scenario onto real tickers."""
    lines = ["INVESTABLE UNIVERSE (the only tickers you may recommend), grouped by sector:"]
    sectors: dict[str, list[str]] = {}
    for t, (name, sector) in UNIVERSE.items():
        sectors.setdefault(sector, []).append(f"{t} ({name})")
    for sector, items in sorted(sectors.items()):
        lines.append(f"  {sector}: " + ", ".join(items))
    return "\n".join(lines)


def _scenario_context(hint: dict) -> str:
    if not hint:
        return ""
    lines = ["SCENARIO REASONING AID (qualitative sector priors — use to pick concrete tickers):"]
    if hint.get("benefit"):
        lines.append("  Sectors that typically BENEFIT: " + ", ".join(hint["benefit"]))
    if hint.get("suffer"):
        lines.append("  Sectors that typically SUFFER: " + ", ".join(hint["suffer"]))
    if hint.get("note"):
        lines.append("  Note: " + hint["note"])
    return "\n".join(lines)


def _deterministic_scenario_answer(hint: dict) -> str:
    """Sector-based buy/sell suggestion when no LLM is available (or rate-limited)."""
    by_sec: dict[str, list[str]] = {}
    for t, (_, sector) in UNIVERSE.items():
        by_sec.setdefault(sector, []).append(t)

    def _names(sectors: list[str]) -> list[str]:
        out = []
        for s in sectors:
            for t in by_sec.get(s, []):
                out.append(f"{t} ({info(t)[1]})")
        return out

    parts = [f"**Scenario view.** {hint.get('note', 'Based on sector exposure within the universe.')}"]
    buys = _names(hint.get("benefit", []))
    sells = _names(hint.get("suffer", []))
    if buys:
        parts.append("**Lean into (likely beneficiaries):**\n- " + "\n- ".join(buys[:10]))
    if sells:
        parts.append("**Reduce / avoid (likely to suffer):**\n- " + "\n- ".join(sells[:10]))
    parts.append("_Hypothetical scenario reasoning from sector exposure — decision-support only, "
                 "not financial advice or a prediction._")
    return "\n\n".join(parts)


def _deterministic_answer(question: str, tickers_found: list[str], as_of: str) -> str:
    """Fallback reply when no LLM key is configured — still data-grounded."""
    scen = _detect_scenario(question)
    if scen and (scen.get("benefit") or scen.get("suffer")):
        return _deterministic_scenario_answer(scen)
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
    scenario = _detect_scenario(question)

    # Assemble grounded context.
    ctx_blocks = [_last_decision_context()]
    ql = question.lower()
    if "portfolio" in ql or "holding" in ql or "my " in ql:
        ctx_blocks.append(_portfolio_context())
    # For scenario questions, give the assistant the full universe + sector priors
    # so it can name concrete buy/sell candidates instead of dodging.
    if scenario is not None:
        ctx_blocks.append(_universe_context())
        sc = _scenario_context(scenario)
        if sc:
            ctx_blocks.append(sc)
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

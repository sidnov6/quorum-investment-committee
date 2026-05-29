"""The committee orchestrator — a cyclic debate with convergence + human gate.

Flow: briefing -> opening cases (bull/bear independent) -> rebuttal -> macro+risk ->
synthesis -> critique -> (loop if serious objection, capped) -> decided.

Emits Turn events via an optional callback so the UI can stream the debate live.
The math/numbers all originate in the deterministic factor + risk engines; the LLM
(if configured) only sharpens prose. Grounding guardrail rejects unsourced numbers.
"""
from __future__ import annotations

import datetime as dt
from typing import Callable, Optional

from quorum.committee.agents import critic as critic_agent
from quorum.committee.agents import debaters
from quorum.committee.agents import pm as pm_agent
from quorum.committee.agents import research
from quorum.committee.agents import risk_officer
from quorum.committee.agents.macro_agent import macro_view
from quorum.committee.factors import compute_factors
from quorum.committee.grounding import enforce
from quorum.config import settings
from quorum.models.router import available_providers
from quorum.schemas import (
    AuditEntry, CommitteeResult, Mandate, ScreenRow, Turn,
)
from quorum.universe import info

Emitter = Optional[Callable[[Turn], None]]


def _now() -> str:
    return dt.datetime.utcnow().isoformat()


def _model_label() -> str:
    prov = available_providers()
    return prov[0] if prov else "deterministic"


def run_committee(mandate: Mandate, emit: Emitter = None) -> CommitteeResult:
    model = _model_label()
    result = CommitteeResult(mandate=mandate, status="briefing")

    def push(turn: Turn):
        result.transcript.append(turn)
        if emit:
            try:
                emit(turn)
            except Exception:
                pass

    def audit(agent: str, tools: list[str], grounding_ok=True, notes=""):
        result.audit_trail.append(AuditEntry(
            agent=agent, model=model, tools_called=tools,
            grounding_ok=grounding_ok, grounding_notes=notes, ts=_now()))

    # ---------- 0. Universe screen ----------
    # The Research analyst scores the WHOLE universe, then the Chair shortlists the
    # most decision-relevant names for the debate floor (like a real IC short list).
    all_factors: dict[str, dict] = {}
    for t in mandate.candidates:
        all_factors[t] = compute_factors(t, mandate.as_of_date)
    audit("research", ["get_fundamentals", "get_prices", "get_news"])

    ranked = sorted(mandate.candidates, key=lambda t: all_factors[t]["composite"], reverse=True)
    # shortlist = strongest longs + a couple of notable avoids (so the bear has targets)
    k = max(2, min(mandate.shortlist_k, len(ranked)))
    top = ranked[: max(1, k - 2)]
    bottom = [t for t in ranked[::-1] if t not in top][: k - len(top)]
    shortlist = top + bottom
    result.shortlist = shortlist
    for t in mandate.candidates:
        result.screen.append(ScreenRow(
            ticker=t, sector=info(t)[1], composite=all_factors[t]["composite"],
            pillars=all_factors[t]["pillars"], shortlisted=t in shortlist))
    push(Turn(round=0, agent="chair", kind="brief",
              content=f"Screened {len(mandate.candidates)} names; shortlisted {len(shortlist)} "
                      f"for debate: {', '.join(shortlist)}.",
              payload={"screen": [r.model_dump() for r in result.screen], "shortlist": shortlist},
              ts=_now()))

    # ---------- 1. Briefing (shortlist only) ----------
    factors_by_ticker: dict[str, dict] = {t: all_factors[t] for t in shortlist}
    for t in shortlist:
        f = factors_by_ticker[t]
        brief = research.build_brief(t, mandate.as_of_date, f)
        result.briefs.append(brief)
        push(Turn(round=0, agent="research", kind="brief",
                  content=f"Evidence brief for {t}: composite {f['composite']}, "
                          f"{f['news_summary']['count']} news items.",
                  payload={"ticker": t, "brief": brief.model_dump(),
                           "factors": {"pillars": f["pillars"], "composite": f["composite"]}},
                  ts=_now()))

    # ---------- Macro (regime context, once) ----------
    result.status = "briefing"
    macro = macro_view(mandate.as_of_date)
    result.macro_view = macro
    audit("macro", ["get_macro"])
    push(Turn(round=0, agent="macro", kind="macro",
              content=f"Macro regime: {macro.regime} (tilt {macro.tilt:+.2f}). {macro.summary}",
              payload=macro.model_dump(), ts=_now()))

    # ---------- Debate rounds ----------
    rounds = 0
    decision = None
    critique = None
    while rounds < settings.MAX_DEBATE_ROUNDS:
        rounds += 1
        result.status = "debating"
        result.bull_case, result.bear_case, result.rebuttals = [], [], []

        for t in shortlist:
            f = factors_by_ticker[t]
            bulls = debaters.bull_case(t, f)
            bears = debaters.bear_case(t, f)
            # grounding gate
            bulls, bn = enforce(bulls)
            bears, rn = enforce(bears)
            if bn or rn:
                audit("guardrail", [], grounding_ok=False, notes="; ".join(bn + rn))
            result.bull_case += bulls
            result.bear_case += bears
            for a in bulls:
                push(Turn(round=rounds, agent="bull", kind="case", content=a.claim,
                          payload={"ticker": t, "confidence": a.confidence,
                                   "evidence": [c.model_dump() for c in a.evidence]}, ts=_now()))
            for a in bears:
                push(Turn(round=rounds, agent="bear", kind="case", content=a.claim,
                          payload={"ticker": t, "confidence": a.confidence,
                                   "evidence": [c.model_dump() for c in a.evidence]}, ts=_now()))
            rebs = debaters.rebuttals(t, f, bulls, bears)
            result.rebuttals += rebs
            for a in rebs:
                push(Turn(round=rounds, agent=a.agent, kind="rebuttal", content=a.claim,
                          payload={"ticker": t}, ts=_now()))
        audit("bull", ["get_fundamentals", "get_prices"])
        audit("bear", ["get_fundamentals", "get_prices", "get_news"])

        # ---------- Risk + synthesis ----------
        result.status = "synthesis"
        # PM proposes within constraints (uses default constraints first)
        provisional = pm_agent.synthesize(
            factors_by_ticker, macro,
            {"max_position_weight": settings.MAX_POSITION_WEIGHT},
            result.bear_case, mandate.horizon_days)
        weights = {p.ticker: p.target_weight for p in provisional.positions}

        result.status = "risk"
        risk = risk_officer.assess(shortlist, weights, mandate.as_of_date, mandate.benchmark)
        result.risk_assessment = risk
        audit("risk", ["compute_risk_metrics", "get_prices"])
        push(Turn(round=rounds, agent="risk", kind="risk",
                  content=(f"Portfolio vol {risk.portfolio.get('annualized_vol','n/a')}, "
                           f"{'VETO: ' + risk.veto_reason if risk.veto else 'within limits'}."),
                  payload=risk.model_dump(), ts=_now()))

        # If risk vetoes, PM re-synthesizes honoring tighter caps.
        decision = provisional
        if risk.veto:
            decision = pm_agent.synthesize(
                factors_by_ticker, macro, risk.constraints, result.bear_case, mandate.horizon_days)
        result.decision = decision
        push(Turn(round=rounds, agent="pm", kind="decision",
                  content=decision.rationale, payload=decision.model_dump(), ts=_now()))

        # ---------- Critique ----------
        result.status = "critique"
        critique = critic_agent.critique(decision, factors_by_ticker, risk)
        result.critique = critique
        audit("critic", [])
        push(Turn(round=rounds, agent="critic", kind="critique",
                  content=" | ".join(critique.findings), payload=critique.model_dump(), ts=_now()))

        # ---------- Convergence ----------
        converged = (not critique.recommend_another_round) and decision.confidence >= settings.PM_CONFIDENCE_FLOOR
        if converged:
            break

    result.rounds_run = rounds
    result.status = "decided"
    if critique and critique.serious_objection and rounds >= settings.MAX_DEBATE_ROUNDS:
        result.status = "escalated"  # honest non-convergence
    push(Turn(round=rounds, agent="chair", kind="decision",
              content=f"Committee {'escalated (unresolved dissent)' if result.status=='escalated' else 'reached a decision'} "
                      f"after {rounds} round(s). Awaiting human gate.",
              payload={"status": result.status}, ts=_now()))
    return result

"""Devil's-Advocate / Critic Agent — stress-test the PM's decision for groupthink."""
from __future__ import annotations

from quorum.schemas import Critique, Decision


def critique(decision: Decision, factors_by_ticker: dict[str, dict], risk) -> Critique:
    findings: list[str] = []
    serious = False

    # Over-concentration on a single thin-evidence name.
    for p in decision.positions:
        if p.target_weight >= 0.30:
            f = factors_by_ticker.get(p.ticker, {})
            present = sum(1 for v in f.get("pillars", {}).values() if v is not None)
            if present < 3:
                findings.append(
                    f"{p.ticker} carries {p.target_weight:.0%} on only {present}/4 evidence pillars — "
                    "concentration on incomplete evidence."
                )
                serious = True

    # Decision relies on momentum alone (chasing).
    for p in decision.positions:
        if p.target_weight > 0.1:
            pil = factors_by_ticker.get(p.ticker, {}).get("pillars", {})
            mom = pil.get("momentum")
            qual = pil.get("quality")
            if mom is not None and mom > 0.3 and (qual is None or qual < 0):
                findings.append(f"{p.ticker} is a momentum-only call (weak/absent quality) — risk of chasing.")

    # Low confidence but still deploying lots of capital.
    invested = sum(p.target_weight for p in decision.positions)
    if decision.confidence < 0.55 and invested > 0.6:
        findings.append(
            f"Confidence {decision.confidence} is low yet {invested:.0%} is deployed — consider more cash."
        )
        serious = True

    # Risk veto ignored?
    if risk and getattr(risk, "veto", False):
        findings.append(f"Risk veto active: {risk.veto_reason}")
        serious = True

    if not findings:
        findings.append("No serious groupthink or concentration flaws detected; dissent is preserved in the memo.")

    return Critique(
        serious_objection=serious,
        findings=findings,
        recommend_another_round=serious,
    )

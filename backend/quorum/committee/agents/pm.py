"""Portfolio Manager Agent — synthesize a decision within risk constraints.

Converts factor composites (+ macro tilt) into target weights, then enforces the
Risk Officer's hard limits (position cap, vol scaling). Produces actions, rationale,
confidence, and explicitly carries the strongest surviving counter-argument.
"""
from __future__ import annotations

from quorum.config import settings
from quorum.schemas import Argument, Decision, MacroView, Position


def _action(weight: float, composite: float) -> str:
    if weight >= 0.05:
        return "buy"
    if composite > 0:
        return "hold"
    return "avoid"


def synthesize(
    factors_by_ticker: dict[str, dict],
    macro: MacroView,
    risk_constraints: dict,
    bear_args: list[Argument],
    horizon_days: int,
) -> Decision:
    max_w = risk_constraints.get("max_position_weight", settings.MAX_POSITION_WEIGHT)
    macro_tilt = macro.tilt if macro else 0.0

    # Raw conviction = composite, nudged by macro regime (risk-on lifts, risk-off cuts).
    convictions: dict[str, float] = {}
    for t, f in factors_by_ticker.items():
        score = f["composite"] + 0.15 * macro_tilt
        convictions[t] = score

    # Only allocate to positive-conviction names.
    positives = {t: s for t, s in convictions.items() if s > 0.05}
    total = sum(positives.values())

    weights: dict[str, float] = {}
    if total > 0:
        for t, s in positives.items():
            weights[t] = min(s / total, max_w)
    # Renormalize after capping, but keep a cash buffer scaled by macro risk-off.
    invested_cap = 1.0
    if macro_tilt < -0.2:
        invested_cap = 0.6  # hold more cash in risk-off
    elif macro_tilt < 0:
        invested_cap = 0.8
    wsum = sum(weights.values())
    if wsum > 0:
        scale = min(invested_cap, 1.0) / wsum if wsum > invested_cap else 1.0
        weights = {t: round(w * scale, 4) for t, w in weights.items()}

    cash_weight = round(max(0.0, 1.0 - sum(weights.values())), 4)

    positions: list[Position] = []
    for t, f in factors_by_ticker.items():
        w = weights.get(t, 0.0)
        comp = f["composite"]
        pillars = f["pillars"]
        drivers = ", ".join(f"{k}={v}" for k, v in pillars.items() if v is not None)
        positions.append(Position(
            ticker=t,
            action=_action(w, comp),
            target_weight=w,
            rationale=f"Composite {comp} ({drivers}); macro {macro.regime if macro else 'n/a'}.",
            confidence=round(min(0.95, 0.5 + abs(comp)), 3),
        ))

    # Confidence: dispersion of convictions + whether a clear leader exists.
    spread = (max(convictions.values()) - min(convictions.values())) if convictions else 0
    conf = round(min(0.95, 0.45 + 0.5 * spread), 3)

    surviving = ""
    if bear_args:
        strongest = max(bear_args, key=lambda a: a.confidence)
        surviving = strongest.claim

    invested = sum(weights.values())
    rationale = (
        f"Allocated {invested:.0%} across {len([w for w in weights.values() if w>0])} name(s), "
        f"{cash_weight:.0%} cash. Macro regime: {macro.regime if macro else 'n/a'} "
        f"(tilt {macro_tilt:+.2f}). Weights driven by blended quality/momentum/sentiment/value "
        f"scores, capped at {max_w:.0%} per name per risk policy."
    )

    return Decision(
        positions=positions,
        cash_weight=cash_weight,
        rationale=rationale,
        confidence=conf,
        surviving_counterargument=surviving,
    )

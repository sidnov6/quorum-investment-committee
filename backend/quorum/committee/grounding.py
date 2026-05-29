"""Grounding guardrail: every numeric claim must trace to a fetched datum.

Deterministic check — extract numbers from an argument's text and verify each
appears in the citation set (within tolerance). Unsourced numbers fail the gate.
"""
from __future__ import annotations

import re

from quorum.schemas import Argument

_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _numbers(text: str) -> list[float]:
    out = []
    for m in _NUM_RE.findall(text):
        try:
            out.append(float(m))
        except ValueError:
            pass
    return out


def verify_argument(arg: Argument, tol: float = 0.02) -> tuple[bool, str]:
    """True if every number in the claim matches a citation value (abs or relative)."""
    cited = []
    for c in arg.evidence:
        try:
            cited.append(float(c.value))
        except (TypeError, ValueError):
            continue
        # also allow the percentage form
    claim_nums = _numbers(arg.claim)
    unmatched = []
    for n in claim_nums:
        # ignore small structural integers (years, counts <= 12, round percents are still checked)
        if n.is_integer() and abs(n) <= 12:
            continue
        ok = False
        for cv in cited:
            if cv == 0:
                ok = ok or abs(n) < 1e-9
            elif abs(n - cv) <= tol or abs(n - cv) / (abs(cv) + 1e-9) <= 0.05:
                ok = True
            # percent vs fraction tolerance (0.25 vs 25)
            elif abs(n - cv * 100) <= 1.0 or abs(n - cv / 100) <= tol:
                ok = True
            if ok:
                break
        if not ok:
            unmatched.append(n)
    if unmatched:
        return False, f"Unsourced numbers: {unmatched}"
    return True, "ok"


def enforce(args: list[Argument]) -> tuple[list[Argument], list[str]]:
    """Drop arguments whose numeric claims aren't grounded; report what was rejected."""
    kept, notes = [], []
    for a in args:
        ok, msg = verify_argument(a)
        if ok:
            kept.append(a)
        else:
            notes.append(f"[{a.agent}] rejected: {msg} | claim='{a.claim[:80]}'")
    return kept, notes

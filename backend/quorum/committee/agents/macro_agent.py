"""Macro Strategist Agent — wrap the macro tool into a committee view + tilt."""
from __future__ import annotations

from quorum.schemas import Citation, MacroView
from quorum.tools.macro import get_macro


def macro_view(as_of: str) -> MacroView:
    m = get_macro(as_of)
    return MacroView(
        regime=m["regime"],
        summary=m["summary"],
        signals=m.get("signals", {}),
        citations=[Citation(**c) for c in m.get("citations", [])],
        tilt=m.get("tilt", 0.0),
    )

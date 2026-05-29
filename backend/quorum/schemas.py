"""Typed contracts shared across the committee. Pydantic = validation + serialization."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Stance = Literal["bull", "bear", "neutral"]
Action = Literal["buy", "hold", "avoid", "trim"]
Status = Literal[
    "briefing", "debating", "risk", "synthesis", "critique", "decided", "escalated", "error"
]


class Citation(BaseModel):
    """Every quantitative claim must point back to a fetched datum."""
    source: str            # e.g. "SEC EDGAR CompanyFacts", "yfinance", "FRED"
    field: str             # e.g. "Revenues", "close", "DGS10"
    value: float | str
    as_of: str             # the date the datum is valid for
    unit: str = ""


class Argument(BaseModel):
    agent: str
    claim: str
    evidence: list[Citation] = Field(default_factory=list)
    confidence: float = 0.5
    stance: Stance = "neutral"


class Mandate(BaseModel):
    candidates: list[str]                       # tickers under consideration (the universe)
    as_of_date: str                             # point-in-time anchor (YYYY-MM-DD)
    horizon_days: int = 60
    objective: str = "Maximize risk-adjusted return over the horizon."
    benchmark: str = "SPY"
    shortlist_k: int = 8                         # how many names reach the debate floor


class ScreenRow(BaseModel):
    ticker: str
    sector: str = ""
    composite: float
    pillars: dict = Field(default_factory=dict)
    shortlisted: bool = False


class EvidenceBrief(BaseModel):
    ticker: str
    as_of: str
    fundamentals: dict = Field(default_factory=dict)
    price_summary: dict = Field(default_factory=dict)
    news: list[dict] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)


class MacroView(BaseModel):
    regime: str
    summary: str
    signals: dict = Field(default_factory=dict)
    citations: list[Citation] = Field(default_factory=list)
    tilt: float = 0.0   # -1 risk-off ... +1 risk-on


class RiskAssessment(BaseModel):
    per_ticker: dict = Field(default_factory=dict)   # ticker -> metrics
    portfolio: dict = Field(default_factory=dict)
    constraints: dict = Field(default_factory=dict)
    veto: bool = False
    veto_reason: str = ""
    citations: list[Citation] = Field(default_factory=list)


class Position(BaseModel):
    ticker: str
    action: Action
    target_weight: float
    rationale: str
    confidence: float


class Decision(BaseModel):
    positions: list[Position]
    cash_weight: float = 0.0
    rationale: str = ""
    confidence: float = 0.5
    surviving_counterargument: str = ""


class Critique(BaseModel):
    serious_objection: bool
    findings: list[str] = Field(default_factory=list)
    recommend_another_round: bool = False


class AuditEntry(BaseModel):
    agent: str
    model: str
    tools_called: list[str] = Field(default_factory=list)
    grounding_ok: bool = True
    grounding_notes: str = ""
    ts: str


class Turn(BaseModel):
    round: int
    agent: str
    kind: str                 # "brief" | "case" | "rebuttal" | "macro" | "risk" | "decision" | "critique"
    content: str
    payload: dict = Field(default_factory=dict)
    ts: str


class CommitteeResult(BaseModel):
    mandate: Mandate
    status: Status
    screen: list[ScreenRow] = Field(default_factory=list)   # full-universe scan
    shortlist: list[str] = Field(default_factory=list)
    briefs: list[EvidenceBrief] = Field(default_factory=list)
    bull_case: list[Argument] = Field(default_factory=list)
    bear_case: list[Argument] = Field(default_factory=list)
    rebuttals: list[Argument] = Field(default_factory=list)
    macro_view: Optional[MacroView] = None
    risk_assessment: Optional[RiskAssessment] = None
    decision: Optional[Decision] = None
    critique: Optional[Critique] = None
    rounds_run: int = 0
    transcript: list[Turn] = Field(default_factory=list)
    audit_trail: list[AuditEntry] = Field(default_factory=list)

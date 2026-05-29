"""Central configuration for QUORUM. No hardcoded knobs scattered across the code."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
STORE_DIR = DATA_DIR / "store"
DB_PATH = STORE_DIR / "quorum.db"

for _d in (SNAPSHOT_DIR, STORE_DIR):
    _d.mkdir(parents=True, exist_ok=True)


class Settings:
    """Runtime settings, env-overridable. Sensible free-tier defaults."""

    # --- Identity required by SEC EDGAR fair-access policy ---
    SEC_USER_AGENT: str = os.getenv("SEC_USER_AGENT", "QUORUM Research contact@quorum.dev")

    # --- Optional API keys (system degrades gracefully without them) ---
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    FINNHUB_API_KEY: str = os.getenv("FINNHUB_API_KEY", "")
    FRED_API_KEY: str = os.getenv("FRED_API_KEY", "")

    # --- LLM routing ---
    # "auto" picks the first provider with a key, else deterministic.
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "auto")
    LLM_TIMEOUT: int = int(os.getenv("LLM_TIMEOUT", "45"))

    # --- Committee behaviour ---
    MAX_DEBATE_ROUNDS: int = int(os.getenv("MAX_DEBATE_ROUNDS", "3"))
    PM_CONFIDENCE_FLOOR: float = float(os.getenv("PM_CONFIDENCE_FLOOR", "0.55"))

    # --- Risk limits (the Risk Officer's hard constraints) ---
    MAX_POSITION_WEIGHT: float = float(os.getenv("MAX_POSITION_WEIGHT", "0.35"))
    MAX_PORTFOLIO_VOL: float = float(os.getenv("MAX_PORTFOLIO_VOL", "0.45"))  # annualized
    VAR_CONFIDENCE: float = float(os.getenv("VAR_CONFIDENCE", "0.95"))
    MAX_DRAWDOWN_LIMIT: float = float(os.getenv("MAX_DRAWDOWN_LIMIT", "0.50"))

    # --- Backtest ---
    STARTING_CASH: float = float(os.getenv("STARTING_CASH", "10000"))
    REBALANCE_EVERY_DAYS: int = int(os.getenv("REBALANCE_EVERY_DAYS", "5"))  # weekly committee
    TRADING_COST_BPS: float = float(os.getenv("TRADING_COST_BPS", "5"))  # 5 bps per trade

    # --- Cache TTLs ---
    QUOTE_CACHE_TTL_SEC: int = int(os.getenv("QUOTE_CACHE_TTL_SEC", "900"))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

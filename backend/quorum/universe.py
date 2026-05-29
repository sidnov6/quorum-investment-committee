"""Investable universe — a deliberately diversified, multi-sector set of US large/mid caps.

Not a tech-only cherry-pick: every GICS sector is represented so the committee must
choose across genuinely different businesses and regimes. Editable via conf or API.
"""
from __future__ import annotations

# ticker -> (company, sector). ~50 names spanning all 11 GICS sectors so the
# committee chooses across genuinely different businesses, not a tech monoculture.
UNIVERSE: dict[str, tuple[str, str]] = {
    # Information Technology (7)
    "MSFT": ("Microsoft", "Information Technology"),
    "AAPL": ("Apple", "Information Technology"),
    "NVDA": ("NVIDIA", "Information Technology"),
    "CRM": ("Salesforce", "Information Technology"),
    "TXN": ("Texas Instruments", "Information Technology"),
    "ORCL": ("Oracle", "Information Technology"),
    "AMD": ("Advanced Micro Devices", "Information Technology"),
    # Communication Services (5)
    "GOOGL": ("Alphabet", "Communication Services"),
    "META": ("Meta Platforms", "Communication Services"),
    "DIS": ("Walt Disney", "Communication Services"),
    "NFLX": ("Netflix", "Communication Services"),
    "TMUS": ("T-Mobile US", "Communication Services"),
    # Consumer Discretionary (6)
    "AMZN": ("Amazon", "Consumer Discretionary"),
    "TSLA": ("Tesla", "Consumer Discretionary"),
    "NKE": ("Nike", "Consumer Discretionary"),
    "MCD": ("McDonald's", "Consumer Discretionary"),
    "HD": ("Home Depot", "Consumer Discretionary"),
    "SBUX": ("Starbucks", "Consumer Discretionary"),
    # Consumer Staples (5)
    "PG": ("Procter & Gamble", "Consumer Staples"),
    "KO": ("Coca-Cola", "Consumer Staples"),
    "PEP": ("PepsiCo", "Consumer Staples"),
    "COST": ("Costco", "Consumer Staples"),
    "WMT": ("Walmart", "Consumer Staples"),
    # Health Care (6)
    "UNH": ("UnitedHealth", "Health Care"),
    "JNJ": ("Johnson & Johnson", "Health Care"),
    "MRK": ("Merck", "Health Care"),
    "LLY": ("Eli Lilly", "Health Care"),
    "ABBV": ("AbbVie", "Health Care"),
    "PFE": ("Pfizer", "Health Care"),
    # Financials (6)
    "JPM": ("JPMorgan Chase", "Financials"),
    "V": ("Visa", "Financials"),
    "MA": ("Mastercard", "Financials"),
    "BAC": ("Bank of America", "Financials"),
    "GS": ("Goldman Sachs", "Financials"),
    "BRK-B": ("Berkshire Hathaway", "Financials"),
    # Industrials (5)
    "CAT": ("Caterpillar", "Industrials"),
    "HON": ("Honeywell", "Industrials"),
    "UNP": ("Union Pacific", "Industrials"),
    "BA": ("Boeing", "Industrials"),
    "GE": ("GE Aerospace", "Industrials"),
    # Energy (3)
    "XOM": ("Exxon Mobil", "Energy"),
    "CVX": ("Chevron", "Energy"),
    "COP": ("ConocoPhillips", "Energy"),
    # Utilities (2)
    "NEE": ("NextEra Energy", "Utilities"),
    "DUK": ("Duke Energy", "Utilities"),
    # Materials (3)
    "LIN": ("Linde", "Materials"),
    "FCX": ("Freeport-McMoRan", "Materials"),
    "NEM": ("Newmont", "Materials"),
    # Real Estate (3)
    "AMT": ("American Tower", "Real Estate"),
    "PLD": ("Prologis", "Real Estate"),
    "O": ("Realty Income", "Real Estate"),
}

SECTORS = sorted({s for _, s in UNIVERSE.values()})


def tickers() -> list[str]:
    return list(UNIVERSE.keys())


def by_sector() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for t, (_, s) in UNIVERSE.items():
        out.setdefault(s, []).append(t)
    return out


def diversified_sample(n_per_sector: int = 1) -> list[str]:
    """One (or more) name per sector — a balanced default committee mandate."""
    out = []
    for s, ts in by_sector().items():
        out += ts[:n_per_sector]
    return out


def info(ticker: str) -> tuple[str, str]:
    return UNIVERSE.get(ticker, (ticker, "Unknown"))

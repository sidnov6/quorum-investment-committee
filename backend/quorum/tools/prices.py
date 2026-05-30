"""Price/quote tool. yfinance backbone, point-in-time aware, cached as Bronze."""
from __future__ import annotations

import datetime as dt
from typing import Optional

import pandas as pd

from quorum.tools.snapshot import cached_fetch


def _to_date(d: str | dt.date) -> dt.date:
    if isinstance(d, dt.date):
        return d
    return dt.date.fromisoformat(str(d)[:10])


# In-process full-history cache so a backtest fetches each ticker's bars only once
# and then slices point-in-time in memory (huge speedup over per-day refetches).
_FULL_HISTORY_START = "2015-01-01"
_MEM: dict[str, pd.DataFrame] = {}


def _yf_history(ticker: str) -> list[dict]:
    try:
        import yfinance as yf

        df = yf.download(
            ticker,
            start=_FULL_HISTORY_START,
            end=(dt.date.today() + dt.timedelta(days=1)).isoformat(),
            progress=False,
            auto_adjust=True,
            threads=False,
        )
    except Exception:
        return []
    if df is None or df.empty:
        return []
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower).reset_index()
    date_col = "Date" if "Date" in df.columns else df.columns[0]
    return [
        {
            "date": str(r[date_col])[:10],
            "open": float(r.get("open", 0) or 0),
            "high": float(r.get("high", 0) or 0),
            "low": float(r.get("low", 0) or 0),
            "close": float(r.get("close", 0) or 0),
            "volume": float(r.get("volume", 0) or 0),
        }
        for _, r in df.iterrows()
    ]


def _stooq_history(ticker: str) -> list[dict]:
    """Free daily OHLCV from Stooq CSV — reliable fallback when yfinance is blocked."""
    import requests

    sym = ticker.lower().replace("-", "-") + ".us"  # Stooq US suffix (e.g. brk-b.us)
    try:
        r = requests.get("https://stooq.com/q/d/l/", params={"s": sym, "i": "d"}, timeout=20)
        if r.status_code != 200 or "Date" not in r.text[:50]:
            return []
        out = []
        for line in r.text.strip().splitlines()[1:]:
            parts = line.split(",")
            if len(parts) < 6 or parts[4] in ("", "N/D"):
                continue
            out.append({
                "date": parts[0],
                "open": float(parts[1] or 0), "high": float(parts[2] or 0),
                "low": float(parts[3] or 0), "close": float(parts[4] or 0),
                "volume": float(parts[5] or 0),
            })
        return out
    except Exception:
        return []


def _full_history(ticker: str) -> pd.DataFrame:
    if ticker in _MEM:
        return _MEM[ticker]
    today = dt.date.today().isoformat()

    def _fetch():
        import yfinance as yf

        df = yf.download(
            ticker,
            start=_FULL_HISTORY_START,
            end=(dt.date.today() + dt.timedelta(days=1)).isoformat(),
            progress=False,
            auto_adjust=True,
            threads=False,
        )
        if df is None or df.empty:
            return []
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.rename(columns=str.lower).reset_index()
        date_col = "Date" if "Date" in df.columns else df.columns[0]
        return [
            {
                "date": str(r[date_col])[:10],
                "open": float(r.get("open", 0) or 0),
                "high": float(r.get("high", 0) or 0),
                "low": float(r.get("low", 0) or 0),
                "close": float(r.get("close", 0) or 0),
                "volume": float(r.get("volume", 0) or 0),
            }
            for _, r in df.iterrows()
        ]

    # Snapshot keyed by ticker + today only (one fetch per ticker per day).
    records = cached_fetch("yfinance_full", ticker, today, _fetch, ttl=None)
    if not records:
        df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    else:
        df = pd.DataFrame(records)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
    _MEM[ticker] = df
    return df


def get_prices(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Daily OHLCV between [start, end], sliced from the cached full history.

    Returns a DataFrame indexed by date with columns: open, high, low, close, volume.
    Empty DataFrame on failure (callers must handle missing data gracefully).
    """
    df = _full_history(ticker)
    if df.empty:
        return df
    return df[(df.index >= pd.Timestamp(_to_date(start))) & (df.index <= pd.Timestamp(_to_date(end)))]


def get_price_history(ticker: str, as_of: str, lookback_days: int = 400) -> pd.DataFrame:
    """All daily bars up to (and including) as_of. Never returns future data."""
    end = _to_date(as_of)
    start = end - dt.timedelta(days=lookback_days)
    df = get_prices(ticker, start.isoformat(), end.isoformat())
    if df.empty:
        return df
    return df[df.index <= pd.Timestamp(end)]


def get_quote(ticker: str, as_of: str) -> Optional[dict]:
    """The latest close on/before as_of, plus simple derived stats."""
    df = get_price_history(ticker, as_of, lookback_days=400)
    if df.empty:
        return None
    last = df.iloc[-1]
    close = float(last["close"])
    out = {"ticker": ticker, "as_of": as_of, "close": close, "date": str(df.index[-1])[:10]}

    def _ret(n: int) -> Optional[float]:
        if len(df) > n:
            prev = float(df["close"].iloc[-1 - n])
            if prev:
                return round((close / prev - 1) * 100, 2)
        return None

    out["ret_1m_pct"] = _ret(21)
    out["ret_3m_pct"] = _ret(63)
    out["ret_6m_pct"] = _ret(126)
    out["ret_12m_pct"] = _ret(252)
    if len(df) >= 200:
        out["sma_50"] = round(float(df["close"].iloc[-50:].mean()), 2)
        out["sma_200"] = round(float(df["close"].iloc[-200:].mean()), 2)
        out["above_sma_200"] = bool(close > out["sma_200"])
    return out

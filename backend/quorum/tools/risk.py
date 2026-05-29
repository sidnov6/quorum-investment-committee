"""Deterministic risk math. THE LLM NEVER COMPUTES THESE NUMBERS.

Annualized vol, max drawdown, beta vs benchmark, historical & parametric VaR,
correlation, and portfolio-level aggregation. Pure NumPy/pandas/scipy.
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd

from quorum.tools.prices import get_price_history

TRADING_DAYS = 252


def _returns(close: pd.Series) -> pd.Series:
    return close.pct_change().dropna()


def annualized_vol(returns: pd.Series) -> float:
    if len(returns) < 2:
        return 0.0
    return float(returns.std(ddof=1) * math.sqrt(TRADING_DAYS))


def max_drawdown(close: pd.Series) -> float:
    if len(close) < 2:
        return 0.0
    cummax = close.cummax()
    dd = (close - cummax) / cummax
    return float(dd.min())


def beta(asset_ret: pd.Series, bench_ret: pd.Series) -> Optional[float]:
    df = pd.concat([asset_ret, bench_ret], axis=1, join="inner").dropna()
    if len(df) < 20:
        return None
    cov = np.cov(df.iloc[:, 0], df.iloc[:, 1])[0, 1]
    var = np.var(df.iloc[:, 1], ddof=1)
    return float(cov / var) if var else None


def historical_var(returns: pd.Series, conf: float = 0.95) -> float:
    """1-day historical VaR as a positive fraction of capital at risk."""
    if len(returns) < 20:
        return 0.0
    return float(-np.percentile(returns, (1 - conf) * 100))


def parametric_var(returns: pd.Series, conf: float = 0.95) -> float:
    if len(returns) < 20:
        return 0.0
    from scipy.stats import norm

    mu, sigma = returns.mean(), returns.std(ddof=1)
    return float(-(mu + norm.ppf(1 - conf) * sigma))


def annualized_return(close: pd.Series) -> float:
    if len(close) < 2:
        return 0.0
    total = close.iloc[-1] / close.iloc[0] - 1
    years = len(close) / TRADING_DAYS
    if years <= 0:
        return 0.0
    return float((1 + total) ** (1 / years) - 1)


def sharpe(returns: pd.Series, rf: float = 0.0) -> float:
    if len(returns) < 2 or returns.std(ddof=1) == 0:
        return 0.0
    excess = returns.mean() - rf / TRADING_DAYS
    return float(excess / returns.std(ddof=1) * math.sqrt(TRADING_DAYS))


def ticker_risk(ticker: str, as_of: str, benchmark: str = "SPY", conf: float = 0.95) -> dict:
    """Full per-ticker risk metrics, point-in-time."""
    px = get_price_history(ticker, as_of, lookback_days=400)
    if px.empty or len(px) < 30:
        return {"ticker": ticker, "available": False}
    close = px["close"]
    ret = _returns(close)
    bench = get_price_history(benchmark, as_of, lookback_days=400)
    b = beta(ret, _returns(bench["close"])) if not bench.empty else None
    return {
        "ticker": ticker,
        "available": True,
        "annualized_vol": round(annualized_vol(ret), 4),
        "annualized_return": round(annualized_return(close), 4),
        "max_drawdown": round(max_drawdown(close), 4),
        "beta": round(b, 3) if b is not None else None,
        "var_1d_hist": round(historical_var(ret, conf), 4),
        "var_1d_param": round(parametric_var(ret, conf), 4),
        "sharpe": round(sharpe(ret), 3),
        "n_obs": int(len(ret)),
    }


def compute_risk_metrics(
    tickers: list[str],
    weights: dict[str, float],
    as_of: str,
    benchmark: str = "SPY",
    conf: float = 0.95,
) -> dict:
    """Per-ticker + portfolio-level risk for a proposed weighting."""
    per = {t: ticker_risk(t, as_of, benchmark, conf) for t in tickers}

    # Build aligned return matrix for portfolio vol & correlation.
    series = {}
    for t in tickers:
        px = get_price_history(t, as_of, lookback_days=400)
        if not px.empty and len(px) >= 30:
            series[t] = _returns(px["close"])
    port = {}
    correlation = {}
    if series:
        mat = pd.concat(series, axis=1).dropna()
        if not mat.empty and mat.shape[1] >= 1:
            w = np.array([weights.get(t, 0.0) for t in mat.columns])
            if w.sum() > 0:
                cov = mat.cov().values * TRADING_DAYS
                port_var = float(w @ cov @ w)
                port["annualized_vol"] = round(math.sqrt(max(port_var, 0)), 4)
                port_ret = (mat * w).sum(axis=1)
                port["var_1d_hist"] = round(historical_var(port_ret, conf), 4)
                port["sharpe"] = round(sharpe(port_ret), 3)
                port["max_drawdown"] = round(max_drawdown((1 + port_ret).cumprod()), 4)
            if mat.shape[1] >= 2:
                correlation = mat.corr().round(3).to_dict()
    return {"per_ticker": per, "portfolio": port, "correlation": correlation}

# QUORUM — The Multi-Agent Investment Committee

> A simulated investment committee of specialized AI agents — a **bull**, a **bear**, a **macro strategist**, a **quant/risk officer**, and a **portfolio manager** — that each argue from *real* market data, debate across structured rounds, and converge on a documented allocation, with a human holding the final gate.

**This is decision-support, not financial advice.** No real capital is ever traded — the portfolio is paper-only. The value is the *agentic engineering* and the *transparency of the reasoning*, not investment returns.

---

## What it does

- **Screens a 51-name, all-sector universe** (point-in-time) and shortlists the most decision-relevant names.
- Runs a **cyclic debate**: Research briefs → Bull & Bear argue independently then rebut → Macro adds regime context → Risk Officer computes downside and can **veto** → PM synthesizes weights → Critic stress-tests for groupthink → loop or converge.
- **Grounds every quantitative claim** in fetched data (SEC EDGAR fundamentals, prices, news, FRED macro). Unsourced numbers are rejected by a guardrail.
- Produces an **investment-committee memo** (allocation + rationale + surviving dissent + confidence) and an auditable transcript.
- **Backtests honestly**: $10k portfolio, point-in-time (no lookahead), trading costs included, benchmarked vs SPY.
- Maintains a **live paper portfolio** you can advance daily via a scheduler/cron.

## Architecture

```
backend/
  quorum/
    tools/        # point-in-time data: prices (yfinance), fundamentals (SEC EDGAR),
                  # news (yfinance/Finnhub), macro (FRED), risk (NumPy/SciPy), snapshot cache
    committee/    # factors (deterministic scoring), grounding guardrail, agents/, orchestrator
    models/       # LLM router + provider failover (Gemini→Groq→OpenAI→Anthropic→deterministic)
    backtest/     # point-in-time $10k backtest engine
    store/        # SQLite persistence
    paper.py      # live daily paper-portfolio engine
    universe.py   # 51-name, 11-sector investable universe
  app/main.py     # FastAPI gateway + SSE live debate streaming
  scripts/        # daily_run.py (cron), seed_portfolio.py
frontend/         # Next.js + Tailwind "Committee Room" (Stripe-style UI)
```

### The determinism boundary (why it's trustworthy)
All numbers — prices, ratios, vol, drawdown, VaR, weights — come from **Python/tools**, validated. The LLM (when configured) only *interprets and narrates*; it never computes or recalls figures. This kills the #1 failure of "AI investing" demos: confident wrong numbers.

### Runs with zero keys
With **no API keys**, the committee uses deterministic, evidence-grounded agent logic on free data (yfinance + SEC EDGAR) and runs fully end-to-end. Drop a `GEMINI_API_KEY` (or Groq/OpenAI/Anthropic) into `.env` to upgrade the debate prose to real LLM reasoning — numbers stay deterministic.

---

## Quick start

```bash
./start.sh
```
Then open **http://localhost:3000**. (First run creates the venv, installs deps, and boots both API + UI.)

### Manual
```bash
# Backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend && PYTHONPATH=. uvicorn app.main:app --port 8077

# Frontend (new terminal)
cd frontend && npm install && npm run dev
```

### Seed a track record / run daily
```bash
cd backend && source ../.venv/bin/activate
python scripts/seed_portfolio.py 2024-01-01 2024-12-31 21   # build a historical curve
python scripts/daily_run.py                                  # advance one day (cron this)
```
Cron example (every weekday 17:30):
```
30 17 * * 1-5  cd /path/to/AI\ Trader/backend && PYTHONPATH=. ../.venv/bin/python scripts/daily_run.py
```

---

## The Committee Room (UI)

| Screen | What it shows |
|---|---|
| **Overview** | Hero + latest evaluated track record + how it works |
| **Paper Portfolio** | Live $10k curve, holdings, run-a-meeting-for-a-date |
| **Convene** | Set the mandate (as-of date, shortlist size, universe) |
| **Debate Floor** | The centerpiece — committee streams **live** (SSE), bull left / bear right, every figure a sourced chip |
| **Risk Desk** | Vol, beta, VaR, drawdown, constraints, veto |
| **Decision Memo** | Allocation, rationale, surviving counter-argument, human gate, export PDF |
| **Backtest** | Point-in-time historical run vs SPY, equity curve, every meeting |

---

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | status + active LLM engine |
| GET | `/api/universe` | universe by sector |
| POST | `/api/committee/run` | run a committee (JSON) |
| GET | `/api/committee/stream` | **SSE** live debate |
| POST | `/api/backtest/run` | run a backtest |
| GET | `/api/portfolio` | paper-portfolio snapshot + curve |
| POST | `/api/portfolio/run-today` | advance the paper portfolio |

---

## Honest limitations
- **Not an alpha claim.** Backtests are small-sample, regime-dependent, and the momentum tilt benefits from bull markets. Reported as "directionally reasonable," never "beats the market."
- **News is point-in-time-limited on the free tier** (yfinance returns current headlines); add a Finnhub key for true historical news. Sentiment is one input among several, never the sole driver.
- **Paper only.** No broker, no order routing, no live capital — by design.

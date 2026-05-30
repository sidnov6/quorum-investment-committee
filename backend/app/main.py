"""QUORUM API gateway — FastAPI + SSE live debate streaming.

Endpoints:
  GET  /api/health
  GET  /api/universe                      -> the investable universe by sector
  POST /api/committee/run                 -> run a committee, persist, return result
  GET  /api/committee/stream              -> SSE: stream a committee debate live
  GET  /api/committee/runs                -> recent runs
  GET  /api/committee/runs/{id}           -> full stored run
  POST /api/backtest/run                  -> run + persist a backtest
  GET  /api/backtest/list                 -> recent backtests
  GET  /api/backtest/{id}                 -> full backtest
  GET  /api/portfolio                     -> live paper-portfolio track record
  POST /api/portfolio/run-today           -> advance the daily paper portfolio one step
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import queue
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from quorum.backtest.engine import run_backtest
from quorum.committee.committee import run_committee
from quorum.config import settings
from quorum.schemas import Mandate
from quorum.store import db
from quorum.universe import UNIVERSE, by_sector, info, tickers
from quorum import paper
from quorum import assistant
from quorum import daily as daily_job
from quorum import email_report
import os

app = FastAPI(title="QUORUM API", version="1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    db.init_db()


# ---------------- request models ----------------
class CommitteeRequest(BaseModel):
    candidates: list[str] | None = None
    as_of_date: str | None = None
    horizon_days: int = 60
    shortlist_k: int = 8
    benchmark: str = "SPY"


class ChatRequest(BaseModel):
    question: str
    history: list[dict] = []
    as_of_date: str | None = None


class BacktestRequest(BaseModel):
    candidates: list[str] | None = None
    start: str = "2023-01-01"
    end: str = "2024-12-31"
    rebalance_days: int = 21
    starting_cash: float = 10000.0
    benchmark: str = "SPY"


def _mandate(req: CommitteeRequest) -> Mandate:
    return Mandate(
        candidates=req.candidates or tickers(),
        as_of_date=req.as_of_date or dt.date.today().isoformat(),
        horizon_days=req.horizon_days,
        shortlist_k=req.shortlist_k,
        benchmark=req.benchmark,
    )


# ---------------- endpoints ----------------
@app.get("/api/health")
def health():
    from quorum.models.router import available_providers
    return {"ok": True, "llm": available_providers() or ["deterministic"],
            "universe_size": len(UNIVERSE), "db": "postgres" if db.IS_PG else "sqlite",
            "email": email_report.email_enabled()}


# ---------------- daily job + email ----------------
class SubscribeRequest(BaseModel):
    email: str


@app.post("/api/subscribe")
def subscribe(req: SubscribeRequest):
    e = req.email.strip().lower()
    if "@" not in e or "." not in e:
        return {"ok": False, "error": "invalid email"}
    db.add_subscriber(e)
    return {"ok": True, "email": e, "subscribers": len(db.list_subscribers())}


@app.post("/api/unsubscribe")
def unsubscribe(req: SubscribeRequest):
    db.remove_subscriber(req.email)
    return {"ok": True}


@app.post("/api/daily/run")
def daily_run(as_of_date: str | None = None, token: str = "", send_email: bool = True):
    """Run the daily committee + email job. Protected by DAILY_RUN_TOKEN if set."""
    expected = os.getenv("DAILY_RUN_TOKEN", "")
    if expected and token != expected:
        return {"ok": False, "error": "unauthorized"}
    return daily_job.run_daily(as_of_date, send_email=send_email)


@app.get("/api/daily/preview")
def daily_preview(as_of_date: str | None = None):
    """Render today's report HTML WITHOUT sending — for previewing in the browser."""
    snap = paper.snapshot()
    alerts = daily_job.scan_alerts(as_of_date or __import__("datetime").date.today().isoformat(),
                                   snap.get("holdings", []))
    subject, html = email_report.render_report(snap, None, alerts)
    from fastapi.responses import HTMLResponse
    return HTMLResponse(html)


@app.get("/api/universe")
def universe():
    return {
        "count": len(UNIVERSE),
        "sectors": by_sector(),
        "items": [{"ticker": t, "name": n, "sector": s} for t, (n, s) in UNIVERSE.items()],
    }


@app.post("/api/committee/run")
def committee_run(req: CommitteeRequest):
    m = _mandate(req)
    result = run_committee(m)
    payload = result.model_dump()
    rid = db.save_committee_run(m.as_of_date, m.candidates, result.status,
                                result.decision.confidence if result.decision else 0, payload)
    payload["id"] = rid
    return payload


@app.get("/api/committee/stream")
async def committee_stream(candidates: str = "", as_of_date: str = "",
                           shortlist_k: int = 8, benchmark: str = "SPY"):
    cand = [c.strip().upper() for c in candidates.split(",") if c.strip()] or tickers()
    m = Mandate(candidates=cand, as_of_date=as_of_date or dt.date.today().isoformat(),
                shortlist_k=shortlist_k, benchmark=benchmark)

    q: "queue.Queue" = queue.Queue()
    SENTINEL = object()

    def worker():
        def emit(turn):
            q.put(turn.model_dump())
        result = run_committee(m, emit=emit)
        payload = result.model_dump()
        rid = db.save_committee_run(m.as_of_date, m.candidates, result.status,
                                    result.decision.confidence if result.decision else 0, payload)
        payload["id"] = rid
        q.put({"__final__": payload})
        q.put(SENTINEL)

    threading.Thread(target=worker, daemon=True).start()

    async def gen():
        while True:
            try:
                item = await asyncio.get_event_loop().run_in_executor(None, q.get)
            except Exception:
                break
            if item is SENTINEL:
                break
            if isinstance(item, dict) and "__final__" in item:
                yield {"event": "final", "data": json.dumps(item["__final__"], default=str)}
            else:
                yield {"event": "turn", "data": json.dumps(item, default=str)}

    return EventSourceResponse(gen())


@app.get("/api/committee/runs")
def committee_runs():
    return db.list_committee_runs()


@app.get("/api/committee/runs/{run_id}")
def committee_run_get(run_id: int):
    return db.get_committee_run(run_id) or {"error": "not found"}


@app.post("/api/assistant/chat")
def assistant_chat(req: ChatRequest):
    return assistant.chat(req.question, req.history, req.as_of_date)


@app.post("/api/backtest/run")
def backtest_run(req: BacktestRequest, refresh: bool = False):
    cand = req.candidates or tickers()
    # Reproducibility: identical params return the stored run (real caching, not a re-roll).
    cache_key = json.dumps({
        "c": sorted(cand), "s": req.start, "e": req.end,
        "r": req.rebalance_days, "cash": req.starting_cash, "b": req.benchmark,
    }, sort_keys=True)
    if not refresh:
        cached = db.get_backtest_by_key(cache_key)
        if cached:
            cached["cached"] = True
            return cached
    result = run_backtest(cand, req.start, req.end, starting_cash=req.starting_cash,
                          rebalance_days=req.rebalance_days, benchmark=req.benchmark)
    bid = db.save_backtest(req.start, req.end, cand, result, cache_key=cache_key)
    result["id"] = bid
    result["cached"] = False
    return result


@app.get("/api/backtest/list")
def backtest_list():
    return db.list_backtests()


@app.get("/api/backtest/{bt_id}")
def backtest_get(bt_id: int):
    return db.get_backtest(bt_id) or {"error": "not found"}


@app.get("/api/portfolio")
def portfolio():
    return paper.snapshot()


@app.post("/api/portfolio/run-today")
def portfolio_run_today(as_of_date: str | None = None):
    return paper.run_daily_step(as_of_date)

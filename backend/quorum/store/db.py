"""SQLite persistence — committee runs, backtests, and the live paper portfolio.

Zero-config (a single file). Swap DB_PATH / the connection for Postgres in prod;
the schema is intentionally simple and portable.
"""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
from contextlib import contextmanager
from typing import Optional

from quorum.config import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS committee_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    candidates TEXT NOT NULL,
    status TEXT NOT NULL,
    confidence REAL,
    result_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS backtests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    candidates TEXT NOT NULL,
    final_value REAL,
    total_return REAL,
    result_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS paper_portfolio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date TEXT NOT NULL,
    value REAL NOT NULL,
    cash REAL NOT NULL,
    holdings_json TEXT NOT NULL,
    decision_json TEXT
);
"""


@contextmanager
def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_db():
    with conn() as c:
        c.executescript(_SCHEMA)


def save_committee_run(as_of: str, candidates: list[str], status: str,
                       confidence: float, result: dict) -> int:
    with conn() as c:
        cur = c.execute(
            "INSERT INTO committee_runs (created_at, as_of_date, candidates, status, confidence, result_json)"
            " VALUES (?,?,?,?,?,?)",
            (dt.datetime.utcnow().isoformat(), as_of, json.dumps(candidates), status,
             confidence, json.dumps(result, default=str)),
        )
        return cur.lastrowid


def list_committee_runs(limit: int = 50) -> list[dict]:
    with conn() as c:
        rows = c.execute(
            "SELECT id, created_at, as_of_date, candidates, status, confidence "
            "FROM committee_runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


def get_committee_run(run_id: int) -> Optional[dict]:
    with conn() as c:
        row = c.execute("SELECT result_json FROM committee_runs WHERE id=?", (run_id,)).fetchone()
        return json.loads(row["result_json"]) if row else None


def save_backtest(start: str, end: str, candidates: list[str], result: dict) -> int:
    with conn() as c:
        cur = c.execute(
            "INSERT INTO backtests (created_at, start_date, end_date, candidates, final_value, total_return, result_json)"
            " VALUES (?,?,?,?,?,?,?)",
            (dt.datetime.utcnow().isoformat(), start, end, json.dumps(candidates),
             result.get("final_value"), result.get("metrics", {}).get("total_return"),
             json.dumps(result, default=str)),
        )
        return cur.lastrowid


def list_backtests(limit: int = 50) -> list[dict]:
    with conn() as c:
        rows = c.execute(
            "SELECT id, created_at, start_date, end_date, candidates, final_value, total_return "
            "FROM backtests ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


def get_backtest(bt_id: int) -> Optional[dict]:
    with conn() as c:
        row = c.execute("SELECT result_json FROM backtests WHERE id=?", (bt_id,)).fetchone()
        return json.loads(row["result_json"]) if row else None


# --- live paper portfolio (the daily-run track record) ---
def record_paper_snapshot(run_date: str, value: float, cash: float,
                          holdings: dict, decision: Optional[dict]) -> int:
    with conn() as c:
        cur = c.execute(
            "INSERT INTO paper_portfolio (run_date, value, cash, holdings_json, decision_json)"
            " VALUES (?,?,?,?,?)",
            (run_date, value, cash, json.dumps(holdings), json.dumps(decision, default=str)),
        )
        return cur.lastrowid


def paper_history() -> list[dict]:
    with conn() as c:
        rows = c.execute(
            "SELECT run_date, value, cash, holdings_json, decision_json FROM paper_portfolio "
            "ORDER BY run_date ASC").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["holdings"] = json.loads(d.pop("holdings_json"))
            d["decision"] = json.loads(d.pop("decision_json")) if d["decision_json"] else None
            d.pop("decision_json", None)
            out.append(d)
        return out


def latest_paper_state() -> Optional[dict]:
    h = paper_history()
    return h[-1] if h else None

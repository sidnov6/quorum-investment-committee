"""Persistence — committee runs, backtests, live paper portfolio, subscribers.

Dual backend: if DATABASE_URL is set (Neon/Postgres in production) it is used so data
SURVIVES Render redeploys and sleeps; otherwise falls back to a local SQLite file for
zero-config dev. Same API either way.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sqlite3
from contextlib import contextmanager
from typing import Optional

from quorum.config import DB_PATH

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
IS_PG = DATABASE_URL.startswith(("postgres://", "postgresql://"))

# Placeholder + autoincrement syntax differ between backends.
PH = "%s" if IS_PG else "?"
_PK = "BIGSERIAL PRIMARY KEY" if IS_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS committee_runs (
    id {_PK},
    created_at TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    candidates TEXT NOT NULL,
    status TEXT NOT NULL,
    confidence REAL,
    result_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS backtests (
    id {_PK},
    created_at TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    candidates TEXT NOT NULL,
    final_value REAL,
    total_return REAL,
    cache_key TEXT,
    result_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS paper_portfolio (
    id {_PK},
    run_date TEXT NOT NULL,
    value REAL NOT NULL,
    cash REAL NOT NULL,
    holdings_json TEXT NOT NULL,
    decision_json TEXT
);
CREATE TABLE IF NOT EXISTS subscribers (
    id {_PK},
    email TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);
"""


@contextmanager
def conn():
    if IS_PG:
        import psycopg
        from psycopg.rows import dict_row

        c = psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=False)
        try:
            yield c
            c.commit()
        finally:
            c.close()
    else:
        c = sqlite3.connect(DB_PATH)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        finally:
            c.close()


def _q(sql: str) -> str:
    """Translate ? placeholders to the active backend's style."""
    return sql.replace("?", PH) if IS_PG else sql


def init_db():
    with conn() as c:
        if IS_PG:
            # psycopg can't executescript; run statements individually.
            for stmt in [s for s in _SCHEMA.split(";") if s.strip()]:
                c.execute(stmt)
        else:
            c.executescript(_SCHEMA)
    # Lightweight migration in its own transaction (a failed ALTER must not poison
    # the main one on Postgres). Adds cache_key to pre-existing backtests tables.
    try:
        with conn() as c2:
            c2.execute("ALTER TABLE backtests ADD COLUMN cache_key TEXT")
    except Exception:
        pass  # column already exists


def _insert_returning(c, sql_no_id: str, returning_col: str, params: tuple):
    """INSERT and get the new id portably."""
    if IS_PG:
        cur = c.execute(_q(sql_no_id + f" RETURNING {returning_col}"), params)
        row = cur.fetchone()
        return row[returning_col] if isinstance(row, dict) else row[0]
    cur = c.execute(sql_no_id, params)
    return cur.lastrowid


# ---------------- committee runs ----------------
def save_committee_run(as_of: str, candidates: list[str], status: str,
                       confidence: float, result: dict) -> int:
    with conn() as c:
        return _insert_returning(
            c,
            "INSERT INTO committee_runs (created_at, as_of_date, candidates, status, confidence, result_json)"
            f" VALUES ({PH},{PH},{PH},{PH},{PH},{PH})",
            "id",
            (dt.datetime.utcnow().isoformat(), as_of, json.dumps(candidates), status,
             confidence, json.dumps(result, default=str)),
        )


def list_committee_runs(limit: int = 50) -> list[dict]:
    with conn() as c:
        rows = c.execute(_q(
            "SELECT id, created_at, as_of_date, candidates, status, confidence "
            "FROM committee_runs ORDER BY id DESC LIMIT ?"), (limit,)).fetchall()
        return [dict(r) for r in rows]


def get_committee_run(run_id: int) -> Optional[dict]:
    with conn() as c:
        row = c.execute(_q("SELECT result_json FROM committee_runs WHERE id=?"), (run_id,)).fetchone()
        if not row:
            return None
        return json.loads(row["result_json"] if isinstance(row, dict) else row[0])


# ---------------- backtests ----------------
def save_backtest(start: str, end: str, candidates: list[str], result: dict,
                  cache_key: str = "") -> int:
    with conn() as c:
        return _insert_returning(
            c,
            "INSERT INTO backtests (created_at, start_date, end_date, candidates, final_value, total_return, cache_key, result_json)"
            f" VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})",
            "id",
            (dt.datetime.utcnow().isoformat(), start, end, json.dumps(candidates),
             result.get("final_value"), result.get("metrics", {}).get("total_return"),
             cache_key, json.dumps(result, default=str)),
        )


def get_backtest_by_key(cache_key: str) -> Optional[dict]:
    with conn() as c:
        row = c.execute(_q(
            "SELECT result_json FROM backtests WHERE cache_key=? ORDER BY id DESC LIMIT 1"),
            (cache_key,)).fetchone()
        if not row:
            return None
        return json.loads(row["result_json"] if isinstance(row, dict) else row[0])


def list_backtests(limit: int = 50) -> list[dict]:
    with conn() as c:
        rows = c.execute(_q(
            "SELECT id, created_at, start_date, end_date, candidates, final_value, total_return "
            "FROM backtests ORDER BY id DESC LIMIT ?"), (limit,)).fetchall()
        return [dict(r) for r in rows]


def get_backtest(bt_id: int) -> Optional[dict]:
    with conn() as c:
        row = c.execute(_q("SELECT result_json FROM backtests WHERE id=?"), (bt_id,)).fetchone()
        if not row:
            return None
        return json.loads(row["result_json"] if isinstance(row, dict) else row[0])


# ---------------- live paper portfolio ----------------
def record_paper_snapshot(run_date: str, value: float, cash: float,
                          holdings: dict, decision: Optional[dict]) -> int:
    with conn() as c:
        return _insert_returning(
            c,
            "INSERT INTO paper_portfolio (run_date, value, cash, holdings_json, decision_json)"
            f" VALUES ({PH},{PH},{PH},{PH},{PH})",
            "id",
            (run_date, value, cash, json.dumps(holdings), json.dumps(decision, default=str)),
        )


def paper_history() -> list[dict]:
    with conn() as c:
        rows = c.execute(_q(
            "SELECT run_date, value, cash, holdings_json, decision_json FROM paper_portfolio "
            "ORDER BY run_date ASC")).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["holdings"] = json.loads(d.pop("holdings_json"))
            dj = d.pop("decision_json", None)
            d["decision"] = json.loads(dj) if dj else None
            out.append(d)
        return out


def latest_paper_state() -> Optional[dict]:
    h = paper_history()
    return h[-1] if h else None


# ---------------- subscribers (for daily email) ----------------
def add_subscriber(email: str) -> bool:
    email = email.strip().lower()
    with conn() as c:
        try:
            if IS_PG:
                c.execute(_q(
                    "INSERT INTO subscribers (email, created_at, active) VALUES (?,?,1) "
                    "ON CONFLICT (email) DO UPDATE SET active=1"),
                    (email, dt.datetime.utcnow().isoformat()))
            else:
                c.execute(
                    "INSERT INTO subscribers (email, created_at, active) VALUES (?,?,1) "
                    "ON CONFLICT(email) DO UPDATE SET active=1",
                    (email, dt.datetime.utcnow().isoformat()))
            return True
        except Exception:
            return False


def list_subscribers() -> list[str]:
    with conn() as c:
        rows = c.execute(_q("SELECT email FROM subscribers WHERE active=1 ORDER BY created_at")).fetchall()
        return [(r["email"] if isinstance(r, dict) else r[0]) for r in rows]


def remove_subscriber(email: str) -> bool:
    with conn() as c:
        c.execute(_q("UPDATE subscribers SET active=0 WHERE email=?"), (email.strip().lower(),))
    return True

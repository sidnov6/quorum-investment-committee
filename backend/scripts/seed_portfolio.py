"""Seed the paper portfolio with a historical track record so the dashboard has a
curve immediately. Walks the committee forward across past dates (point-in-time).

Usage:
    python scripts/seed_portfolio.py 2024-01-01 2024-12-31 21
"""
from __future__ import annotations

import sys
import datetime as dt

import pandas as pd

from quorum.store import db
from quorum import paper


def main():
    start = sys.argv[1] if len(sys.argv) > 1 else "2024-01-01"
    end = sys.argv[2] if len(sys.argv) > 2 else dt.date.today().isoformat()
    step = int(sys.argv[3]) if len(sys.argv) > 3 else 21

    db.init_db()
    dates = list(pd.bdate_range(start=start, end=end))[::step]
    print(f"Seeding {len(dates)} committee meetings from {start} to {end} (every {step} bdays)…")
    for d in dates:
        ds = d.strftime("%Y-%m-%d")
        out = paper.run_daily_step(ds)
        if out.get("skipped"):
            print(f"  {ds}  [skip]")
        else:
            print(f"  {ds}  ${out['value']:,.2f}")
    snap = paper.snapshot()
    print(f"\nDone. Final paper value ${snap['value']:,.2f} "
          f"({snap['total_return']*100:+.1f}% since inception).")


if __name__ == "__main__":
    main()

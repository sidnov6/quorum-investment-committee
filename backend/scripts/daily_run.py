"""Daily committee run — call this once per trading day (cron/scheduler).

Convenes the committee on the full universe (point-in-time as of the run date) and
advances the live paper portfolio, building an auditable $10k track record over time.

Usage:
    python scripts/daily_run.py                # today
    python scripts/daily_run.py 2024-06-03     # a specific date
"""
from __future__ import annotations

import sys

from quorum.store import db
from quorum import paper


def main():
    db.init_db()
    as_of = sys.argv[1] if len(sys.argv) > 1 else None
    out = paper.run_daily_step(as_of)
    if out.get("skipped"):
        print(f"[skip] {out['reason']}")
        return
    print(f"[ok] {out['as_of']} value=${out['value']:,.2f} "
          f"turnover={out['turnover']} cost=${out['cost']:.2f} status={out['status']}")
    longs = [p for p in out["decision"]["positions"] if p["target_weight"] > 0]
    for p in sorted(longs, key=lambda x: -x["target_weight"])[:8]:
        print(f"     {p['ticker']:6} {p['target_weight']*100:5.1f}%  {p['action']}")


if __name__ == "__main__":
    main()

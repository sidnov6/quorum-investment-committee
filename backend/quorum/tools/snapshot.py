"""Bronze layer: immutable, point-in-time cache of raw fetches.

Every fetch is pinned by (source, key, as_of) so a historical/backtest run is
reproducible and cannot accidentally see the future. This is the keystone of
honest evaluation.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Callable, Optional

from quorum.config import SNAPSHOT_DIR


def _path(source: str, key: str, as_of: str) -> Path:
    h = hashlib.sha1(f"{source}|{key}|{as_of}".encode()).hexdigest()[:16]
    safe = f"{source}_{key}".replace("/", "_").replace(" ", "_")[:60]
    return SNAPSHOT_DIR / f"{safe}_{as_of}_{h}.json"


def cached_fetch(
    source: str,
    key: str,
    as_of: str,
    fetch_fn: Callable[[], Any],
    ttl: Optional[int] = None,
) -> Any:
    """Return cached payload if present (and fresh), else fetch + persist.

    `ttl=None` means immutable forever (correct for point-in-time historical data).
    A finite ttl is for live quotes that legitimately change.
    """
    p = _path(source, key, as_of)
    if p.exists():
        try:
            blob = json.loads(p.read_text())
            if ttl is None or (time.time() - blob.get("_fetched_at", 0) < ttl):
                return blob["payload"]
        except Exception:
            pass

    payload = fetch_fn()
    # Never cache empty/failed responses — otherwise one transient API failure
    # poisons the value for the whole TTL window (this caused ORCL to price at $0).
    if payload in (None, [], {}):
        return payload
    try:
        p.write_text(json.dumps({"_fetched_at": time.time(), "payload": payload}, default=str))
    except Exception:
        pass
    return payload

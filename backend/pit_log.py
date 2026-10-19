"""Point-in-time context log: what we saw, and when we first saw it.

An append-only SQLite record of market context (exchange product status,
status-page incidents, derivatives positioning snapshots), kept so later
studies can use only what was known before an event. Design notes:
docs/developer/PIT_LOG.md.

Rules:
- `first_seen_utc` is our own clock at capture and is the timestamp to filter
  on. `source_published_utc` is whatever the source claims, kept alongside.
- Rows are never updated or deleted. An edit by a source is a new row with
  `revision_of` pointing at the previous one.
- Missing values stay NULL. Nothing is filled, defaulted or invented.
- Separate file from every live store. Writing never raises into callers:
  `safe_*` helpers log and return instead.

Path: MW_PIT_LOG_DB, default backend/data/pit_context.sqlite (gitignored).
Set MW_PIT_LOG_DISABLED=1 to turn all writes off.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

logger = logging.getLogger("pit_log")

SCHEMA_VERSION = 1
_DEFAULT_PATH = Path(__file__).resolve().parent / "data" / "pit_context.sqlite"
_LOCK = threading.Lock()
_LAST_WRITE: Dict[tuple, float] = {}

SCHEMA = """
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

-- Coinbase products as observed. Mappings to other venues stay NULL until
-- verified; nothing is auto-mapped by ticker here.
CREATE TABLE IF NOT EXISTS symbol_registry (
    product_id TEXT PRIMARY KEY,
    base_currency TEXT NOT NULL,
    quote_currency TEXT NOT NULL,
    coinbase_status TEXT,
    first_seen_utc TEXT NOT NULL,
    last_seen_utc TEXT NOT NULL,
    removed_seen_utc TEXT,
    hyperliquid_coin TEXT,
    okx_inst_id TEXT,
    chain TEXT,
    contract_address TEXT,
    mapping_note TEXT
);

CREATE TABLE IF NOT EXISTS source_health (
    source_id TEXT PRIMARY KEY,
    role TEXT NOT NULL,
    data_status TEXT NOT NULL,       -- live | stale | offline | blocked | unconfigured
    last_ok_utc TEXT,
    last_try_utc TEXT NOT NULL,
    http_status INTEGER,
    last_error TEXT
);

CREATE TABLE IF NOT EXISTS pit_context_log (
    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT,                 -- Coinbase product id when it exists, else NULL
    venue_symbol TEXT,               -- the source's own symbol (e.g. RENDER, RENDER-USDT-SWAP)
    source_id TEXT NOT NULL,
    role TEXT NOT NULL,              -- event_calendar | market_positioning | ...
    event_type TEXT NOT NULL,
    source_published_utc TEXT,
    first_seen_utc TEXT NOT NULL,
    metric_primary REAL,
    metric_secondary REAL,
    label TEXT,
    source_url TEXT,
    payload_json TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    revision_of INTEGER REFERENCES pit_context_log(record_id)
);
CREATE INDEX IF NOT EXISTS idx_pit_product_seen ON pit_context_log(product_id, first_seen_utc);
CREATE INDEX IF NOT EXISTS idx_pit_source_seen ON pit_context_log(source_id, first_seen_utc);

-- Last observed state per watched item, for diffing (not history).
CREATE TABLE IF NOT EXISTS watch_state (
    source_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    state_sha256 TEXT NOT NULL,
    state_json TEXT NOT NULL,
    last_record_id INTEGER,
    updated_utc TEXT NOT NULL,
    PRIMARY KEY (source_id, item_id)
);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def to_utc(text: Optional[str]) -> Optional[str]:
    """Normalise a source timestamp with an offset (e.g. '...-07:00') to UTC 'Z'. None stays None."""
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return str(text)  # keep the source's text rather than guess
    if dt.tzinfo is None:
        return str(text)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def db_path() -> Path:
    return Path(os.getenv("MW_PIT_LOG_DB") or _DEFAULT_PATH)


def disabled() -> bool:
    return os.getenv("MW_PIT_LOG_DISABLED", "").strip() in ("1", "true", "yes")


def connect(path: Optional[Path] = None) -> sqlite3.Connection:
    p = Path(path) if path else db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute("INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
    conn.execute(
        "INSERT OR IGNORE INTO meta(key, value) VALUES ('purpose', ?)",
        ("Point-in-time market context. Filter on first_seen_utc. Append-only.",),
    )
    conn.commit()
    return conn


def canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _finite(x: Any) -> Optional[float]:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if f == f and f not in (float("inf"), float("-inf")) else None


def record(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    role: str,
    event_type: str,
    payload: Dict[str, Any],
    product_id: Optional[str] = None,
    venue_symbol: Optional[str] = None,
    source_published_utc: Optional[str] = None,
    metric_primary: Any = None,
    metric_secondary: Any = None,
    label: Optional[str] = None,
    source_url: Optional[str] = None,
    revision_of: Optional[int] = None,
    first_seen_utc: Optional[str] = None,
) -> int:
    body = canonical(payload)
    cur = conn.execute(
        """INSERT INTO pit_context_log (product_id, venue_symbol, source_id, role, event_type,
               source_published_utc, first_seen_utc, metric_primary, metric_secondary, label,
               source_url, payload_json, payload_sha256, revision_of)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (product_id, venue_symbol, source_id, role, event_type, source_published_utc,
         first_seen_utc or utc_now(), _finite(metric_primary), _finite(metric_secondary), label,
         source_url, body, sha256(body), revision_of),
    )
    return int(cur.lastrowid)


def set_health(conn: sqlite3.Connection, source_id: str, role: str, *, ok: bool,
               http_status: Optional[int] = None, error: Optional[str] = None,
               status: Optional[str] = None) -> None:
    now = utc_now()
    if status is None:
        status = "live" if ok else ("blocked" if http_status in (401, 403, 451) else "offline")
    prev = conn.execute("SELECT last_ok_utc FROM source_health WHERE source_id=?", (source_id,)).fetchone()
    last_ok = now if ok else (prev["last_ok_utc"] if prev else None)
    conn.execute(
        """INSERT INTO source_health (source_id, role, data_status, last_ok_utc, last_try_utc, http_status, last_error)
           VALUES (?,?,?,?,?,?,?)
           ON CONFLICT(source_id) DO UPDATE SET role=excluded.role, data_status=excluded.data_status,
               last_ok_utc=excluded.last_ok_utc, last_try_utc=excluded.last_try_utc,
               http_status=excluded.http_status, last_error=excluded.last_error""",
        (source_id, role, status, last_ok, now, http_status, None if ok else (error or "")[:500]),
    )


def watch(conn: sqlite3.Connection, source_id: str, item_id: str, state: Dict[str, Any]) -> tuple:
    """Compare `state` with the last one seen. Returns (kind, previous_state, last_record_id).

    kind: 'new' (never seen), 'changed', or 'same'. Caller records an event and then
    calls `remember` with the new record id.
    """
    row = conn.execute("SELECT state_sha256, state_json, last_record_id FROM watch_state WHERE source_id=? AND item_id=?",
                       (source_id, item_id)).fetchone()
    digest = sha256(canonical(state))
    if row is None:
        return "new", None, None
    if row["state_sha256"] == digest:
        return "same", json.loads(row["state_json"]), row["last_record_id"]
    return "changed", json.loads(row["state_json"]), row["last_record_id"]


def remember(conn: sqlite3.Connection, source_id: str, item_id: str, state: Dict[str, Any], record_id: Optional[int]) -> None:
    body = canonical(state)
    conn.execute(
        """INSERT INTO watch_state (source_id, item_id, state_sha256, state_json, last_record_id, updated_utc)
           VALUES (?,?,?,?,?,?)
           ON CONFLICT(source_id, item_id) DO UPDATE SET state_sha256=excluded.state_sha256,
               state_json=excluded.state_json, last_record_id=COALESCE(excluded.last_record_id, watch_state.last_record_id),
               updated_utc=excluded.updated_utc""",
        (source_id, item_id, sha256(body), body, record_id, utc_now()),
    )


def watched_items(conn: sqlite3.Connection, source_id: str) -> Dict[str, Dict[str, Any]]:
    return {r["item_id"]: json.loads(r["state_json"])
            for r in conn.execute("SELECT item_id, state_json FROM watch_state WHERE source_id=?", (source_id,))}


def coinbase_product_ids(conn: sqlite3.Connection) -> set:
    return {r[0] for r in conn.execute("SELECT product_id FROM symbol_registry WHERE removed_seen_utc IS NULL")}


# ---------------------------------------------------------------- positioning

def _throttled(key: tuple, min_interval_sec: float) -> bool:
    now = time.monotonic()
    with _LOCK:
        last = _LAST_WRITE.get(key)
        if last is not None and now - last < min_interval_sec:
            return True
        _LAST_WRITE[key] = now
        return False


def safe_record_positioning(items: Iterable[Dict[str, Any]], errors: Iterable[Dict[str, Any]] = (),
                            *, scope: str, min_interval_sec: float = 300.0,
                            path: Optional[Path] = None) -> int:
    """Append derivatives snapshots (funding, open interest) as seen. Never raises.

    `scope` is 'market' (BTC/ETH market-wide legs) or 'coin' (per-coin context).
    At most one snapshot per venue and symbol per `min_interval_sec`.
    """
    if disabled():
        return 0
    try:
        written = 0
        conn = connect(path)
        try:
            known = coinbase_product_ids(conn)
            for item in items:
                venue = str(item.get("exchange") or item.get("venue") or "unknown")
                symbol = str(item.get("symbol") or item.get("base_asset") or "")
                if _throttled((str(path or db_path()), scope, venue, symbol), min_interval_sec):
                    continue
                base = str(item.get("base_asset") or "").upper()
                pid = f"{base}-USD" if f"{base}-USD" in known else None
                record(conn, source_id=f"{venue}_perp", role="market_positioning",
                       event_type="POSITIONING_SNAPSHOT", product_id=pid, venue_symbol=symbol,
                       metric_primary=item.get("funding_rate"),
                       metric_secondary=item.get("open_interest_usd", item.get("open_interest")),
                       label=f"{scope}; funding interval {item.get('funding_interval_hours') or 8}h",
                       payload={**item, "scope": scope})
                set_health(conn, f"{venue}_perp", "market_positioning", ok=True)
                written += 1
            for err in errors or ():
                venue = str(err.get("exchange") or "unknown")
                set_health(conn, f"{venue}_perp", "market_positioning", ok=False,
                           http_status=err.get("status_code"), error=err.get("message"),
                           status="blocked" if err.get("status") == "blocked" else "offline")
            conn.commit()
        finally:
            conn.close()
        return written
    except Exception as exc:  # the log must never break the board or the sentiment service
        logger.warning("pit_log positioning write failed: %s", exc)
        return 0

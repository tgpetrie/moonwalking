"""Local, owner-scoped paper ticket state. This store never contacts Coinbase."""

from __future__ import annotations

import json
import math
import os
from contextlib import contextmanager
from pathlib import Path
import sqlite3
import time
import uuid

from coinbase_execution_agent import VALID_MODES


@contextmanager
def _connect():
    path = Path(
        os.environ.get("MW_PAPER_EXECUTION_DB")
        or Path(__file__).resolve().parent / "data" / "paper_execution.sqlite"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS paper_execution_modes (
                owner_id INTEGER PRIMARY KEY,
                mode TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS paper_execution_tickets (
                id TEXT PRIMARY KEY,
                owner_id INTEGER NOT NULL,
                product_id TEXT NOT NULL,
                created_ts INTEGER NOT NULL,
                ticket_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS paper_execution_owner
            ON paper_execution_tickets(owner_id, created_ts DESC);
            CREATE TABLE IF NOT EXISTS paper_execution_positions (
                ticket_id TEXT PRIMARY KEY,
                owner_id INTEGER NOT NULL,
                product_id TEXT NOT NULL,
                quantity REAL NOT NULL,
                entry_price REAL NOT NULL,
                risk_usd REAL NOT NULL,
                opened_ts INTEGER NOT NULL,
                closed_ts INTEGER,
                exit_price REAL,
                realized_r REAL
            );
            """
        )
        with conn:
            yield conn
    finally:
        conn.close()


def get_mode(owner_id):
    with _connect() as conn:
        row = conn.execute(
            "SELECT mode FROM paper_execution_modes WHERE owner_id=?", (owner_id,)
        ).fetchone()
    return row["mode"] if row else "advisory"


def set_mode(owner_id, mode):
    if mode not in VALID_MODES:
        raise ValueError("Invalid execution mode")
    with _connect() as conn:
        conn.execute(
            "INSERT INTO paper_execution_modes(owner_id, mode) VALUES(?, ?) "
            "ON CONFLICT(owner_id) DO UPDATE SET mode=excluded.mode",
            (owner_id, mode),
        )


def list_tickets(owner_id, product_id=None):
    with _connect() as conn:
        if product_id:
            rows = conn.execute(
                "SELECT ticket_json FROM paper_execution_tickets "
                "WHERE owner_id=? AND product_id=? ORDER BY created_ts DESC, rowid DESC LIMIT 100",
                (owner_id, product_id),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT ticket_json FROM paper_execution_tickets "
                "WHERE owner_id=? ORDER BY created_ts DESC, rowid DESC LIMIT 100",
                (owner_id,),
            ).fetchall()
    return [json.loads(row["ticket_json"]) for row in rows]


def stage_ticket(owner_id, ticket):
    record = dict(
        ticket, id=str(uuid.uuid4()), paper=True, created_ts=int(time.time()),
        reference_price_source="operator_supplied_paper_ticket",
    )
    with _connect() as conn:
        conn.execute(
            "INSERT INTO paper_execution_tickets VALUES (?, ?, ?, ?, ?)",
            (record["id"], owner_id, record["product_id"], record["created_ts"],
             json.dumps(record, allow_nan=False)),
        )
    return record


def _risk_metrics(conn, owner_id, now):
    day_start = int(now // 86400) * 86400
    positions = conn.execute(
        "SELECT COUNT(*) FROM paper_execution_positions WHERE owner_id=? AND closed_ts IS NULL",
        (owner_id,),
    ).fetchone()[0]
    reserved = 0
    for row in conn.execute(
        "SELECT t.ticket_json FROM paper_execution_tickets t "
        "LEFT JOIN paper_execution_positions p ON p.ticket_id=t.id "
        "WHERE t.owner_id=? AND p.ticket_id IS NULL", (owner_id,),
    ):
        ticket = json.loads(row[0])
        if ticket.get("side") == "buy" and ticket.get("status") in {"approved_paper", "auto_approved_autonomous"}:
            reserved += 1
    realized = conn.execute(
        "SELECT COALESCE(SUM(realized_r), 0) FROM paper_execution_positions "
        "WHERE owner_id=? AND closed_ts>=? AND closed_ts<?",
        (owner_id, day_start, day_start + 86400),
    ).fetchone()[0]
    return {"open_positions": positions + reserved, "daily_realized_r": realized}


def risk_metrics(owner_id):
    with _connect() as conn:
        return _risk_metrics(conn, owner_id, time.time())


def list_open_positions(owner_id):
    """Open paper positions, oldest first, as ``{symbol, product_id, quantity, ...}``."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT ticket_id, product_id, quantity, entry_price, opened_ts "
            "FROM paper_execution_positions WHERE owner_id=? AND closed_ts IS NULL "
            "ORDER BY opened_ts, ticket_id",
            (owner_id,),
        ).fetchall()
    return [
        {
            "symbol": row["product_id"].split("-")[0],
            "product_id": row["product_id"],
            "quantity": row["quantity"],
            "entry_price": row["entry_price"],
            "ticket_id": row["ticket_id"],
            "opened_ts": row["opened_ts"],
            "source": "paper",
        }
        for row in rows
    ]


def stage_evaluated_ticket(owner_id, evaluator):
    """Evaluate and reserve an autonomous ticket under one write lock."""
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        ticket = evaluator(_risk_metrics(conn, owner_id, time.time()))
        record = dict(
            ticket, id=str(uuid.uuid4()), paper=True, created_ts=int(time.time()),
            reference_price_source="operator_supplied_paper_ticket",
        )
        conn.execute(
            "INSERT INTO paper_execution_tickets VALUES (?, ?, ?, ?, ?)",
            (record["id"], owner_id, record["product_id"], record["created_ts"],
             json.dumps(record, allow_nan=False)),
        )
        return record


def _positive_number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return float(value)


def fill_ticket(owner_id, ticket_id, price):
    price = _positive_number(price, "fill_price")
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT ticket_json FROM paper_execution_tickets WHERE owner_id=? AND id=?", (owner_id, ticket_id)).fetchone()
        if row is None:
            raise LookupError("Paper ticket not found")
        ticket = json.loads(row[0])
        if ticket.get("side") != "buy" or ticket.get("status") not in {"approved_paper", "auto_approved_autonomous"}:
            raise ValueError("Only approved unfilled buy tickets can be filled")
        limit = _positive_number(ticket.get("entry_price"), "entry_price")
        stop = _positive_number(ticket.get("stop_limit_price"), "stop_limit_price")
        quantity = _positive_number(ticket.get("base_size") or ticket.get("size"), "base_size")
        if price > limit or price <= stop:
            raise ValueError("Fill price must be at or below the buy limit and above the stop")
        filled_ts = int(time.time())
        conn.execute(
            "INSERT INTO paper_execution_positions(ticket_id,owner_id,product_id,quantity,entry_price,risk_usd,opened_ts) VALUES(?,?,?,?,?,?,?)",
            (ticket_id, owner_id, ticket["product_id"], quantity, price, quantity * (price - stop), filled_ts),
        )
        ticket["status"] = "filled_paper"
        ticket["fill_price"] = price
        ticket["filled_ts"] = filled_ts
        ticket["fill_price_source"] = "operator_supplied_paper_fill"
        conn.execute("UPDATE paper_execution_tickets SET ticket_json=? WHERE owner_id=? AND id=?", (json.dumps(ticket, allow_nan=False), owner_id, ticket_id))
        return ticket


def close_position(owner_id, ticket_id, price):
    price = _positive_number(price, "exit_price")
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM paper_execution_positions WHERE owner_id=? AND ticket_id=?", (owner_id, ticket_id)).fetchone()
        if row is None:
            raise LookupError("Paper position not found")
        if row["closed_ts"] is not None:
            raise ValueError("Paper position already closed")
        realized = (price - row["entry_price"]) * row["quantity"] / row["risk_usd"]
        closed_ts = int(time.time())
        conn.execute("UPDATE paper_execution_positions SET closed_ts=?, exit_price=?, realized_r=? WHERE owner_id=? AND ticket_id=?", (closed_ts, price, realized, owner_id, ticket_id))
        ticket = json.loads(conn.execute("SELECT ticket_json FROM paper_execution_tickets WHERE owner_id=? AND id=?", (owner_id, ticket_id)).fetchone()[0])
        ticket.update(
            status="closed_paper", exit_price=price, realized_r=realized,
            closed_ts=closed_ts, exit_price_source="operator_supplied_paper_fill",
        )
        conn.execute("UPDATE paper_execution_tickets SET ticket_json=? WHERE owner_id=? AND id=?", (json.dumps(ticket, allow_nan=False), owner_id, ticket_id))
        return ticket


def approve_ticket(owner_id, ticket_id):
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT ticket_json FROM paper_execution_tickets WHERE owner_id=? AND id=?",
            (owner_id, ticket_id),
        ).fetchone()
        if row is None:
            raise LookupError("Paper ticket not found")
        ticket = json.loads(row["ticket_json"])
        if ticket.get("status") != "staged_for_approval":
            raise ValueError("Only staged tickets can be approved")
        ticket["status"] = "approved_paper"
        conn.execute(
            "UPDATE paper_execution_tickets SET ticket_json=? WHERE owner_id=? AND id=?",
            (json.dumps(ticket, allow_nan=False), owner_id, ticket_id),
        )
    return ticket


def cancel_ticket(owner_id, ticket_id):
    """Release an unfilled paper reservation, without touching an exchange."""
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT ticket_json FROM paper_execution_tickets WHERE owner_id=? AND id=?", (owner_id, ticket_id)).fetchone()
        if row is None:
            raise LookupError("Paper ticket not found")
        ticket = json.loads(row[0])
        if ticket.get("status") not in {"staged_for_approval", "approved_paper", "auto_approved_autonomous", "auto_approved_guardian"}:
            raise ValueError("Only unfilled paper tickets can be cancelled")
        ticket["status"] = "cancelled_paper"
        conn.execute("UPDATE paper_execution_tickets SET ticket_json=? WHERE owner_id=? AND id=?", (json.dumps(ticket, allow_nan=False), owner_id, ticket_id))
        return ticket

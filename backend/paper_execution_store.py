"""Local, owner-scoped paper ticket state. This store never contacts Coinbase."""

from __future__ import annotations

import json
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
        """
    )
    try:
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
    record = dict(ticket, id=str(uuid.uuid4()), paper=True, created_ts=int(time.time()))
    with _connect() as conn:
        conn.execute(
            "INSERT INTO paper_execution_tickets VALUES (?, ?, ?, ?, ?)",
            (record["id"], owner_id, record["product_id"], record["created_ts"],
             json.dumps(record, allow_nan=False)),
        )
    return record


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

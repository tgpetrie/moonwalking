from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import time
from typing import Iterable

from .contracts import AgentObservation


DEFAULT_DB_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "agent_observations.sqlite"
)


class AgentStore:
    """SQLite ledger for local agent runs and observations."""

    def __init__(self, db_path: str | os.PathLike | None = None):
        env_path = os.environ.get("MW_AGENT_OBSERVATIONS_DB")
        self.db_path = Path(db_path or env_path or DEFAULT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.ensure_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_db(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent TEXT NOT NULL,
                    started_ts INTEGER NOT NULL,
                    finished_ts INTEGER,
                    status TEXT NOT NULL,
                    error TEXT,
                    observation_count INTEGER NOT NULL DEFAULT 0,
                    model_version TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER,
                    created_ts INTEGER NOT NULL,
                    agent TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    product_id TEXT,
                    symbol TEXT,
                    summary TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    source_json TEXT NOT NULL,
                    expires_ts INTEGER,
                    FOREIGN KEY(run_id) REFERENCES agent_runs(id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS ix_agent_observations_created "
                "ON agent_observations(created_ts DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS ix_agent_observations_symbol "
                "ON agent_observations(symbol, created_ts DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS ix_agent_runs_agent "
                "ON agent_runs(agent, started_ts DESC)"
            )

    def begin_run(self, agent: str, *, model_version: str | None = None) -> int:
        started_ts = int(time.time())
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO agent_runs(agent, started_ts, status, model_version)
                VALUES (?, ?, ?, ?)
                """,
                (agent, started_ts, "running", model_version),
            )
            return int(cur.lastrowid)

    def finish_run(
        self,
        run_id: int,
        *,
        status: str,
        observation_count: int = 0,
        error: str | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE agent_runs
                SET finished_ts = ?, status = ?, error = ?, observation_count = ?
                WHERE id = ?
                """,
                (
                    int(time.time()),
                    status,
                    str(error)[:500] if error else None,
                    int(observation_count),
                    int(run_id),
                ),
            )

    def record_observations(
        self, run_id: int | None, observations: Iterable[AgentObservation]
    ) -> int:
        rows = []
        for observation in observations:
            record = observation.to_record()
            rows.append(
                (
                    run_id,
                    record["created_ts"],
                    record["agent"],
                    record["kind"],
                    record["severity"],
                    record["product_id"],
                    record["symbol"],
                    record["summary"],
                    json.dumps(record["evidence"], sort_keys=True),
                    json.dumps(record["source"], sort_keys=True),
                    record["expires_ts"],
                )
            )
        if not rows:
            return 0
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO agent_observations(
                    run_id, created_ts, agent, kind, severity, product_id, symbol,
                    summary, evidence_json, source_json, expires_ts
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def latest(
        self,
        *,
        limit: int = 100,
        agent: str | None = None,
        symbol: str | None = None,
    ) -> list[dict]:
        limit = min(max(int(limit), 1), 250)
        filters = []
        params: list[object] = []
        if agent:
            filters.append("agent = ?")
            params.append(agent)
        if symbol:
            filters.append("symbol = ?")
            params.append(symbol.upper().split("-")[0])
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM agent_observations
                {where}
                ORDER BY created_ts DESC, id DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        return [self._row_to_observation(row) for row in rows]

    def status(self) -> dict:
        with self._connect() as conn:
            total_observations = conn.execute(
                "SELECT COUNT(*) FROM agent_observations"
            ).fetchone()[0]
            last_run = conn.execute(
                """
                SELECT *
                FROM agent_runs
                ORDER BY started_ts DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
            agents = conn.execute(
                """
                SELECT agent, MAX(started_ts) AS last_started_ts,
                       SUM(observation_count) AS observation_count
                FROM agent_runs
                GROUP BY agent
                ORDER BY agent
                """
            ).fetchall()
        return {
            "db_path": str(self.db_path),
            "total_observations": int(total_observations),
            "last_run": dict(last_run) if last_run else None,
            "agents": [dict(row) for row in agents],
        }

    @staticmethod
    def _row_to_observation(row: sqlite3.Row) -> dict:
        item = dict(row)
        item["evidence"] = json.loads(item.pop("evidence_json") or "{}")
        item["source"] = json.loads(item.pop("source_json") or "{}")
        return item

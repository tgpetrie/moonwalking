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

    # A run still marked "running" this long after it started almost certainly
    # died without calling finish_run (crash, closed terminal). One agent pass
    # takes seconds; fifteen minutes is generous.
    STALE_RUN_SECONDS = 15 * 60

    def agent_summaries(
        self,
        known_agents: Iterable[str] = (),
        *,
        now: int | None = None,
    ) -> list[dict]:
        """One row per agent: latest run, derived state, and that run's findings.

        Includes agents in ``known_agents`` that have never run, so the page can
        say so instead of silently leaving them out. State comes only from
        recorded runs:

        - ``never_run``   no run recorded on this machine
        - ``running``     latest run started and has not finished yet
        - ``interrupted`` latest run never finished and is older than
                          STALE_RUN_SECONDS (the process most likely died)
        - ``failed``      latest run finished with status "error"
        - ``idle``        latest run finished OK; agents run on demand, so this
                          is the normal resting state
        """
        now = int(now if now is not None else time.time())
        with self._connect() as conn:
            seen = [
                row[0]
                for row in conn.execute(
                    "SELECT DISTINCT agent FROM agent_runs ORDER BY agent"
                ).fetchall()
            ]
            names = list(dict.fromkeys([*known_agents, *seen]))
            summaries = []
            for name in names:
                latest = conn.execute(
                    """
                    SELECT * FROM agent_runs WHERE agent = ?
                    ORDER BY started_ts DESC, id DESC LIMIT 1
                    """,
                    (name,),
                ).fetchone()
                run_count = conn.execute(
                    "SELECT COUNT(*) FROM agent_runs WHERE agent = ?", (name,)
                ).fetchone()[0]
                by_severity: dict[str, int] = {}
                if latest is not None:
                    for severity, count in conn.execute(
                        """
                        SELECT severity, COUNT(*) FROM agent_observations
                        WHERE run_id = ? GROUP BY severity
                        """,
                        (latest["id"],),
                    ).fetchall():
                        by_severity[severity] = int(count)
                summaries.append(
                    self._summarize(name, latest, int(run_count), by_severity, now)
                )
        return summaries

    def _summarize(
        self,
        name: str,
        latest: sqlite3.Row | None,
        run_count: int,
        by_severity: dict[str, int],
        now: int,
    ) -> dict:
        if latest is None:
            return {
                "agent": name,
                "state": "never_run",
                "run_count": 0,
                "last_activity_ts": None,
                "latest_run": None,
                "latest_findings_by_severity": {},
            }
        run = dict(latest)
        status = run.get("status")
        if status == "running":
            stale = now - int(run["started_ts"]) >= self.STALE_RUN_SECONDS
            state = "interrupted" if stale else "running"
        elif status == "error":
            state = "failed"
        else:
            state = "idle"
        return {
            "agent": name,
            "state": state,
            "run_count": run_count,
            "last_activity_ts": run.get("finished_ts") or run.get("started_ts"),
            "latest_run": run,
            "latest_findings_by_severity": by_severity,
        }

    @staticmethod
    def _row_to_observation(row: sqlite3.Row) -> dict:
        item = dict(row)
        item["evidence"] = json.loads(item.pop("evidence_json") or "{}")
        item["source"] = json.loads(item.pop("source_json") or "{}")
        return item

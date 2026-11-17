from __future__ import annotations

from contextlib import closing, contextmanager
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_EVEN
import json
import os
from pathlib import Path
import sqlite3
import time
from typing import Callable, Iterable

from .contracts import AgentObservation


DEFAULT_DB_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "agent_observations.sqlite"
)

AUTONOMY_MODES = ("approval_queue", "auto_protect_exits")
EXECUTION_MODES = ("dry_run", "live_guarded")
DEFAULT_AUTONOMY_SETTINGS = {
    "autonomy_mode": "approval_queue",
    "execution_mode": "dry_run",
    "emergency_pause": False,
    "daily_order_cap": 3,
}
MAX_DAILY_ORDER_CAP = 20
# Proposal states an operator or the strategist can no longer change.
AUTO_ORDER_STATUSES = ("auto_executed_dry_run", "auto_armed_dry_run")
OPEN_PROPOSAL_STATUSES = frozenset({"pending_approval", "blocked_by_guard"})
# A trim in one of these states has freed USDC for its reload ladder.
RELOAD_PLAN_ACTIVE_STATUSES = ("approved", "auto_executed_dry_run")
PRIVATE_AGENT = "cycle_strategist"


def usdc_cents(value, *, round_down=False) -> int:
    """Use the same precision for persisted budgets, debits and approvals."""
    if type(value) not in (int, float):
        return 0
    amount = Decimal(str(value))
    if not amount.is_finite() or amount <= 0:
        return 0
    rounding = ROUND_DOWN if round_down else ROUND_HALF_EVEN
    return int((amount * 100).to_integral_value(rounding=rounding))


def split_reload_cents(total: int, weights: list[int]) -> list[int]:
    """Allocate every cent, giving the remainder to the closest allocations."""
    combined = sum(weights)
    parts = [divmod(total * weight, combined) for weight in weights]
    cents = [part for part, _ in parts]
    order = sorted(range(len(parts)), key=lambda i: -parts[i][1])
    for index in order[:total - sum(cents)]:
        cents[index] += 1
    return cents


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

    @contextmanager
    def _connection(self, *, write_lock: bool = False):
        with closing(self._connect()) as conn, conn:
            if write_lock:
                conn.execute("BEGIN IMMEDIATE")
            yield conn

    def ensure_db(self) -> None:
        with self._connection() as conn:
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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_autonomy_settings (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    autonomy_mode TEXT NOT NULL,
                    execution_mode TEXT NOT NULL,
                    emergency_pause INTEGER NOT NULL,
                    daily_order_cap INTEGER NOT NULL,
                    updated_ts INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trade_proposals (
                    proposal_id TEXT PRIMARY KEY,
                    run_id INTEGER,
                    agent TEXT NOT NULL,
                    action TEXT NOT NULL,
                    side TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    product_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_ts INTEGER NOT NULL,
                    updated_ts INTEGER NOT NULL,
                    executed_ts INTEGER,
                    proposal_json TEXT NOT NULL,
                    execution_json TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS ix_trade_proposals_status "
                "ON trade_proposals(status, updated_ts DESC)"
            )

    def begin_run(self, agent: str, *, model_version: str | None = None) -> int:
        started_ts = int(time.time())
        with self._connection() as conn:
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
        with self._connection() as conn:
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
        with self._connection() as conn:
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
        include_cycle_strategist: bool = True,
    ) -> list[dict]:
        limit = min(max(int(limit), 1), 250)
        filters = []
        params: list[object] = []
        if not include_cycle_strategist:
            filters.append("agent != ?")
            params.append(PRIVATE_AGENT)
        if agent:
            filters.append("agent = ?")
            params.append(agent)
        if symbol:
            filters.append("symbol = ?")
            params.append(symbol.upper().split("-")[0])
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        with self._connection() as conn:
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

    def status(self, *, include_cycle_strategist: bool = True) -> dict:
        where = "" if include_cycle_strategist else "WHERE agent != ?"
        params = () if include_cycle_strategist else (PRIVATE_AGENT,)
        with self._connection() as conn:
            total_observations = conn.execute(
                f"SELECT COUNT(*) FROM agent_observations {where}", params
            ).fetchone()[0]
            last_run = conn.execute(
                f"""
                SELECT *
                FROM agent_runs
                {where}
                ORDER BY started_ts DESC, id DESC
                LIMIT 1
                """,
                params,
            ).fetchone()
            agents = conn.execute(
                f"""
                SELECT agent, MAX(started_ts) AS last_started_ts,
                       SUM(observation_count) AS observation_count
                FROM agent_runs
                {where}
                GROUP BY agent
                ORDER BY agent
                """,
                params,
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
        include_cycle_strategist: bool = True,
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
        known_agents = tuple(known_agents)
        with self._connection() as conn:
            seen = [
                row[0]
                for row in conn.execute(
                    "SELECT DISTINCT agent FROM agent_runs ORDER BY agent"
                ).fetchall()
            ]
            names = list(dict.fromkeys([*known_agents, *seen]))
            summaries = []
            for name in names:
                if name == PRIVATE_AGENT and not include_cycle_strategist:
                    if name in known_agents:
                        summaries.append(self._summarize(name, None, 0, {}, now))
                    continue
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

    # ─── autonomy settings ────────────────────────────────────────────────

    def get_autonomy_settings(self) -> dict:
        with self._connection() as conn:
            return self._get_autonomy_settings(conn)

    @staticmethod
    def _get_autonomy_settings(conn: sqlite3.Connection) -> dict:
        row = conn.execute(
            "SELECT * FROM agent_autonomy_settings WHERE id = 1"
        ).fetchone()
        if row is None:
            return {**DEFAULT_AUTONOMY_SETTINGS, "updated_ts": None}
        return {
            "autonomy_mode": row["autonomy_mode"],
            "execution_mode": row["execution_mode"],
            "emergency_pause": bool(row["emergency_pause"]),
            "daily_order_cap": int(row["daily_order_cap"]),
            "updated_ts": int(row["updated_ts"]),
        }

    def set_autonomy_settings(self, **changes) -> dict:
        unknown = set(changes) - set(DEFAULT_AUTONOMY_SETTINGS)
        if unknown:
            raise ValueError(f"unknown autonomy settings: {sorted(unknown)}")
        with self._connection(write_lock=True) as conn:
            settings = {**self._get_autonomy_settings(conn), **changes}
            if settings["autonomy_mode"] not in AUTONOMY_MODES:
                raise ValueError(f"invalid autonomy_mode: {settings['autonomy_mode']}")
            if settings["execution_mode"] not in EXECUTION_MODES:
                raise ValueError(f"invalid execution_mode: {settings['execution_mode']}")
            if type(settings["emergency_pause"]) is not bool:
                raise ValueError("emergency_pause must be a boolean")
            cap = settings["daily_order_cap"]
            if type(cap) is not int or not 0 <= cap <= MAX_DAILY_ORDER_CAP:
                raise ValueError(
                    f"daily_order_cap must be an integer from 0 to {MAX_DAILY_ORDER_CAP}"
                )
            updated_ts = int(time.time())
            conn.execute(
                """
                INSERT INTO agent_autonomy_settings(
                    id, autonomy_mode, execution_mode, emergency_pause,
                    daily_order_cap, updated_ts
                )
                VALUES (1, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    autonomy_mode = excluded.autonomy_mode,
                    execution_mode = excluded.execution_mode,
                    emergency_pause = excluded.emergency_pause,
                    daily_order_cap = excluded.daily_order_cap,
                    updated_ts = excluded.updated_ts
                """,
                (
                    settings["autonomy_mode"],
                    settings["execution_mode"],
                    int(settings["emergency_pause"]),
                    cap,
                    updated_ts,
                ),
            )
            return {**settings, "updated_ts": updated_ts}

    # ─── trade proposals ──────────────────────────────────────────────────

    def get_proposal(self, proposal_id: str) -> dict | None:
        with self._connection() as conn:
            return self._get_proposal(conn, proposal_id)

    def _get_proposal(self, conn: sqlite3.Connection, proposal_id: str) -> dict | None:
        row = conn.execute(
            "SELECT * FROM trade_proposals WHERE proposal_id = ?", (proposal_id,)
        ).fetchone()
        return self._row_to_proposal(row) if row else None

    def route_proposal(
        self,
        proposal: dict,
        route: Callable[[dict, int, int], tuple[str, dict | None]],
        *,
        clock: Callable[[], float] = time.time,
    ) -> tuple[dict, dict]:
        """Check current policy and commit one proposal under the same write lock.

        The route callback must be a pure dry-run decision; it cannot do I/O.
        Operator decisions, execution records and UTC-day counts are serialized
        across processes using this ledger.
        """
        with self._connection(write_lock=True) as conn:
            now = clock()
            settings = self._get_autonomy_settings(conn)
            existing = self._get_proposal(conn, proposal["proposal_id"])
            if existing and existing["status"] not in OPEN_PROPOSAL_STATUSES:
                return existing, settings
            day_start = int(now // 86_400) * 86_400
            status, execution = route(
                settings, self._count_auto_orders(conn, day_start, day_start + 86_400), int(now * 1000)
            )
            record = self._save_proposal(
                conn, {**proposal, "status": status}, execution, int(now), None
            )
            return record, settings

    def save_proposal(
        self,
        proposal: dict,
        *,
        run_id: int | None = None,
        execution: dict | None = None,
        now: int | None = None,
    ) -> dict:
        """Insert or refresh a proposal awaiting an operator or a guard recheck."""
        with self._connection(write_lock=True) as conn:
            existing = self._get_proposal(conn, proposal["proposal_id"])
            if existing and existing["status"] not in OPEN_PROPOSAL_STATUSES:
                return existing
            if proposal["status"] not in OPEN_PROPOSAL_STATUSES:
                raise ValueError("closed proposals must go through the decision or routing path")
            return self._save_proposal(
                conn, proposal, execution, int(now if now is not None else time.time()), run_id
            )

    def _save_proposal(
        self, conn: sqlite3.Connection, proposal: dict,
        execution: dict | None, now: int, run_id: int | None,
    ) -> dict:
        executed_ts = now if proposal["status"] in AUTO_ORDER_STATUSES else None
        conn.execute(
            """
            INSERT INTO trade_proposals(
                proposal_id, run_id, agent, action, side, symbol, product_id,
                status, created_ts, updated_ts, executed_ts, proposal_json,
                execution_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(proposal_id) DO UPDATE SET
                run_id = excluded.run_id,
                status = excluded.status,
                updated_ts = excluded.updated_ts,
                executed_ts = excluded.executed_ts,
                proposal_json = excluded.proposal_json,
                execution_json = excluded.execution_json
            """,
            (
                proposal["proposal_id"],
                run_id,
                proposal["agent"],
                proposal["action"],
                proposal["side"],
                proposal["symbol"],
                proposal["product_id"],
                proposal["status"],
                now,
                now,
                executed_ts,
                json.dumps(proposal, sort_keys=True, default=str, allow_nan=False),
                json.dumps(execution, sort_keys=True, default=str, allow_nan=False)
                if execution is not None
                else None,
            ),
        )
        return self._get_proposal(conn, proposal["proposal_id"])

    def list_proposals(
        self, *, status: str | None = None, symbol: str | None = None, limit: int = 100
    ) -> list[dict]:
        limit = min(max(int(limit), 1), 250)
        filters, params = [], []
        if status:
            filters.append("status = ?")
            params.append(status)
        if symbol:
            filters.append("symbol = ?")
            params.append(symbol.upper().split("-")[0])
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        with self._connection() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM trade_proposals {where}
                ORDER BY updated_ts DESC, proposal_id
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        return [self._row_to_proposal(row) for row in rows]

    def decide_proposal(self, proposal_id: str, decision: str) -> dict:
        """Record approval/rejection without placing an order; repeats are no-ops."""
        status = {"approve": "approved", "reject": "rejected"}.get(decision)
        if status is None:
            raise ValueError("decision must be 'approve' or 'reject'")
        with self._connection(write_lock=True) as conn:
            existing = self._get_proposal(conn, proposal_id)
            if existing is None:
                raise KeyError(proposal_id)
            if existing["status"] == status:
                return existing
            if existing["status"] not in OPEN_PROPOSAL_STATUSES:
                raise ValueError(f"proposal is already {existing['status']}")
            if status == "approved" and existing["action"] == "RELOAD_ACCUMULATE":
                self._validate_reload_approval(conn, existing)
            conn.execute(
                "UPDATE trade_proposals SET status = ?, updated_ts = ? WHERE proposal_id = ?",
                (status, int(time.time()), proposal_id),
            )
            return self._get_proposal(conn, proposal_id)

    def active_reload_plans(self, symbol: str | None = None) -> list[dict]:
        """Reload ladders that still hold unspent USDC, oldest first.

        Approved fills debit their allocated amount. Older approved proposals
        treated a named rung as fully spent and retain that behavior.
        """
        with self._connection() as conn:
            conn.execute("BEGIN")
            return self._active_reload_plans(conn, symbol)

    def _active_reload_plans(self, conn, symbol: str | None) -> list[dict]:
        filters, params = "", []
        if symbol:
            filters, params = "AND symbol = ?", [symbol.upper().split("-")[0]]
        trims = conn.execute(
            f"""
            SELECT * FROM trade_proposals
            WHERE action = 'TRIM_TO_USDC' AND status IN (?, ?) {filters}
            ORDER BY created_ts, proposal_id
            """,
            (*RELOAD_PLAN_ACTIVE_STATUSES, *params),
        ).fetchall()
        reloads = conn.execute(
            f"""
            SELECT proposal_json FROM trade_proposals
            WHERE action = 'RELOAD_ACCUMULATE' AND status = 'approved' {filters}
            """,
            params,
        ).fetchall()
        spent = {}
        closed = set()
        for row in reloads:
            evidence = json.loads(row["proposal_json"]).get("evidence") or {}
            for fill in evidence.get("reload_fills") or []:
                if not isinstance(fill, dict):
                    continue
                key = (fill.get("plan_id"), fill.get("tranche"))
                if evidence.get("reload_allocation_version") == 1:
                    spent[key] = spent.get(key, 0) + usdc_cents(fill.get("usdc"))
                else:
                    closed.add(key)
        plans = []
        for row in trims:
            proposal = self._row_to_proposal(row)
            plan = proposal.get("reload_plan")
            if not isinstance(plan, dict) or not plan.get("available"):
                continue
            rungs = [t for t in plan.get("tranches") or [] if isinstance(t, dict)]
            allocations = [usdc_cents(t.get("usdc")) for t in rungs]
            budget = usdc_cents(plan.get("freed_usdc"))
            if proposal["status"] == "auto_executed_dry_run":
                execution = proposal.get("execution") or {}
                budget = min(budget, usdc_cents(execution.get("proceeds_usd")))
            if budget <= 0 or not any(allocations):
                continue
            if sum(allocations) != budget:
                allocations = split_reload_cents(budget, allocations)
            tranches = []
            remaining = 0
            for rung, allocated in zip(rungs, allocations):
                key = (proposal["proposal_id"], rung.get("index"))
                balance = 0 if key in closed else max(0, allocated - spent.get(key, 0))
                remaining += balance
                tranches.append({
                    **rung,
                    "remaining_usdc": balance / 100,
                    "filled": balance == 0,
                })
            if remaining <= 0:
                continue
            plans.append({
                **plan,
                "plan_id": proposal["proposal_id"],
                "symbol": proposal["symbol"],
                "product_id": proposal["product_id"],
                "trim_status": proposal["status"],
                "created_ts": proposal["created_ts"],
                "tranches": tranches,
                "funding_usdc": budget / 100,
                "remaining_usdc": remaining / 100,
            })
        return plans

    def get_compounding_summary(self, prices: dict | None = None) -> dict:
        """What approved and dry-run executed trims, stops and reloads add up to.

        ``prices`` maps a symbol to its current scan price and is only used for
        ``drawdown_avoided_usd``. Extra coins compare what a reload's USDC buys
        at the reload price with what the same USDC bought at the trim's sale
        price, so no fresh cash is counted. Descriptive, dry-run figures.
        """

        def number(value):
            try:
                out = float(value)
            except (TypeError, ValueError):
                return None
            return out if 0 < out < float("inf") else None

        def sale_price(proposal):
            if not proposal:
                return None
            return number((proposal.get("execution") or {}).get("fill_price")) or number(
                proposal.get("reference_price")
            )

        with self._connection() as conn:
            conn.execute("BEGIN")
            plans = self._active_reload_plans(conn, None)
            rows = conn.execute(
                """
                SELECT * FROM trade_proposals
                WHERE status IN (?, ?)
                  AND action IN ('TRIM_TO_USDC', 'PROTECTIVE_STOP', 'RELOAD_ACCUMULATE')
                ORDER BY created_ts, proposal_id
                """,
                RELOAD_PLAN_ACTIVE_STATUSES,
            ).fetchall()
            proposals = [self._row_to_proposal(row) for row in rows]

        trims = {p["proposal_id"]: p for p in proposals if p["action"] == "TRIM_TO_USDC"}
        realized: dict[str, float] = {}
        for proposal in proposals:
            if proposal["action"] != "RELOAD_ACCUMULATE" or proposal["status"] != "approved":
                continue
            bought_at = number(proposal.get("reference_price"))
            for fill in (proposal.get("evidence") or {}).get("reload_fills") or []:
                if not isinstance(fill, dict):
                    continue
                usdc, sold_at = number(fill.get("usdc")), sale_price(trims.get(fill.get("plan_id")))
                if bought_at and usdc and sold_at:
                    symbol = proposal["symbol"]
                    realized[symbol] = realized.get(symbol, 0.0) + usdc / bought_at - usdc / sold_at
        projected = dict(realized)
        for plan in plans:
            sold_at = sale_price(trims.get(plan["plan_id"]))
            for rung in plan["tranches"]:
                level, left = number(rung.get("level")), number(rung.get("remaining_usdc"))
                if sold_at and level and left:
                    symbol = plan["symbol"]
                    projected[symbol] = projected.get(symbol, 0.0) + left / level - left / sold_at

        avoided, priced = 0.0, set()
        for proposal in proposals:
            if proposal["action"] == "RELOAD_ACCUMULATE":
                continue
            price = number((prices or {}).get(proposal["symbol"]))
            sold_at = sale_price(proposal)
            quantity = (
                number((proposal.get("reload_plan") or {}).get("trim_quantity"))
                or number((proposal.get("execution") or {}).get("quantity"))
                or number(proposal.get("quantity"))
                or number((proposal.get("evidence") or {}).get("quantity"))
            )
            if price and sold_at and quantity:
                priced.add(proposal["symbol"])
                if price < sold_at:
                    avoided += (sold_at - price) * quantity
        return {
            "freed_usdc_available": sum(usdc_cents(p["remaining_usdc"]) for p in plans) / 100,
            "active_ladders_count": len(plans),
            "realized_extra_coins_by_symbol": {s: round(v, 8) for s, v in sorted(realized.items())},
            "projected_extra_coins_by_symbol": {s: round(v, 8) for s, v in sorted(projected.items())},
            "drawdown_avoided_usd": round(avoided, 2),
            "drawdown_priced_symbols": sorted(priced),
            "dry_run_only": True,
        }

    def _validate_reload_approval(self, conn, proposal) -> None:
        evidence = proposal.get("evidence") or {}
        fills = evidence.get("reload_fills") or []
        sized = usdc_cents((proposal.get("sizing") or {}).get("suggested_notional_usd"))
        if not fills or not sized:
            raise ValueError("Reload has no allocated size. Refresh the proposal.")
        plans = self._active_reload_plans(conn, proposal["symbol"])
        available = {
            (plan["plan_id"], rung["index"]): usdc_cents(rung["remaining_usdc"])
            for plan in plans
            for rung in plan["tranches"]
        }
        total = 0
        for fill in fills:
            key = (fill.get("plan_id"), fill.get("tranche"))
            amount = usdc_cents(fill.get("usdc"))
            balance = available.pop(key, 0)
            if not 0 < amount <= balance or (
                evidence.get("reload_allocation_version") != 1 and amount != balance
            ):
                raise ValueError("Reload funds are no longer available. Refresh the proposal.")
            total += amount
        if total != sized:
            raise ValueError("Reload allocation does not match the sized buy. Refresh the proposal.")

    @staticmethod
    def _count_auto_orders(
        conn: sqlite3.Connection, since_ts: int, until_ts: int | None = None
    ) -> int:
        return int(
            conn.execute(
                """
                SELECT COUNT(*) FROM trade_proposals
                WHERE status IN (?, ?) AND executed_ts >= ?
                AND (? IS NULL OR executed_ts < ?)
                """,
                (*AUTO_ORDER_STATUSES, since_ts, until_ts, until_ts),
            ).fetchone()[0]
        )

    def count_auto_orders_since(self, since_ts: int) -> int:
        with self._connection() as conn:
            return self._count_auto_orders(conn, int(since_ts))

    @staticmethod
    def _row_to_proposal(row: sqlite3.Row) -> dict:
        item = json.loads(row["proposal_json"])
        item.update(
            status=row["status"],
            run_id=row["run_id"],
            created_ts=row["created_ts"],
            updated_ts=row["updated_ts"],
            executed_ts=row["executed_ts"],
            execution=json.loads(row["execution_json"])
            if row["execution_json"]
            else None,
        )
        return item

    @staticmethod
    def _row_to_observation(row: sqlite3.Row) -> dict:
        item = dict(row)
        item["evidence"] = json.loads(item.pop("evidence_json") or "{}")
        item["source"] = json.loads(item.pop("source_json") or "{}")
        return item

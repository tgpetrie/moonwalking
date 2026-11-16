from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import requests

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from agents.cycle_context import (  # noqa: E402
    build_cycle_context,
    normalize_positions,
    normalize_watchlist,
)
from agents.runner import run_once  # noqa: E402
from agents.store import AgentStore  # noqa: E402


def fetch_json(url: str, *, timeout: float = 12.0, params: dict | None = None) -> dict | None:
    try:
        response = requests.get(url, timeout=timeout, params=params)
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else None
    except requests.RequestException as exc:
        print(f"Local backend unavailable for {url}: {exc}")
        return None


def split_symbols(raw: str) -> list[str]:
    return normalize_watchlist(raw.split(","))


def load_positions(positions_file: str, paper_owner_id: int | None) -> list[dict]:
    """Held positions from a JSON file and/or the owner's open paper positions."""
    rows: list[dict] = []
    if positions_file:
        payload = json.loads(Path(positions_file).expanduser().read_text(encoding="utf-8"))
        items = payload.get("positions") if isinstance(payload, dict) else payload
        if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
            raise ValueError("positions file must contain a list of position objects")
        rows.extend(items)
    if paper_owner_id is not None:
        import paper_execution_store

        rows.extend(paper_execution_store.list_open_positions(paper_owner_id))
    return rows


def repo_status() -> dict:
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    ).stdout.splitlines()
    modified = []
    untracked = []
    for line in status:
        if not line:
            continue
        path = line[3:].replace("\\", "/")
        if line.startswith("??"):
            untracked.append(path)
        else:
            modified.append(path)
    return {"branch": branch, "modified_files": modified, "untracked_files": untracked}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run local Moonwalking agents once against the local backend."
    )
    parser.add_argument("--api-base", default="http://127.0.0.1:5003")
    parser.add_argument("--db-path", default=None)
    parser.add_argument(
        "--symbols",
        default="",
        help="Optional comma-separated symbols for the portfolio risk fallback route.",
    )
    parser.add_argument(
        "--audit-file",
        default="",
        help="Optional path to an AUDIT.md file to turn into local agent work items.",
    )
    parser.add_argument(
        "--watchlist",
        default="",
        help="Comma-separated watchlist for the cycle strategist and smart alerts "
        "(defaults to --symbols).",
    )
    parser.add_argument(
        "--positions-file",
        default="",
        help="JSON list (or {\"positions\": [...]}) of held positions: "
        "symbol, quantity, optional stop_price / higher_low_floor.",
    )
    parser.add_argument(
        "--paper-owner-id",
        type=int,
        default=None,
        help="Also treat this owner's open paper positions as held.",
    )
    parser.add_argument(
        "--no-smart-alerts",
        action="store_true",
        help="Skip smart alert rule evaluation on this pass.",
    )
    args = parser.parse_args()
    if args.paper_owner_id is not None and not 0 < args.paper_owner_id < 2**63:
        parser.error("--paper-owner-id must be a positive SQLite user ID")

    # Follow Flask's configured store paths without enabling notification channels.
    try:
        from dotenv import dotenv_values
    except ImportError:
        pass
    else:
        settings = dotenv_values(BACKEND / ".env")
        for name in ("MW_AGENT_OBSERVATIONS_DB", "MW_SMART_ALERTS_DB", "MW_PAPER_EXECUTION_DB"):
            if settings.get(name):
                os.environ.setdefault(name, settings[name])

    try:
        positions = normalize_positions(load_positions(args.positions_file, args.paper_owner_id))
    except (OSError, ValueError, sqlite3.Error) as exc:
        parser.error(f"cannot load positions: {exc}")

    api_base = args.api_base.rstrip("/")
    context = {
        "board_snapshot": fetch_json(f"{api_base}/data"),
        "repo_status": repo_status(),
    }
    if args.symbols:
        context["risk_board"] = fetch_json(
            f"{api_base}/api/risk-levels/portfolio",
            params={"symbols": ",".join(split_symbols(args.symbols))},
        )
    if args.audit_file:
        audit_path = Path(args.audit_file).expanduser()
        context["audit_markdown"] = audit_path.read_text(encoding="utf-8")
        context["audit_source_path"] = str(audit_path)

    watchlist = split_symbols(args.watchlist or args.symbols)
    # When Flask caps the submitted list, prioritize held coins over watch-only coins.
    scan_symbols = list(dict.fromkeys([*(row["symbol"] for row in positions), *watchlist]))
    params = {"symbols": ",".join(scan_symbols)} if scan_symbols else None
    scan = fetch_json(f"{api_base}/api/macro-cycle-scan", timeout=60.0, params=params)
    # Unlike an in-process scan, a response from HTTP must carry freshness metadata.
    if scan is not None and scan.get("status") != "ready":
        scan = None
    context.update(build_cycle_context(scan, positions=positions, watchlist=watchlist))
    if context["cycle_scan"] is None:
        print("Cycle scan is warming, stale or unavailable; cycle agents skip this pass.")

    engine = None
    if not args.no_smart_alerts:
        from alert_delivery import dispatcher
        from smart_alerts import SmartAlertEngine

        engine = SmartAlertEngine(dispatcher=dispatcher)
    result = run_once(context, store=AgentStore(args.db_path), smart_alert_engine=engine)
    print(result)
    if any(run.get("status") == "error" for run in result.get("runs", [])):
        return 1
    if (result.get("smart_alerts") or {}).get("status") == "error":
        return 1
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())

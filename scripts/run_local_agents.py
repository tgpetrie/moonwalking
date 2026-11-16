from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import subprocess

import requests

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from agents.cycle_context import build_cycle_context, normalize_positions  # noqa: E402
from agents.runner import run_once  # noqa: E402
from agents.store import AgentStore  # noqa: E402


def fetch_json(url: str, *, timeout: float = 12.0) -> dict | None:
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else None
    except requests.RequestException as exc:
        print(f"Local backend unavailable for {url}: {exc}")
        return None


def split_symbols(raw: str) -> list[str]:
    return [part.strip().upper() for part in str(raw or "").split(",") if part.strip()]


def load_positions(positions_file: str, paper_owner_id: int | None) -> list[dict]:
    """Held positions from a JSON file and/or the owner's open paper positions."""
    rows: list[dict] = []
    if positions_file:
        payload = json.loads(Path(positions_file).expanduser().read_text(encoding="utf-8"))
        items = payload.get("positions") if isinstance(payload, dict) else payload
        rows.extend(item for item in items or [] if isinstance(item, dict))
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

    api_base = args.api_base.rstrip("/")
    context = {
        "board_snapshot": fetch_json(f"{api_base}/data"),
        "repo_status": repo_status(),
    }
    if args.symbols:
        context["risk_board"] = fetch_json(
            f"{api_base}/api/risk-levels/portfolio?symbols={args.symbols}"
        )
    if args.audit_file:
        audit_path = Path(args.audit_file).expanduser()
        context["audit_markdown"] = audit_path.read_text(encoding="utf-8")
        context["audit_source_path"] = str(audit_path)

    positions = load_positions(args.positions_file, args.paper_owner_id)
    watchlist = split_symbols(args.watchlist or args.symbols)
    scan_symbols = sorted(
        set(watchlist) | {row["symbol"] for row in normalize_positions(positions)}
    )
    query = f"?symbols={','.join(scan_symbols)}" if scan_symbols else ""
    # The backend serves its cached daily scan; a cold backend answers "warming".
    scan = fetch_json(f"{api_base}/api/macro-cycle-scan{query}", timeout=60.0)
    context.update(build_cycle_context(scan, positions=positions, watchlist=watchlist))
    if context["cycle_scan"] is None:
        print("Cycle scan not ready yet (warming or unavailable); cycle agents skip this pass.")

    engine = None
    if not args.no_smart_alerts:
        from alert_delivery import dispatcher
        from smart_alerts import SmartAlertEngine

        engine = SmartAlertEngine(dispatcher=dispatcher)
    result = run_once(context, store=AgentStore(args.db_path), smart_alert_engine=engine)
    print(result)
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())

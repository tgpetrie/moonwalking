from __future__ import annotations

import argparse
from pathlib import Path
import sys
import subprocess

import requests

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

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
    result = run_once(context, store=AgentStore(args.db_path))
    print(result)
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())

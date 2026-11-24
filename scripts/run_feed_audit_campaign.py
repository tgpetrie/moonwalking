"""Retry interrupted feed captures as separate attempts; never stitch windows."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
PRODUCTS = ["BTC-USD", "SOL-USD", "ALCX-USD", "AURORA-USD"]


def write_state(root, value):
    path = root / "STATUS.json"
    temporary = root / "STATUS.json.tmp"
    temporary.write_text(
        json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def run_once(directory, seconds, products):
    with directory.with_suffix(".stdout.log").open(
        "wb"
    ) as stdout, directory.with_suffix(".stderr.log").open("wb") as stderr:
        return subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/coinbase_feed_audit.py"),
                "capture",
                "--run-dir",
                str(directory),
                "--seconds",
                str(seconds),
                "--products",
                *products,
            ],
            cwd=ROOT,
            stdout=stdout,
            stderr=stderr,
            timeout=seconds + 600,
            check=False,
        ).returncode


def campaign(
    root, seconds=3600, max_attempts=3, products=None, runner=run_once, pause=time.sleep
):
    products = list(PRODUCTS if products is None else products)
    if (
        seconds <= 0
        or not 1 <= max_attempts <= 3
        or not products
        or len(set(products)) != len(products)
    ):
        raise ValueError(
            "positive duration, 1-3 attempts and distinct products required"
        )
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    state = {
        "version": "feed-audit-campaign-v1",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "requested_seconds": seconds,
        "max_attempts": max_attempts,
        "products": products,
        "code_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "controller_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "status": "starting",
        "attempts": [],
        "hour_gate_pass": False,
    }
    write_state(root, state)
    for number in range(1, max_attempts + 1):
        directory = root / f"attempt-{number:02d}"
        state.update(status="capturing", active_attempt=number)
        write_state(root, state)
        attempt = {"attempt": number, "directory": directory.name}
        try:
            attempt["process_exit_code"] = runner(directory, seconds, products)
            report = json.loads((directory / "REPORT.json").read_text(encoding="utf-8"))
            capture = report["capture"]
            completed = (
                attempt["process_exit_code"] == 0
                and capture["completed"]
                and capture["elapsed_seconds"] >= seconds
            )
            attempt.update(
                completed=completed,
                elapsed_seconds=capture["elapsed_seconds"],
                errors=capture.get("errors", []),
                hour_gate_pass=bool(report["hour_gate_pass"]),
            )
            if report["hour_gate_pass"] and not completed:
                raise ValueError(
                    "inconsistent passing report from an incomplete capture"
                )
        except Exception as exc:
            completed = False
            attempt.update(
                completed=False,
                hour_gate_pass=False,
                error_type=type(exc).__name__,
                error=str(exc),
            )
        state["attempts"].append(attempt)
        if completed:
            # Stop even if thin-product evidence is inconclusive. Do not retry
            # completed samples merely to search for a more favorable verdict.
            state.update(
                status=(
                    "complete"
                    if attempt["hour_gate_pass"]
                    else "complete_gate_inconclusive"
                ),
                hour_gate_pass=attempt["hour_gate_pass"],
                report=str(directory / "REPORT.json"),
            )
            write_state(root, state)
            return state
        if number < max_attempts:
            state["status"] = "waiting_to_retry"
            write_state(root, state)
            pause(5 * number)
    state["status"] = "attempts_exhausted"
    write_state(root, state)
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=3600)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--products", nargs="+", default=PRODUCTS)
    args = parser.parse_args()
    result = campaign(args.run_root, args.seconds, args.max_attempts, args.products)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

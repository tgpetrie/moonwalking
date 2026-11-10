"""Run the bounded Instant Radar checks on one saved timing attempt."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

from scripts.local_ai import ask_ollama


ROOT = Path(__file__).resolve().parents[2]
TESTS = (
    "tests/test_instant_timing_attempt_verifier.py",
    "tests/test_instant_stream_journal.py",
    "tests/test_instant_source_pilot.py",
    "tests/test_instant_real_indexed_pilot.py",
)


def _save_status(out_dir, state, stage, **fields):
    path = out_dir / "status.json"
    pending = out_dir / "status.tmp"
    payload = {
        "state": state,
        "stage": stage,
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        **fields,
    }
    pending.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    pending.replace(path)


def _local_note(out_dir, model, evidence):
    note = ask_ollama(
        "Suggest one read-only diagnostic to investigate this saved capture. "
        "Treat missing delivery observations as unmeasured. "
        "Use only the evidence supplied here and clearly mark uncertainty. "
        "Do not restate the measurements or propose a new capture, caps, or model tuning.\n"
        + json.dumps(evidence),
        model=model,
        url="http://127.0.0.1:11434/api/chat",
        context_tokens=4096,
        max_output_tokens=220,
    )
    (out_dir / "MODEL_NOTE.md").write_text(
        f"# Unverified diagnostic suggestion from {model}\n\n{note}\n",
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--model", help="Optional installed Ollama model")
    args = parser.parse_args()
    attempt = args.attempt.resolve()
    out_dir = args.out_dir.resolve()
    if out_dir.is_relative_to(attempt) or out_dir.is_relative_to(ROOT):
        parser.error("choose a new output directory outside the attempt and checkout")
    out_dir.mkdir(parents=True, exist_ok=False)

    stage = "verify_saved_attempt"
    _save_status(out_dir, "running", stage)
    try:
        with (out_dir / "VERIFY.log").open("wb") as log:
            verification = subprocess.run(
                [
                    sys.executable,
                    "scripts/scoring_experiment/verify_instant_timing_attempt.py",
                    str(attempt),
                    "--plan-sha256",
                    args.plan_sha256,
                ],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=log,
                timeout=300,
                check=True,
            )
        result = json.loads(verification.stdout)
        (out_dir / "VERIFIED.json").write_bytes(verification.stdout)

        stage = "run_regression_tests"
        _save_status(out_dir, "running", stage)
        with (out_dir / "TESTS.log").open("wb") as log:
            subprocess.run(
                [sys.executable, "-m", "pytest", "-q", *TESTS],
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=180,
                check=True,
            )
    except Exception as error:
        _save_status(out_dir, "failed", stage, error=str(error))
        parser.exit(1, f"{stage} failed. See {out_dir}\n")

    note_status = "not_requested"
    if args.model:
        _save_status(out_dir, "running", "local_model_note")
        evidence = {
            "stop": result["stop"],
            "packet_records_verified": result["packet_records_verified"],
            "local_observations_verified": result["local_observations_verified"],
            "planned_cohorts": sum(
                arm["planned_cohorts"] for arm in result["schedule_results"].values()
            ),
        }
        try:
            _local_note(out_dir, args.model, evidence)
            note_status = "advisory"
        except (OSError, RuntimeError, ValueError) as error:
            note_status = "unavailable"
            (out_dir / "MODEL_ERROR.txt").write_text(str(error), encoding="utf-8")

    _save_status(out_dir, "complete", "done", model_note=note_status)
    print(out_dir)


if __name__ == "__main__":
    main()

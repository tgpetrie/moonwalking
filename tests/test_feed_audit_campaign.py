"""Controller behavior with synthetic attempt reports, never real market data."""

import importlib.util
import json
from pathlib import Path

import pytest

path = Path(__file__).resolve().parents[1] / "scripts/run_feed_audit_campaign.py"
spec = importlib.util.spec_from_file_location("audit_campaign", path)
controller = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller)


def scripted_attempts(outcomes, calls):
    def run(directory, seconds, products):
        calls.append(directory)
        directory.mkdir()
        outcome = outcomes[len(calls) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        elapsed, completed, passed = outcome
        report = {
            "capture": {
                "completed": completed,
                "elapsed_seconds": elapsed,
                "errors": [],
            },
            "hour_gate_pass": passed,
        }
        (directory / "REPORT.json").write_text(json.dumps(report))
        return 0  # the capture CLI may exit zero even when a connection failed

    return run


def test_interrupted_attempts_are_preserved_but_not_added_together(tmp_path):
    calls = []
    result = controller.campaign(
        tmp_path / "campaign",
        runner=scripted_attempts(
            [(2000, False, False), (2000, False, False), (3600, True, True)], calls
        ),
        pause=lambda _: None,
    )
    assert len(calls) == 3 and all((p / "REPORT.json").exists() for p in calls)
    assert (
        result["hour_gate_pass"] and result["attempts"][-1]["elapsed_seconds"] == 3600
    )
    assert not result["attempts"][0]["completed"]


def test_completed_but_inconclusive_sample_is_not_retried_to_seek_a_pass(tmp_path):
    calls = []
    result = controller.campaign(
        tmp_path / "campaign",
        runner=scripted_attempts([(3600, True, False)], calls),
        pause=lambda _: None,
    )
    assert len(calls) == 1
    assert (
        result["status"] == "complete_gate_inconclusive"
        and not result["hour_gate_pass"]
    )


def test_inconsistent_passing_report_from_incomplete_capture_is_rejected(tmp_path):
    calls = []
    result = controller.campaign(
        tmp_path / "campaign",
        max_attempts=1,
        runner=scripted_attempts([(3600, False, True)], calls),
        pause=lambda _: None,
    )
    assert result["status"] == "attempts_exhausted" and not result["hour_gate_pass"]
    assert result["attempts"][0]["error_type"] == "ValueError"


def test_attempt_limit_and_missing_report_fail_closed(tmp_path):
    calls = []
    result = controller.campaign(
        tmp_path / "campaign",
        max_attempts=2,
        runner=scripted_attempts(
            [RuntimeError("process failed"), (100, False, False)], calls
        ),
        pause=lambda _: None,
    )
    assert len(calls) == 2 and result["status"] == "attempts_exhausted"
    assert not result["hour_gate_pass"]
    assert result["attempts"][0]["error_type"] == "RuntimeError"


def test_existing_campaign_is_not_overwritten(tmp_path):
    root = tmp_path / "campaign"
    root.mkdir()
    (root / "STATUS.json").write_text("preserved")
    with pytest.raises(FileExistsError):
        controller.campaign(root)
    assert (root / "STATUS.json").read_text() == "preserved"


def test_smoke_duration_does_not_become_an_hour_pass(tmp_path):
    calls = []
    result = controller.campaign(
        tmp_path / "campaign",
        seconds=10,
        runner=scripted_attempts([(10, True, False)], calls),
        pause=lambda _: None,
    )
    assert (
        result["status"] == "complete_gate_inconclusive"
        and not result["hour_gate_pass"]
    )

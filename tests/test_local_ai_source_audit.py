"""Input integrity and scoring guards; no local model or network required."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / "scripts/local_ai_source_audit/run.py"
SPEC = importlib.util.spec_from_file_location("local_audit", PATH)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class LocalAuditTests(unittest.TestCase):
    def test_every_packet_has_unique_and_explicit_metric_labels(self):
        for case in audit.build_cases():
            ids = [e["id"] for e in case["evidence"]]
            self.assertEqual(ids, ["asset", "tvl", "dailyFees", "dailyRevenue"])
            self.assertEqual(len(ids), len(set(ids)))
            for evidence in case["evidence"][1:]:
                self.assertEqual(evidence["metric"], evidence["id"])
                self.assertIn("provider_id", evidence)

    def test_parent_provider_ids_cannot_overwrite_evidence_labels(self):
        aave = next(c for c in audit.build_cases() if c["case_id"] == "AAVE")
        self.assertEqual(aave["evidence"][1]["provider_id"], "parent#aave")
        self.assertEqual(aave["evidence"][1]["id"], "tvl")

    def test_gold_answers_never_enter_the_inference_packet(self):
        for case in audit.build_cases():
            payload = audit.request_payload(audit.MODELS[0], case)
            packet = json.loads(payload["messages"][1]["content"])
            self.assertEqual(set(packet), {"case_id", "product_id", "claim", "evidence"})
            self.assertNotIn("expected", packet)
            self.assertNotIn("score", packet)

    def test_unknown_citation_ids_and_wrong_fields_fail(self):
        case = audit.build_cases()[0]
        correct = {**case["expected"], "evidence_ids": ["tvl"]}
        self.assertTrue(audit.score(case, correct)["exact_case_pass"])
        self.assertFalse(audit.score(case, {**correct, "evidence_ids": ["invented"]})["exact_case_pass"])
        self.assertFalse(audit.score(case, {**correct, "tvl_status": "no_series"})["exact_case_pass"])

    def test_empty_successful_series_differs_from_unverified_endpoint(self):
        self.assertEqual(audit.metric_label({"status": "no_daily_series_returned"}), "no_series")
        self.assertEqual(audit.metric_label({"status": "no_successful_response"}), "not_verified")

    def test_incomplete_jobs_remain_pending_in_review_queue(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(audit, "OUT", Path(tmp)):
            row = audit.review_queue([audit.build_cases()[0]])[0]
            self.assertEqual(row["triage_priority"], "high")
            self.assertTrue(all(p["status"] == "pending" for p in row["model_proposals"].values()))
            self.assertTrue(row["human_review_required"])

    def test_model_cannot_overwrite_authoritative_facts(self):
        case = audit.build_cases()[0]
        answer = {**case["expected"], "tvl_status": "no_series", "evidence_ids": ["tvl"], "note": "wrong"}
        record = {"response": {"message": {"content": json.dumps(answer)}}, "score": audit.score(case, answer)}
        with tempfile.TemporaryDirectory() as tmp, patch.object(audit, "OUT", Path(tmp)):
            folder = Path(tmp) / audit.MODELS[0].replace(":", "_")
            folder.mkdir()
            (folder / (case["case_id"] + ".json")).write_text(json.dumps(record))
            row = audit.review_queue([case])[0]
            self.assertEqual(row["authoritative_metric_facts"]["tvl_status"], "available")
            self.assertTrue(any("factual field mismatch" in flag for flag in row["flags"]))

    def test_resume_does_not_claim_an_unrequested_model(self):
        case = audit.build_cases()[0]
        activity = {"requested": False}
        with tempfile.TemporaryDirectory() as tmp, patch.object(audit, "OUT", Path(tmp)):
            folder = Path(tmp) / audit.MODELS[0].replace(":", "_")
            folder.mkdir()
            (folder / (case["case_id"] + ".json")).write_text("{}")
            with patch.object(audit, "build_cases", return_value=[case]), patch.object(audit, "summarize"), \
                    patch.object(audit.urllib.request, "urlopen", side_effect=AssertionError("No inference expected")):
                audit.run(audit.MODELS[0], activity)
            self.assertFalse(activity["requested"])


if __name__ == "__main__":
    unittest.main()

"""Reject evidence loss and false identity promotion in the cohort converter."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/scoring_experiment"))
import apply_verified_cohort_review as review


class CohortReviewTests(unittest.TestCase):
    def fixture(self, folder):
        raw = folder / "AAVE_fees.json"
        review.write(raw, {"id": "parent#aave", "address": "0xabc", "gecko_id": "aave"})
        meta = folder / "AAVE_capture.json"
        review.write(meta, {"http_status": 200, "sha256": review.fd.sha256(raw),
                            "url": "https://api.llama.fi/summary/fees/aave?dataType=dailyFees"})
        manifest = {"files": [{"path": f.name, "sha256": review.fd.sha256(f)} for f in [raw, meta]]}
        held = [{"product_id": "AAVE-USD", "status": "held", "source_ids": {"fees": "aave"},
                 "series_files": {"fees": raw.name}, "series_sha256": {"fees": review.fd.sha256(raw)}}]
        decisions = {"AAVE-USD": {"status": "approved", "source_family": "aave",
                                  "expected_source_id": "parent#aave", "identity_evidence": {
                                      "chain": "ethereum", "contract_address": "0xABC", "gecko_id": "aave"}}}
        coins = [{"id": "AAVE", "name": "Aave", "default_network": "ethereum", "supported_networks": [
            {"id": "ethereum", "contract_address": "0xaBc"}]}]
        return decisions, held, coins, manifest

    def test_preserves_captured_bytes_and_writes_the_actual_gate_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            decisions, held, coins, manifest = self.fixture(folder)
            cohort, _ = review.build(decisions, held, folder, coins, manifest)
            e = cohort[0]
            self.assertEqual(e["series_files"], held[0]["series_files"])
            self.assertEqual(e["series_sha256"], held[0]["series_sha256"])
            self.assertEqual(e["source_ids"]["fees"], "parent#aave")
            self.assertEqual(e["source_metrics"]["fees"], "dailyFees")
            self.assertEqual(e["scope"], "parent")
            self.assertIsInstance(e["identity_evidence"], str)
            self.assertEqual(held[0]["status"], "held")
            self.assertEqual(review.gate.validate_entry(e, review.read(folder / "AAVE_fees.json")), [])

    def test_changed_capture_cannot_be_promoted(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            decisions, held, coins, manifest = self.fixture(folder)
            (folder / "AAVE_fees.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "changed"):
                review.build(decisions, held, folder, coins, manifest)

    def test_wrong_contract_cannot_be_promoted(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            decisions, held, coins, manifest = self.fixture(folder)
            coins[0]["supported_networks"][0]["contract_address"] = "0xdef"
            with self.assertRaisesRegex(ValueError, "contract mismatch"):
                review.build(decisions, held, folder, coins, manifest)

    def test_an_unreviewed_source_id_change_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unreviewed provider id"):
            review.canonical_source("AAVE-USD", "parent#aave", {"id": "parent#other"})

    def test_solana_contract_case_is_not_discarded(self):
        coin = {"id": "JTO", "default_network": "solana", "supported_networks": [
            {"id": "solana", "contract_address": "ABCxyz"}]}
        with self.assertRaisesRegex(ValueError, "contract mismatch"):
            review.verify_identity("JTO-USD", {"id": "parent#jito", "address": "solana:abcxyz"},
                                   coin, {"chain": "solana", "contract_address": "abcxyz"})

    def test_proposal_code_is_not_executed(self):
        text = "```python\nraise RuntimeError('must not run')\nDECISIONS = {'A': {'status':'held'}}\n```"
        self.assertEqual(review.proposed_decisions(text), {"A": {"status": "held"}})
        with self.assertRaises(ValueError):
            review.proposed_decisions("```python\nDECISIONS = dict(A='held')\n```")

    def test_op_amendment_uses_exact_verified_nested_capture_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            raw = folder / "OP_alternative_fees.json"
            review.write(raw, {"id": "chain#optimism", "category": "Chain", "gecko_id": "optimism"})
            meta = folder / "OP_alternative_capture.json"
            review.write(meta, {"http_status": 200, "sha256": review.fd.sha256(raw),
                                "url": "https://api.llama.fi/summary/fees/op-mainnet?dataType=dailyFees"})
            manifest = {"files": [{"path": f.name, "sha256": review.fd.sha256(f)} for f in [raw, meta]]}
            held = [{"product_id": "OP-USD", "status": "held", "source_ids": {"fees": "optimism"}}]
            decisions = {"OP-USD": {"status": "held", "source_family": "optimism"}}
            coins = [{"id": "OP", "default_network": "optimism", "supported_networks": [
                {"id": "optimism", "contract_address": review.GOVERNANCE_CONTRACTS["OP-USD"]}]}]
            self.assertEqual(review.build(decisions, held, folder, coins, manifest)[0][0]["status"], "held")
            e = review.build(decisions, held, folder, coins, manifest, amend_op=True)[0][0]
            self.assertEqual(e["series_files"]["fees"], raw.name)
            self.assertEqual(e["series_sha256"]["fees"], review.fd.sha256(raw))
            self.assertEqual(e["source_ids"]["fees"], "chain#optimism")
            self.assertEqual(e["identity_verification"]["association_role"], "governance_token_chain_context")


if __name__ == "__main__":
    unittest.main()

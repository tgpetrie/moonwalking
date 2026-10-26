"""Apply local, evidenced decisions to Gemini's proposal; never execute its code.

Reads retained public captures and their frozen manifest. No network, returns,
model fitting or live application access. Holds remain holds unless the explicit
OP Mainnet amendment is requested and independently validated.
"""
from __future__ import annotations

import argparse
import ast
import copy
import json
import re
from pathlib import Path

import fundamentals as fd
import fundamentals_gate as gate
import panel

ROOT = Path(__file__).resolve().parents[2]
PRIOR = ROOT / "docs/research/results/fundamentals_review_20261026"
OUT = ROOT / "docs/research/results/fundamentals_cohort_acceptance_20261026"
CAPTURES = Path.home() / ".moonwalking/analysis/fundamentals_review_20261026"
CURRENCIES = Path.home() / ".moonwalking/analysis/source_review_20261026/coinbase_currencies.json"
REVIEW_DATE = "2026-10-26"
ID_AMENDMENTS = {"YFI-USD": ("119", "113"), "ORCA-USD": ("283", "parent#orca"),
                 "PENDLE-USD": ("382", "parent#pendle")}
CHAIN_LINKS = {
    "ETH-USD": ("ethereum", "chain#ethereum", "ethereum"),
    "SOL-USD": ("solana", "chain#solana", "solana"),
    "AVAX-USD": ("avacchain", "chain#avalanche", "avalanche-2"),
    "NEAR-USD": ("near", "chain#near", "near"),
    "ADA-USD": ("cardano", "chain#cardano", "cardano"),
    "APT-USD": ("aptos", "chain#aptos", "aptos"),
    "INJ-USD": ("injective", "chain#injective", "injective-protocol"),
    "ARB-USD": ("arbitrum", "chain#arbitrum", "arbitrum"),
    "OP-USD": ("optimism", "chain#optimism", "optimism"),
    "SEI-USD": ("seievm", "chain#sei", "sei-network"),
    "SUI-USD": ("sui", "chain#sui", "sui"),
    "STX-USD": ("stacks", "chain#stacks", "blockstack"),
}
GOVERNANCE_CONTRACTS = {"ARB-USD": "0x912ce59144191c1204e64559fe8253a0e49e6548",
                        "OP-USD": "0x4200000000000000000000000000000000000042"}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")


def proposed_decisions(text):
    """Only literal table data is accepted; imports and function bodies never run."""
    blocks = re.findall(r"```python\s*\n(.*?)```", text, re.S)
    found = []
    for block in blocks:
        for node in ast.parse(block).body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "DECISIONS":
                found.append(ast.literal_eval(node.value))
            elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "DECISIONS" for t in node.targets):
                found.append(ast.literal_eval(node.value))
    if len(found) != 1 or not isinstance(found[0], dict):
        raise ValueError("Expected one literal DECISIONS table")
    return found[0]


def address(value):
    """EVM case is immaterial; Solana/base58 case is preserved."""
    value = value or ""
    value = value.split(":", 1)[-1]
    return value.lower() if value.startswith("0x") else value


def verify_identity(pid, doc, coin, proposal):
    if coin.get("id") != pid.removesuffix("-USD"):
        raise ValueError(f"{pid}: Coinbase identity missing")
    facts = {"coinbase_id": coin["id"], "coinbase_name": coin.get("name"),
             "coinbase_default_network": coin.get("default_network"), "source_id": doc.get("id"),
             "source_name": doc.get("name"), "source_address": doc.get("address"),
             "source_gecko_id": doc.get("gecko_id"), "source_linked_protocols": doc.get("linkedProtocols"),
             "interpretation_limit": "Protocol/chain activity context; no direct token-revenue or value-accrual claim."}
    if pid in CHAIN_LINKS:
        network, provider, gecko = CHAIN_LINKS[pid]
        if (coin.get("default_network"), doc.get("id"), doc.get("gecko_id"), doc.get("category")) != (network, provider, gecko, "Chain"):
            raise ValueError(f"{pid}: native/associated-chain identity mismatch")
        if pid in GOVERNANCE_CONTRACTS:
            contracts = [address(n.get("contract_address")) for n in coin.get("supported_networks", []) if n.get("id") == network]
            if GOVERNANCE_CONTRACTS[pid] not in contracts:
                raise ValueError(f"{pid}: governance contract mismatch")
            facts["association_role"] = "governance_token_chain_context"
            facts["verified_governance_contract"] = GOVERNANCE_CONTRACTS[pid]
        else:
            facts["association_role"] = "native_asset_chain_context"
    else:
        raw = doc.get("address") or ""
        declared_network = raw.split(":", 1)[0] if ":" in raw else proposal.get("chain")
        contracts = [address(n.get("contract_address")) for n in coin.get("supported_networks", []) if n.get("id") == declared_network]
        source = address(raw)
        if not source or source not in contracts or source != address(proposal.get("contract_address")):
            raise ValueError(f"{pid}: source/Coinbase/proposed contract mismatch")
        if doc.get("gecko_id") and doc["gecko_id"] != proposal.get("gecko_id"):
            raise ValueError(f"{pid}: provider/proposed CoinGecko identity mismatch")
        facts["association_role"] = "token_associated_protocol_context"
        facts["verified_contract_network"] = declared_network
        facts["verified_contract"] = source
    return facts


def canonical_source(pid, proposed_id, doc):
    actual = str(doc.get("id") or "")
    if actual != proposed_id and ID_AMENDMENTS.get(pid) != (proposed_id, actual):
        raise ValueError(f"{pid}: unreviewed provider id change {proposed_id!r} -> {actual!r}")
    return actual, "parent" if actual.startswith("parent#") else "chain" if actual.startswith("chain#") else "protocol"


def build(decisions, held, captures, currencies, manifest, amend_op=False):
    if len({r["product_id"] for r in held}) != len(held) or set(decisions) != {r["product_id"] for r in held}:
        raise ValueError("Proposal and worksheet must contain the same unique product IDs")
    known = {r["path"]: r for r in manifest["files"]}
    coins = {r["id"]: r for r in currencies}

    def captured(name):
        path = captures / name
        if name not in known or fd.sha256(path) != known[name]["sha256"]:
            raise ValueError(f"Capture not in frozen manifest or changed: {name}")
        return read(path)

    cohort, evidence = [], []
    for original in held:
        e = copy.deepcopy(original)
        pid = e["product_id"]
        decision = decisions[pid]
        e["gemini_proposed_status"] = decision["status"]
        e["status"] = "held"
        if decision["status"] != "approved" and not (pid == "OP-USD" and amend_op):
            e["hold_reason"] = decision.get("hold_reason", "Held in the supplied proposal")
            cohort.append(e)
            continue
        if pid == "OP-USD":
            # Exact retained names, bound to the frozen manifest; never glob or
            # use guessed IDs. The old failed capture is retained separately.
            meta = captured("OP_alternative_capture.json")
            filename = "OP_alternative_fees.json"
            expected_id = "chain#optimism"
            proposal = {"chain": "optimism", "contract_address": GOVERNANCE_CONTRACTS[pid]}
        else:
            filename = original["series_files"]["fees"]
            meta = captured(pid.removesuffix("-USD") + "_capture.json")
            expected_id = decision.get("expected_source_id")
            proposal = decision.get("identity_evidence", {})
        doc = captured(filename)
        if meta.get("http_status") != 200 or fd.sha256(captures / filename) != meta.get("sha256"):
            raise ValueError(f"{pid}: missing successful, hash-verified fee response")
        if pid != "OP-USD" and original["series_sha256"]["fees"] != meta["sha256"]:
            raise ValueError(f"{pid}: worksheet/capture hash mismatch")
        if "dataType=dailyFees" not in meta.get("url", ""):
            raise ValueError(f"{pid}: capture is not a dailyFees request")
        source, scope = canonical_source(pid, expected_id, doc)
        facts = verify_identity(pid, doc, coins.get(pid.removesuffix("-USD"), {}), proposal)
        e.update(status="approved", scope=scope, source_family=decision["source_family"],
                 reviewer="Codex: local captured-identity and scope review", reviewed_at=REVIEW_DATE,
                 source_ids={"fees": source}, source_metrics={"fees": "dailyFees"},
                 source_urls={"fees": meta["url"]}, series_files={"fees": filename},
                 series_sha256={"fees": meta["sha256"]},
                 identity_evidence=json.dumps(facts, sort_keys=True), identity_verification=facts,
                 returned_metadata={k: doc.get(k) for k in ["id", "name", "category", "address", "gecko_id", "linkedProtocols"]})
        if pid in ID_AMENDMENTS:
            e["source_amendment"] = {"gemini_expected_id": expected_id, "locally_verified_id": source,
                                     "reason": "Current captured fee source ID/scope, independently matched by token contract"}
        if pid == "OP-USD":
            e["source_amendment"] = {"old_source_slug": original.get("source_ids", {}).get("fees"),
                                     "reason": "Adopt retained op-mainnet dailyFees diagnostic; original optimism request failed"}
        if gate.validate_entry(e, doc):
            raise ValueError(f"{pid}: does not meet hardened entry validation: {gate.validate_entry(e, doc)}")
        cohort.append(e)
        evidence.append({"product_id": pid, **facts})
    return cohort, evidence


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--submission", type=Path, default=OUT / "GEMINI_SUBMISSION.md")
    ap.add_argument("--captures", type=Path, default=CAPTURES)
    ap.add_argument("--amend-op-mainnet", action="store_true")
    a = ap.parse_args()
    if fd.sha256(CURRENCIES) != read(PRIOR / "MEASUREMENTS.json")["coinbase_identity_capture_sha256"]:
        raise ValueError("Coinbase currency capture differs from the reviewed snapshot")
    decision = proposed_decisions(a.submission.read_text(encoding="utf-8"))
    cohort, evidence = build(decision, read(PRIOR / "PROPOSED_COHORT_HELD.json"), a.captures,
                             read(CURRENCIES), read(PRIOR / "CAPTURE_MANIFEST.json"), a.amend_op_mainnet)
    cov = gate.coverage(cohort, a.captures, gate.eligible_index(panel.load_config()))
    verdict = gate.evaluate_gate(cov["per_day_counts"], cov["problems"])
    counts = cov["per_day_counts"]
    report = {"gate_code_commit": "8047ba75c78441bb96b95a478c62292f7355f004", "gate": verdict,
              "gate_source_sha256": fd.sha256(Path(gate.__file__)),
              "fundamentals_config_sha256": fd.sha256(Path(__file__).with_name("fundamentals_config.json")),
              "held_worksheet_sha256": fd.sha256(PRIOR / "PROPOSED_COHORT_HELD.json"),
              "capture_manifest_sha256": fd.sha256(PRIOR / "CAPTURE_MANIFEST.json"),
              "cohort_entries": len(cohort), "approved": sum(e["status"] == "approved" for e in cohort),
              "held": sum(e["status"] == "held" for e in cohort), "op_amendment_applied": a.amend_op_mainnet,
              "provenance": "retrospective_catalog_backfill_subject_to_adapter_revisions",
              "outcome_values_used": False, "submission_sha256": fd.sha256(a.submission),
              "coinbase_currencies_sha256": fd.sha256(CURRENCIES), "per_product": cov["per_product"],
              "per_day_counts": {str(d.date()): int(n) for d, n in counts.items()}}
    write(OUT / "REVIEWED_COHORT.json", cohort)
    write(OUT / "IDENTITY_VERIFICATION.json", evidence)
    write(OUT / "GATE_REPORT.json", report)
    print(json.dumps({k: report[k] for k in ["approved", "held", "gate"]}, indent=2))
    return 0 if verdict["gate_passed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())

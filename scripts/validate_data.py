"""Validate fixture integrity and relationships without network access."""

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(root):
    root = root.resolve()
    def read(path):
        return json.loads((root / path).read_text(encoding="utf-8"))

    manifest = read("knowledge_base/source_manifest.json")
    seen = set()
    for source in manifest["sources"]:
        path = (root / source["path"]).resolve()
        require(path.is_relative_to(root), "Source path escapes project")
        require(source["path"] not in seen, "Duplicate manifest path")
        seen.add(source["path"])
        require(hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"], f"Source hash mismatch: {source['path']}")

    def records(path):
        require(path in seen, f"Unregistered source: {path}")
        payload = read(path)
        require(payload["schema_version"] == 1, f"Unsupported schema: {path}")
        return payload["records"]

    def indexed(path, key):
        rows = records(path)
        result = {row[key]: row for row in rows}
        require(len(rows) == len(result), f"Duplicate IDs: {path}")
        require(all(row.get("synthetic") is True for row in rows), f"Missing synthetic marker: {path}")
        return result

    customers = indexed("data/customers/customers.json", "customer_id")
    policies = indexed("data/policies/policies.json", "policy_id")
    rules = indexed("data/rules/policy_rules.json", "rule_id")
    claims = indexed("data/demo_claims/claims.json", "claim_id")
    history = indexed("data/historical_claims/claims.json", "claim_id")
    docs = indexed("data/claim_documents/documents.json", "document_id")
    require(len({r['insurance_line'] for r in rules.values()}) == 7, "Must cover all seven insurance lines")
    require(not claims.keys() & history.keys(), "Current and historical claim IDs overlap")
    for rule in rules.values():
        require(not set(rule["covered_events"]) & set(rule["excluded_events"]), "Coverage conflicts with exclusion")
        require(0 <= rule["deductible_inr"] <= rule["per_claim_limit_inr"], "Invalid deductible")
        require(0 <= rule["stp_claim_ceiling_inr"] <= rule["per_claim_limit_inr"], "Invalid STP ceiling")
        require(rule["settlement_mode"] in {"reimbursement", "fixed_benefit"}, "Unknown settlement mode")
    for policy in policies.values():
        require(policy["customer_id"] in customers, "Unknown policy customer")
        require(policy["rule_id"] in rules, "Unknown policy rule")
        require(policy["insurance_line"] == rules[policy["rule_id"]]["insurance_line"], "Policy/rule line mismatch")
        require(date.fromisoformat(policy["start_date"]) <= date.fromisoformat(policy["end_date"]), "Invalid policy dates")
    for claim in list(claims.values()) + list(history.values()):
        require(claim["policy_id"] in policies, "Unknown claim policy")
        policy = policies[claim["policy_id"]]
        require(claim["customer_id"] == policy["customer_id"], "Claim/policy customer mismatch")
        require(claim["currency"] == policy["currency"] == "INR", "Currency mismatch")
        require(type(claim["claimed_amount_inr"]) is int and claim["claimed_amount_inr"] > 0, "Invalid amount")
        incident, submitted = map(date.fromisoformat, (claim["incident_date"], claim["submitted_date"]))
        require(incident <= submitted <= date(2026, 10, 1), "Invalid claim chronology")
        require(date.fromisoformat(policy["start_date"]) <= incident <= date.fromisoformat(policy["end_date"]), "Baseline incident outside policy dates")
        if "closed_date" in claim:
            require(submitted <= date.fromisoformat(claim["closed_date"]) <= date(2026, 10, 1), "Invalid historical closure date")
            require(0 <= claim["settled_amount_inr"] <= rules[policy["rule_id"]]["per_claim_limit_inr"], "Invalid historical settlement")
        else:
            require(claim["insurance_line"] == policy["insurance_line"], "Claim/policy line mismatch")
    for document in docs.values():
        require(document["claim_id"] in claims, "Document references unknown claim")
        require(document["path"] in seen, "Unregistered document")
        require(document["verification_status"] == "unverified", "Fixtures must not claim evidence verification")
        require(hashlib.sha256((root / document["path"]).read_bytes()).hexdigest() == document["sha256"], "Document hash mismatch")
    for claim in claims.values():
        rule = rules[policies[claim["policy_id"]]["rule_id"]]
        supplied = {doc["document_type"] for doc in docs.values() if doc["claim_id"] == claim["claim_id"]}
        require(set(rule["required_documents"]) <= supplied, "Baseline claim missing document")
    routing = records("data/rules/routing_rules.json")
    require(0 <= routing["minimum_evidence_confidence"] <= 1, "Invalid confidence threshold")
    require(0 <= routing["stp_risk_max"] < routing["investigation_risk_min"] <= 100, "Invalid risk thresholds")
    indicators = indexed("data/rules/anomaly_indicators.json", "indicator_id")
    require(all(0 <= row["points"] <= 100 for row in indicators.values()), "Invalid indicator points")
    return {"customers": len(customers), "policies": len(policies), "policy_rules": len(rules),
            "demo_claims": len(claims), "historical_claims": len(history), "documents": len(docs), "registered_sources": len(seen)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        counts = validate(args.data_root)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f"FAIL: {error}\n")
    print("PASS: baseline fixture integrity and relationships")
    for name, count in counts.items():
        print(f"  {name}: {count}")

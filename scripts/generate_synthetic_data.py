"""Create deterministic academic fixtures. Never silently replace changed files."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO_DATE = "2026-10-01"
# line, code, covered event, excluded event, evidence type, mode, limit, deductible, STP ceiling
LINES = [
    ("Motor – Car", "MTR", "collision", "mechanical_breakdown", "repair_estimate", "reimbursement", 500000, 2000, 50000),
    ("Motor – Bike", "BIK", "collision", "wear_and_tear", "repair_estimate", "reimbursement", 100000, 500, 15000),
    ("Health", "HLT", "hospitalization", "cosmetic_procedure", "hospital_bill", "reimbursement", 500000, 1000, 40000),
    ("Life", "LIF", "insured_death", "policy_maturity", "death_certificate", "fixed_benefit", 1000000, 0, 0),
    ("Travel", "TRV", "baggage_loss", "change_of_mind", "carrier_loss_report", "reimbursement", 100000, 1000, 20000),
    ("Home/Property", "HOM", "fire_damage", "gradual_deterioration", "damage_assessment", "reimbursement", 2000000, 5000, 75000),
    ("Personal Accident", "PAC", "accidental_fracture", "illness", "medical_certificate", "fixed_benefit", 50000, 0, 50000),
]


def build_files():
    customers, policies, history, claims, documents, rules = [], [], [], [], [], []
    files = {}
    for index, (line, code, event, exclusion, evidence, mode, limit, deductible, ceiling) in enumerate(LINES, 1):
        customer_id = f"CUST-{index:06d}"
        policy_id = f"POL-{code}-{index:06d}"
        rule_id = f"RULE-{code}-V1"
        claim_id = f"CLM-{index:06d}"
        amount = limit if mode == "fixed_benefit" else ceiling // 2
        customers.append({"customer_id": customer_id, "display_name": f"Synthetic Customer {index:03d}", "synthetic": True})
        policies.append({"policy_id": policy_id, "customer_id": customer_id, "insurance_line": line,
                         "rule_id": rule_id, "start_date": "2026-01-01", "end_date": "2026-12-31",
                         "premium_paid": True, "currency": "INR", "synthetic": True})
        rules.append({"rule_id": rule_id, "version": 1, "insurance_line": line,
                      "coverage_clause": f"{code}-COV-01", "covered_events": [event],
                      "exclusion_clause": f"{code}-EXC-01", "excluded_events": [exclusion],
                      "document_clause": f"{code}-DOC-01", "required_documents": ["claim_form", evidence],
                      "settlement_clause": f"{code}-SET-01", "settlement_mode": mode,
                      "per_claim_limit_inr": limit, "deductible_inr": deductible,
                      "fixed_benefit_inr": limit if mode == "fixed_benefit" else None,
                      "stp_clause": f"{code}-STP-01", "stp_claim_ceiling_inr": ceiling,
                      "mandatory_human_review": code == "LIF", "synthetic": True})
        claims.append({"claim_id": claim_id, "customer_id": customer_id, "policy_id": policy_id,
                       "insurance_line": line, "incident_id": f"INC-DEMO-{index:06d}",
                       "incident_date": "2026-09-20", "submitted_date": DEMO_DATE, "event_type": event,
                       "claimed_amount_inr": amount, "currency": "INR", "synthetic": True})
        for number, kind in enumerate(["claim_form", evidence], 1):
            document_id = f"DOC-{index:06d}-{number:02d}"
            path = f"data/claim_documents/text/{document_id}.txt"
            content = (f"SYNTHETIC ACADEMIC DOCUMENT — NOT A REAL INSURANCE RECORD\n"
                       f"Document: {document_id}\nType: {kind}\nClaim: {claim_id}\n"
                       f"Policy: {policy_id}\nIncident date: 2026-09-20\nEvent: {event}\n"
                       f"Claimed amount INR: {amount}\n")
            if mode == "reimbursement" and number == 2:
                content += f"Supported expense INR: {amount}\n"
            files[path] = content
            documents.append({"document_id": document_id, "claim_id": claim_id, "document_type": kind,
                              "path": path, "sha256": hashlib.sha256(content.encode()).hexdigest(),
                              "verification_status": "unverified", "synthetic": True})
        # A past life-death claim on the same policy would contradict this demo.
        if code != "LIF":
            history.append({"claim_id": f"CLM-HIST-{index:06d}", "policy_id": policy_id,
                            "customer_id": customer_id, "incident_id": f"INC-HIST-{index:06d}",
                            "incident_date": "2026-03-10", "submitted_date": "2026-03-12",
                            "closed_date": "2026-03-15", "event_type": event, "claimed_amount_inr": amount,
                            "settled_amount_inr": limit if mode == "fixed_benefit" else max(0, min(amount, limit) - deductible),
                            "route": "Human Review", "status": "Closed", "currency": "INR", "synthetic": True})
    payloads = {
        "data/customers/customers.json": customers,
        "data/policies/policies.json": policies,
        "data/historical_claims/claims.json": history,
        "data/claim_documents/documents.json": documents,
        "data/demo_claims/claims.json": claims,
        "data/rules/policy_rules.json": rules,
        "data/rules/routing_rules.json": {
            "rule_id": "ROUTING-V1", "synthetic": True, "minimum_evidence_confidence": 0.9,
            "stp_risk_max": 19, "investigation_risk_min": 60,
            "precedence": ["Investigation", "Pending Documents", "Human Review", "Rejected", "STP Approved"],
            "notes": "Design contract only. Unresolved contradictions or low confidence block final decisions. Rejection requires verified affirmative exclusion or invalid-policy evidence."},
        "data/rules/anomaly_indicators.json": [
            {"indicator_id": "RISK-DUP-01", "points": 60, "condition": "Same policy and incident ID as a prior claim", "synthetic": True},
            {"indicator_id": "RISK-FREQ-01", "points": 25, "condition": "At least 3 earlier claims on the same policy in the 90 days before submission", "synthetic": True},
            {"indicator_id": "RISK-CONFLICT-01", "points": 35, "condition": "Conflicting incident dates in submitted evidence", "synthetic": True},
        ],
    }
    for path, records in payloads.items():
        files[path] = json.dumps({"schema_version": 1, "dataset_id": "INSUREFLOW-DEMO-V1",
                                 "as_of_date": DEMO_DATE, "records": records}, indent=2, ensure_ascii=False) + "\n"
    files["knowledge_base/source_manifest.json"] = json.dumps({
        "manifest_version": 1, "approval_scope": "Synthetic academic fixtures only; not claim verification",
        "sources": [{"source_id": f"SRC-{i:03d}", "path": path,
                     "sha256": hashlib.sha256(content.encode()).hexdigest(),
                     "approved_for": "untrusted_claim_evidence" if path.startswith("data/claim_documents/") else "internal_reference"}
                    for i, (path, content) in enumerate(sorted(files.items()), 1)]
    }, indent=2) + "\n"
    return files


def generate(root):
    files = build_files()
    for relative, content in files.items():
        target = root / relative
        if target.exists() and target.read_bytes() != content.encode():
            raise ValueError(f"Refusing to overwrite changed file: {target}")
    for relative, content in files.items():
        target = root / relative
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
    return len(files)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT)
    args = parser.parse_args()
    print(f"Synthetic fixture files ready: {generate(args.output_dir)}")

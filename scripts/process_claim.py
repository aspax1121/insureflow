"""Run a registered synthetic claim and save its audit report locally."""

import argparse
from pathlib import Path
import sys

# Allow the documented direct invocation from any working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.engine import ROOT, process_claim, save_report
from backend.evidence import EvidenceStore, index_records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--claim-id')
    group.add_argument('--all', action='store_true', help='Process all seven baseline submissions')
    args = parser.parse_args()
    if args.all:
        try:
            claims = index_records(EvidenceStore(ROOT).records('data/demo_claims/claims.json'), 'claim_id')
        except (ValueError, OSError, KeyError, TypeError) as error:
            parser.exit(1, f'Cannot load claim list: {error}\n')
        ids = list(claims)
    else:
        ids = [args.claim_id]
    blocked = False
    for claim_id in ids:
        result = process_claim(claim_id)
        report_path = save_report(result)
        print(f"\n{claim_id} → {result['route']}")
        print(f"  Reason: {'; '.join(result['reasons'])}")
        print(f"  Estimated settlement INR: {result['estimated_settlement_inr']}")
        print(f"  Evidence confidence: {result['confidence']} (deterministic sufficiency score)")
        print(f"  Risk: {result['risk_score']}; external sources accessed: {result['external_sources_accessed']}")
        for stage in result['agent_audit_trail']:
            print(f"  {stage['stage']}: {stage['status']}")
        print(f'  Audit report: {report_path}')
        blocked |= result['processing_status'] == 'blocked'
    return int(blocked)


if __name__ == '__main__':
    raise SystemExit(main())

"""Run an evidence-gated, deterministic claim simulation."""

from datetime import date, datetime, timezone
import json
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from agents.stages import STAGES, STAGE_NAMES, finding
from backend.evidence import EvidenceError, EvidenceStore, index_records

ROOT = Path(__file__).resolve().parents[1]


def load_context(store, claim_id, as_of):
    def indexed(path, key):
        return index_records(store.records(path), key)
    ctx = {
        'store': store, 'as_of': as_of, 'audit': [], 'review': [], 'rejections': [],
        'confidence': 1.0, 'risk': 0, 'estimate': None, 'evidence_complete': False,
        'policy_status': 'unresolved', 'coverage_status': 'unresolved', 'missing': [],
        'customers': indexed('data/customers/customers.json', 'customer_id'),
        'policies': indexed('data/policies/policies.json', 'policy_id'),
        'rules': indexed('data/rules/policy_rules.json', 'rule_id'),
        'history': indexed('data/historical_claims/claims.json', 'claim_id'),
        'documents': index_records(store.documents(), 'document_id'),
        'indicators': indexed('data/rules/anomaly_indicators.json', 'indicator_id'),
        'routing': store.records('data/rules/routing_rules.json'),
    }
    claims = indexed('data/demo_claims/claims.json', 'claim_id')
    if claim_id not in claims:
        raise EvidenceError(f'Unknown claim ID: {claim_id}')
    ctx['claim'] = claims[claim_id]
    routing = ctx['routing']
    if (routing['precedence'] != ['Investigation', 'Pending Documents', 'Human Review', 'Rejected', 'STP Approved']
            or not 0 < routing['minimum_evidence_confidence'] <= 1
            or not 0 <= routing['stp_risk_max'] < routing['investigation_risk_min'] <= 100):
        raise EvidenceError('Invalid or unsupported routing configuration')
    for rule in ctx['rules'].values():
        if (rule['settlement_mode'] not in {'reimbursement', 'fixed_benefit'}
                or set(rule['covered_events']) & set(rule['excluded_events'])
                or not rule['required_documents'] or 'claim_form' not in rule['required_documents']
                or not 0 <= rule['deductible_inr'] <= rule['per_claim_limit_inr']
                or not 0 <= rule['stp_claim_ceiling_inr'] <= rule['per_claim_limit_inr']
                or type(rule['mandatory_human_review']) is not bool):
            raise EvidenceError('Invalid policy rule configuration')
        if rule['settlement_mode'] == 'fixed_benefit' and not 0 < rule['fixed_benefit_inr'] <= rule['per_claim_limit_inr']:
            raise EvidenceError('Invalid fixed benefit')
    for policy in ctx['policies'].values():
        rule = ctx['rules'].get(policy['rule_id'])
        if rule and rule['insurance_line'] != policy['insurance_line']:
            raise EvidenceError('Policy/rule line mismatch')
        if policy['currency'] != 'INR' or date.fromisoformat(policy['start_date']) > date.fromisoformat(policy['end_date']):
            raise EvidenceError('Invalid policy dates or currency')
    for key in ('RISK-DUP-01', 'RISK-FREQ-01', 'RISK-CONFLICT-01'):
        points = ctx['indicators'][key]['points']
        if type(points) is not int or not 0 <= points <= 100:
            raise EvidenceError('Invalid risk points')
    return ctx


def process_claim(claim_id, root=ROOT, as_of=date(2026, 10, 1)):
    started = perf_counter()
    timestamp = datetime.now(timezone.utc).isoformat()
    store, ctx = None, None
    audit = []
    failure = None
    try:
        store = EvidenceStore(root)
        ctx = load_context(store, claim_id, as_of)
        audit = ctx['audit']
        for stage in STAGES:
            stage_start = perf_counter()
            item = stage(ctx)
            item.update(timestamp_utc=datetime.now(timezone.utc).isoformat(),
                        duration_ms=round((perf_counter() - stage_start) * 1000, 3),
                        confidence=ctx['confidence'])
            audit.append(item)
    except (EvidenceError, OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError) as error:
        failure = f'Processing blocked by unavailable or invalid evidence/configuration: {error}'
        for name in STAGE_NAMES[len(audit):]:
            audit.append(finding(name, 'Human Review' if name == 'Decision & Routing' else 'blocked', failure, [],
                                 timestamp_utc=datetime.now(timezone.utc).isoformat(), duration_ms=0, confidence=0.0))
    route = 'Human Review' if failure else ctx['route']
    reasons = [failure] if failure else ctx['reasons']
    access = store.access_log if store else []
    return {
        'run_id': str(uuid4()), 'engine_version': 'deterministic-v1', 'simulation': True,
        'claim_id': claim_id, 'as_of_date': as_of.isoformat(), 'started_at_utc': timestamp,
        'processing_status': 'blocked' if failure else 'completed',
        'route': route, 'reasons': reasons,
        'escalation_reason': '; '.join(reasons) if route in {'Human Review', 'Investigation', 'Pending Documents'} else None,
        'policy_validation': ctx['policy_status'] if ctx and not failure else 'unresolved',
        'coverage_status': ctx['coverage_status'] if ctx and not failure else 'unresolved',
        'document_completeness': bool(ctx and not failure and ctx['evidence_complete']),
        'missing_documents': ctx['missing'] if ctx else [],
        'risk_score': ctx['risk'] if ctx and not failure else None,
        'estimated_settlement_inr': ctx['estimate'] if ctx and not failure else None,
        'confidence': ctx['confidence'] if ctx and not failure else 0.0,
        'confidence_method': 'Binary synthetic-evidence sufficiency; not model probability or real-world authenticity',
        'processing_time_ms': round((perf_counter() - started) * 1000, 3),
        'external_sources_accessed': sum(event['external'] and event['status'] == 'read' for event in access),
        'external_access_scope': 'Engine tool activity only; not operating-system network monitoring',
        'agent_audit_trail': audit, 'source_access_log': access,
    }


def save_report(report, root=ROOT):
    folder = Path(root) / 'runtime' / 'runs'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{report['run_id']}.json"
    with target.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    return target

"""Local browser API for registered synthetic claims."""

import json
from collections import Counter
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse

from backend.engine import ROOT, process_claim, save_report
from backend.evidence import EvidenceError, EvidenceStore, index_records
from backend.submissions import ClaimInput, ProcessInput, Submissions

ROUTES = ['STP Approved', 'Human Review', 'Investigation', 'Rejected', 'Pending Documents']


def create_app(root=ROOT):
    root = Path(root)
    submissions = Submissions(root)
    app = FastAPI(title='InsureFlow · AegisSure Insurance', version='0.1.0',
                  description='Local synthetic claims demo. Deterministic rules; no LLM or real payments.')

    @app.exception_handler(EvidenceError)
    async def evidence_error(request, error):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content={'detail': str(error)})

    def catalog():
        store = EvidenceStore(root)
        return list(index_records(store.records('data/demo_claims/claims.json'), 'claim_id').values()) + submissions.all()

    def require_claim(claim_id):
        claim = next((c for c in catalog() if c['claim_id'] == claim_id), None)
        if claim is None:
            raise HTTPException(404, 'Registered synthetic claim not found')
        return claim

    def reports():
        result, unreadable = [], 0
        for path in (root / 'runtime' / 'runs').glob('*.json'):
            try:
                report = json.loads(path.read_text(encoding='utf-8'))
                if (report['route'] not in ROUTES or not isinstance(report['claim_id'], str)
                        or not isinstance(report['processing_time_ms'], (int, float))
                        or not isinstance(report['agent_audit_trail'], list)):
                    raise ValueError('Invalid report')
                for key in ('run_id', 'started_at_utc', 'risk_score', 'estimated_settlement_inr',
                            'external_sources_accessed', 'confidence', 'processing_status'):
                    report[key]
                result.append(report)
            except (OSError, ValueError, KeyError, TypeError):
                unreadable += 1
        return sorted(result, key=lambda r: r['started_at_utc'], reverse=True), unreadable

    @app.get('/', include_in_schema=False)
    def home():
        return RedirectResponse('/docs')

    @app.get('/health')
    def health():
        return {'status': 'ok', 'mode': 'synthetic-local-demo', 'engine_version': 'deterministic-v1'}

    @app.get('/claims')
    def claims():
        return catalog()

    @app.get('/policies')
    def policies():
        return submissions.policies()

    @app.post('/submissions', status_code=201)
    def create_submission(payload: ClaimInput):
        try:
            return submissions.create(payload)
        except ValueError as error:
            if isinstance(error, EvidenceError):
                raise
            raise HTTPException(422, str(error)) from error

    @app.get('/submissions/{claim_id}')
    def submission_detail(claim_id: str):
        result = submissions.get(claim_id)
        if result is None:
            raise HTTPException(404, 'Submission not found')
        return result | {'templates': submissions.templates(result['claim'])}

    @app.post('/submissions/{claim_id}/process')
    def process_submission(claim_id: str, payload: ProcessInput):
        if submissions.get(claim_id) is None:
            raise HTTPException(404, 'Submission not found')
        try:
            return submissions.process(claim_id, [d.model_dump() for d in payload.documents], payload.evidence_mode)
        except ValueError as error:
            if isinstance(error, EvidenceError):
                raise
            raise HTTPException(422, str(error)) from error

    @app.get('/claims/{claim_id}')
    def claim_detail(claim_id: str):
        claim = require_claim(claim_id)
        store = EvidenceStore(root)
        policies = index_records(store.records('data/policies/policies.json'), 'policy_id')
        rules = index_records(store.records('data/rules/policy_rules.json'), 'rule_id')
        policy = policies.get(claim['policy_id'])
        stored = submissions.get(claim_id)
        if stored:
            return {'claim': claim, 'policy': policy, 'rule': rules.get(policy['rule_id']) if policy else None,
                    'documents': stored['documents'], 'result': stored['result']}
        documents = [dict(d) for d in store.documents() if d['claim_id'] == claim_id]
        for document in documents:
            try:
                document['text'] = store.text(document['path'], 'untrusted_claim_evidence')
            except EvidenceError as error:
                document['error'] = str(error)
        return {'claim': claim, 'policy': policy, 'rule': rules.get(policy['rule_id']) if policy else None,
                'documents': documents}

    @app.post('/claims/process-all')
    def process_all():
        results = []
        for claim in catalog():
            if claim['claim_id'].startswith('CLM-NEW-'):
                continue
            result = process_claim(claim['claim_id'], root)
            save_report(result, root)
            results.append(result)
        return results

    @app.post('/claims/{claim_id}/process')
    def process_one(claim_id: str):
        require_claim(claim_id)
        if submissions.get(claim_id):
            return submissions.process(claim_id)
        result = process_claim(claim_id, root)
        save_report(result, root)
        return result

    @app.get('/runs/{run_id}')
    def run_detail(run_id: str):
        try:
            UUID(run_id)
        except ValueError:
            raise HTTPException(404, 'Run not found')
        available, _ = reports()
        result = next((r for r in available if r['run_id'] == run_id), None)
        if result is None:
            raise HTTPException(404, 'Run not found')
        return result

    @app.get('/dashboard')
    def dashboard():
        known = {claim['claim_id']: claim for claim in catalog()}
        available, unreadable = reports()
        latest = {}
        for report in available:
            if report['claim_id'] in known:
                latest.setdefault(report['claim_id'], report)
        rows = []
        for claim_id, report in latest.items():
            claim = known[claim_id]
            rows.append({key: report[key] for key in (
                'claim_id', 'run_id', 'route', 'risk_score', 'confidence', 'estimated_settlement_inr',
                'processing_time_ms', 'started_at_utc', 'processing_status')} | {
                    'insurance_line': claim['insurance_line'], 'claimed_amount_inr': claim['claimed_amount_inr']})
        total = len(rows)
        counts = Counter(row['route'] for row in rows)
        estimates = [row['estimated_settlement_inr'] for row in rows if row['estimated_settlement_inr'] is not None]
        awaiting = [claim | {'route': 'Awaiting submission', 'origin': 'Customer Portal'} for claim in known.values()
                    if claim['claim_id'].startswith('CLM-NEW-') and claim['claim_id'] not in latest]
        return {
            'awaiting_submission': awaiting,
            'registered_claims': len(known), 'processed_claims': total, 'total_runs': len(available),
            'route_counts': {route: counts[route] for route in ROUTES},
            'route_percentages': {route: round(counts[route] / total * 100, 1) if total else 0 for route in ROUTES},
            'average_processing_ms': round(sum(row['processing_time_ms'] for row in rows) / total, 2) if total else 0,
            'total_estimated_settlement_inr': sum(estimates),
            'average_estimated_settlement_inr': round(sum(estimates) / len(estimates), 2) if estimates else 0,
            'estimate_count': len(estimates), 'claims': rows,
            'external_sources_accessed': sum(r['external_sources_accessed'] for r in available),
            'blocked_runs': sum(r['processing_status'] == 'blocked' for r in available),
            'unreadable_reports': unreadable,
            'agent_activity': [stage | {'claim_id': claim_id} for claim_id, r in latest.items() for stage in r['agent_audit_trail']],
        }

    @app.get('/knowledge-base')
    def knowledge_base():
        store = EvidenceStore(root)
        sources = []
        for path, source in store.sources.items():
            try:
                store.text(path, source['approved_for'])
                status = 'Integrity checked'
            except EvidenceError:
                status = 'Blocked: unavailable or changed'
            sources.append({'path': path, 'scope': source['approved_for'], 'status': status})
        return {'sources': sources, 'rules': store.records('data/rules/policy_rules.json'),
                'history': store.records('data/historical_claims/claims.json'),
                'models': {'status': 'Not integrated', 'baseline': 'deterministic-v1', 'benchmark_run': False}}

    return app


app = create_app()

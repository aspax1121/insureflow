"""Seven explicit stages. Document verification is synthetic-template consistency only."""

from datetime import date
import hashlib

from backend.evidence import EvidenceError

CLAIMS = 'data/demo_claims/claims.json'
POLICIES = 'data/policies/policies.json'
RULES = 'data/rules/policy_rules.json'
HISTORY = 'data/historical_claims/claims.json'
ROUTING = 'data/rules/routing_rules.json'
INDICATORS = 'data/rules/anomaly_indicators.json'


def ref(source, record, clause):
    return {'source': source, 'record_id': record, 'clause': clause}


def finding(stage, status, reason, evidence, **details):
    return {'stage': stage, 'status': status, 'reason': reason, 'evidence': evidence, **details}


def intake(ctx):
    claim = ctx['claim']
    required = ('claim_id', 'policy_id', 'customer_id', 'insurance_line', 'incident_id',
                'incident_date', 'submitted_date', 'event_type', 'claimed_amount_inr', 'currency')
    invalid = [field for field in required if field not in claim or claim[field] in (None, '')]
    amount = claim.get('claimed_amount_inr')
    if type(amount) is not int or amount <= 0:
        invalid.append('claimed_amount_inr')
    if claim.get('currency') != 'INR':
        invalid.append('currency')
    try:
        incident = date.fromisoformat(claim['incident_date'])
        submitted = date.fromisoformat(claim['submitted_date'])
        if not incident <= submitted <= ctx['as_of']:
            invalid.append('claim chronology')
    except (KeyError, ValueError, TypeError):
        invalid.append('claim dates')
    ctx['invalid'] = invalid
    if invalid:
        ctx['review'].append('Invalid or incomplete claim fields: ' + ', '.join(sorted(set(invalid))))
        ctx['confidence'] = 0.0
    policy = ctx['policies'].get(claim.get('policy_id'))
    ctx['policy'] = policy
    ctx['rule'] = ctx['rules'].get(policy.get('rule_id')) if policy else None
    rule = ctx['rule']
    documents = [d for d in ctx['documents'].values() if d['claim_id'] == claim['claim_id']]
    ctx['claim_documents'] = documents
    expected = rule['required_documents'] if rule else []
    ctx['missing'] = sorted(set(expected) - {d['document_type'] for d in documents})
    if ctx['missing']:
        ctx['confidence'] = 0.0
    return finding('Claim Intake', 'needs_attention' if invalid or ctx['missing'] else 'complete',
                   'Submission fields and required document presence checked.',
                   [ref(CLAIMS, claim['claim_id'], 'INTAKE-01'), ref('data/claim_documents/documents.json', claim['claim_id'], rule['document_clause'] if rule else 'INTAKE-01')],
                   missing_documents=ctx['missing'], invalid_fields=invalid)


def policy_validation(ctx):
    claim, policy = ctx['claim'], ctx['policy']
    evidence = [ref(CLAIMS, claim['claim_id'], 'POL-VALID-01')]
    if policy:
        evidence.append(ref(POLICIES, policy['policy_id'], 'start_date/end_date/premium_paid/customer_id'))
    ctx['policy_status'] = 'unresolved'
    if not policy or not ctx['rule']:
        ctx['review'].append('Policy or its approved rule set could not be resolved')
        ctx['confidence'] = 0.0
    elif policy['customer_id'] != claim.get('customer_id') or policy['customer_id'] not in ctx['customers'] or policy['insurance_line'] != claim.get('insurance_line'):
        ctx['review'].append('Policy ownership or insurance line mismatch')
        ctx['confidence'] = 0.0
    elif not ctx['invalid']:
        evidence.append(ref('data/customers/customers.json', policy['customer_id'], 'customer_id'))
        if not date.fromisoformat(policy['start_date']) <= date.fromisoformat(claim['incident_date']) <= date.fromisoformat(policy['end_date']):
            ctx['rejections'].append('Incident occurred outside the policy coverage dates')
        if policy['premium_paid'] is False:
            ctx['rejections'].append('Policy record explicitly shows unpaid premium')
        elif policy['premium_paid'] is not True:
            ctx['review'].append('Premium status is unknown')
            ctx['confidence'] = 0.0
        ctx['policy_status'] = 'invalid' if ctx['rejections'] else ('valid' if not ctx['review'] else 'unresolved')
    return finding('Policy Validation', ctx['policy_status'],
                   '; '.join(ctx['rejections'] + ctx['review']) or 'Ownership, premium and incident-date coverage verified.', evidence)


def parse_document(text):
    lines = text.splitlines()
    if not lines or lines[0] != 'SYNTHETIC ACADEMIC DOCUMENT — NOT A REAL INSURANCE RECORD':
        raise EvidenceError('Unsupported document template')
    allowed = {'Document', 'Type', 'Claim', 'Policy', 'Incident date', 'Event', 'Claimed amount INR', 'Supported expense INR'}
    values = {}
    for line in lines[1:]:
        key, separator, value = line.partition(': ')
        if not separator or key not in allowed or key in values:
            raise EvidenceError('Unexpected or repeated document field')
        values[key] = value
    return values


def coverage(ctx):
    claim, rule = ctx['claim'], ctx['rule']
    evidence = [ref(CLAIMS, claim['claim_id'], 'EVIDENCE-01')]
    ctx['coverage_status'] = 'unresolved'
    ctx['verified_documents'] = []
    ctx['expenses'] = []
    ctx['date_conflict'] = False
    if not rule:
        return finding('Coverage', 'unresolved', 'No approved policy rule available.', evidence)
    evidence.append(ref(RULES, rule['rule_id'], rule['coverage_clause']))
    event = claim.get('event_type')
    if event in rule['excluded_events']:
        ctx['coverage_status'] = 'excluded'
        ctx['rejections'].append('Event is explicitly excluded: ' + event)
        evidence.append(ref(RULES, rule['rule_id'], rule['exclusion_clause']))
    elif event in rule['covered_events']:
        ctx['coverage_status'] = 'covered'
    else:
        ctx['review'].append('Event is not resolved by an explicit coverage or exclusion rule')
        ctx['confidence'] = 0.0
    document_types = [d['document_type'] for d in ctx['claim_documents']]
    if len(set(document_types)) != len(document_types):
        ctx['review'].append('Multiple documents of the same type need reconciliation')
        ctx['confidence'] = 0.0
    for document in ctx['claim_documents']:
        evidence.append(ref(document['path'], document['document_id'], rule['document_clause']))
        try:
            text = ctx['store'].text(document['path'], 'untrusted_claim_evidence')
            if hashlib.sha256(text.encode()).hexdigest() != document['sha256']:
                raise EvidenceError('Document metadata hash mismatch')
            values = parse_document(text)
            expected = {'Document': document['document_id'], 'Type': document['document_type'],
                        'Claim': claim['claim_id'], 'Policy': claim.get('policy_id'),
                        'Incident date': claim.get('incident_date'), 'Event': event,
                        'Claimed amount INR': str(claim.get('claimed_amount_inr'))}
            if values.get('Incident date') and values['Incident date'] != claim.get('incident_date'):
                ctx['date_conflict'] = True
            if any(values.get(key) != value for key, value in expected.items()):
                raise EvidenceError('Document fields conflict with or fail to support the submission')
            if document['document_type'] not in rule['required_documents']:
                raise EvidenceError('Unexpected document type')
            if rule['settlement_mode'] == 'reimbursement' and document['document_type'] != 'claim_form':
                expense = int(values['Supported expense INR'])
                if expense <= 0:
                    raise EvidenceError('Supported expense must be positive')
                ctx['expenses'].append(expense)
            ctx['verified_documents'].append(document['document_id'])
        except (EvidenceError, ValueError, KeyError, TypeError) as error:
            ctx['review'].append(f"Document {document['document_id']} needs review: {error}")
            ctx['confidence'] = 0.0
    ctx['evidence_complete'] = (not ctx['missing'] and not ctx['invalid'] and
                               len(ctx['verified_documents']) == len(ctx['claim_documents']) and bool(ctx['claim_documents']))
    return finding('Coverage', ctx['coverage_status'], 'Coverage clauses and synthetic document consistency checked.', evidence,
                   document_completeness=ctx['evidence_complete'], verified_document_ids=ctx['verified_documents'])


def historical_claims(ctx):
    claim = ctx['claim']
    rows = []
    if not ctx['invalid']:
        rows = [row for row in ctx['history'].values() if row['policy_id'] == claim['policy_id'] and
                date.fromisoformat(row['submitted_date']) <= date.fromisoformat(claim['submitted_date'])]
    ctx['duplicates'] = [r for r in rows if r['incident_id'] == claim.get('incident_id')]
    ctx['recent'] = [r for r in rows if 0 <= (date.fromisoformat(claim['submitted_date']) - date.fromisoformat(r['submitted_date'])).days <= 90]
    return finding('Historical Claims', 'checked', f'{len(rows)} earlier claims on this policy.',
                   [ref(HISTORY, row['claim_id'], 'HISTORY-01') for row in rows] or [ref(HISTORY, 'dataset', 'HISTORY-01')],
                   duplicate_claim_ids=[r['claim_id'] for r in ctx['duplicates']], recent_claim_count=len(ctx['recent']))


def anomaly_detection(ctx):
    signals = []
    if ctx['duplicates']:
        signals.append('RISK-DUP-01')
    if len(ctx['recent']) >= 3:
        signals.append('RISK-FREQ-01')
    if ctx['date_conflict']:
        signals.append('RISK-CONFLICT-01')
    ctx['risk'] = min(100, sum(ctx['indicators'][key]['points'] for key in signals))
    evidence = [ref(INDICATORS, key, key) for key in signals]
    evidence += [ref(HISTORY, r['claim_id'], 'RISK-DUP-01') for r in ctx['duplicates']]
    if 'RISK-FREQ-01' in signals:
        evidence += [ref(HISTORY, r['claim_id'], 'RISK-FREQ-01') for r in ctx['recent']]
    if ctx['date_conflict']:
        evidence += [ref(d['path'], d['document_id'], 'RISK-CONFLICT-01') for d in ctx['claim_documents']]
    return finding('Fraud/Anomaly Detection', 'indicators_found' if signals else 'no_indicators',
                   'Risk indicators support routing; they do not establish fraud.',
                   evidence or [ref(INDICATORS, 'dataset', 'RISK-01')], risk_score=ctx['risk'], indicators=signals)


def settlement(ctx):
    rule, claim = ctx['rule'], ctx['claim']
    evidence = []
    ctx['estimate'] = None
    if rule:
        evidence.append(ref(RULES, rule['rule_id'], rule['settlement_clause']))
    if rule and ctx['policy_status'] == 'valid' and ctx['coverage_status'] == 'covered' and ctx['evidence_complete'] and ctx['confidence'] == 1.0:
        amount = claim['claimed_amount_inr']
        if rule['settlement_mode'] == 'fixed_benefit':
            if amount != rule['fixed_benefit_inr']:
                ctx['review'].append('Claimed amount differs from fixed benefit')
            else:
                ctx['estimate'] = rule['fixed_benefit_inr']
        elif ctx['expenses']:
            ctx['estimate'] = max(0, min(amount, min(ctx['expenses']), rule['per_claim_limit_inr']) - rule['deductible_inr'])
        if ctx['estimate'] == 0:
            ctx['review'].append('Zero payable estimate requires human review')
        evidence += [ref(d['path'], d['document_id'], rule['settlement_clause']) for d in ctx['claim_documents']]
    return finding('Settlement', 'estimated' if ctx['estimate'] is not None else 'withheld',
                   'Evidence-supported simulation; no payment is made.' if ctx['estimate'] is not None else 'No settlement estimate without sufficient verified evidence and applicable coverage.',
                   evidence, estimated_settlement_inr=ctx['estimate'])


def decision_routing(ctx):
    rule, routing = ctx['rule'], ctx['routing']
    if rule:
        if rule['mandatory_human_review']:
            ctx['review'].append('Policy rule requires human review')
        if not ctx['invalid'] and ctx['claim']['claimed_amount_inr'] > rule['stp_claim_ceiling_inr']:
            ctx['review'].append('Claimed amount exceeds the STP ceiling')
    if ctx['risk'] > routing['stp_risk_max']:
        ctx['review'].append('Risk exceeds the STP threshold')
    if ctx['confidence'] < routing['minimum_evidence_confidence']:
        ctx['review'].append('Evidence confidence is below the decision threshold')
    if ctx['risk'] >= routing['investigation_risk_min']:
        route, reasons = 'Investigation', ['Supported anomaly indicators meet the investigation threshold']
    elif ctx['missing']:
        route, reasons = 'Pending Documents', ['Missing required documents: ' + ', '.join(ctx['missing'])]
    elif ctx['review']:
        route, reasons = 'Human Review', ctx['review']
    elif ctx['rejections']:
        route, reasons = 'Rejected', ctx['rejections']
    elif ctx['evidence_complete'] and ctx['estimate'] is not None and ctx['policy_status'] == 'valid' and ctx['coverage_status'] == 'covered':
        route, reasons = 'STP Approved', ['All policy, coverage, evidence, value and risk gates passed']
    else:
        route, reasons = 'Human Review', ['Insufficient evidence for a final decision']
    ctx['route'] = route
    ctx['reasons'] = list(dict.fromkeys(reasons))
    evidence = [ref(ROUTING, routing['rule_id'], 'ROUTE-01')]
    if rule:
        evidence.append(ref(RULES, rule['rule_id'], rule['stp_clause']))
    # Carry supporting record references into the final routing finding.
    for stage in ctx['audit']:
        for item in stage['evidence']:
            if item not in evidence:
                evidence.append(item)
    return finding('Decision & Routing', route, '; '.join(ctx['reasons']), evidence,
                   escalation_reason='; '.join(ctx['reasons']) if route in {'Human Review', 'Investigation', 'Pending Documents'} else None)


STAGES = [intake, policy_validation, coverage, historical_claims, anomaly_detection, settlement, decision_routing]
STAGE_NAMES = ['Claim Intake', 'Policy Validation', 'Coverage', 'Historical Claims', 'Fraud/Anomaly Detection', 'Settlement', 'Decision & Routing']

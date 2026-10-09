"""Persist synthetic submissions and build isolated, authorized engine inputs."""

from contextlib import closing
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from backend.engine import process_claim, save_report
from backend.evidence import EvidenceError, EvidenceStore, index_records

DEMO_DATE = date(2026, 10, 1)


class ClaimInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    policy_id: str = Field(pattern=r'^POL-[A-Z]{3}-\d{6}$')
    insurance_line: str = Field(min_length=1, max_length=40)
    incident_id: str = Field(pattern=r'^INC-[A-Za-z0-9-]{1,60}$')
    incident_date: date
    event_type: str = Field(pattern=r'^[a-z_]{1,60}$')
    claimed_amount_inr: int = Field(strict=True, gt=0, le=100000000)
    synthetic_confirmed: Literal[True]


class DocumentInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    document_type: str = Field(pattern=r'^[a-z_]{1,50}$')
    text: str = Field(min_length=1, max_length=16000)


class ProcessInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    documents: list[DocumentInput] = Field(max_length=5)
    synthetic_confirmed: Literal[True]
    evidence_mode: Literal['uploaded', 'generated_demo', 'none'] = 'uploaded'


class Submissions:
    def __init__(self, root):
        self.root = Path(root)
        self.path = self.root / 'runtime' / 'submissions.sqlite3'

    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute('''CREATE TABLE IF NOT EXISTS submissions (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT UNIQUE NOT NULL,
            claim TEXT NOT NULL,
            documents TEXT NOT NULL DEFAULT '[]',
            result TEXT,
            created_at TEXT NOT NULL
        )''')
        connection.commit()
        return connection

    def policies(self):
        store = EvidenceStore(self.root)
        policies = store.records('data/policies/policies.json')
        rules = index_records(store.records('data/rules/policy_rules.json'), 'rule_id')
        return [p | {'rule': rules[p['rule_id']]} for p in policies]

    def all(self):
        if not self.path.exists():
            return []
        with closing(self.connect()) as conn:
            return [json.loads(row['claim']) for row in conn.execute('SELECT claim FROM submissions ORDER BY sequence')]

    def get(self, claim_id):
        if not claim_id.startswith('CLM-NEW-') or not 6 <= len(claim_id[8:]) <= 12 or not claim_id[8:].isdigit() or not self.path.exists():
            return None
        with closing(self.connect()) as conn:
            row = conn.execute('SELECT * FROM submissions WHERE sequence=?', (int(claim_id[8:]),)).fetchone()
            if row is None or json.loads(row['claim'])['claim_id'] != claim_id:
                return None
            return {'claim': json.loads(row['claim']), 'documents': json.loads(row['documents']),
                    'result': json.loads(row['result']) if row['result'] else None}

    def create(self, payload):
        policies = {p['policy_id']: p for p in self.policies()}
        policy = policies.get(payload.policy_id)
        if not policy or policy['insurance_line'] != payload.insurance_line:
            raise ValueError('Select a registered synthetic policy matching the insurance line')
        if payload.incident_date > DEMO_DATE:
            raise ValueError('Incident date must be on or before the fixed demo date: 2026-10-01')
        with closing(self.connect()) as conn, conn:
            conn.execute('BEGIN IMMEDIATE')
            existing = conn.execute('SELECT claim FROM submissions WHERE request_id=?', (str(payload.request_id),)).fetchone()
            if existing:
                claim = json.loads(existing['claim'])
                submitted = payload.model_dump(mode='json')
                if any(claim[key] != submitted[key] for key in ('policy_id', 'insurance_line', 'incident_id', 'incident_date', 'event_type', 'claimed_amount_inr')):
                    raise ValueError('Request ID already belongs to a different submission')
                return claim
            cursor = conn.execute('INSERT INTO submissions(request_id, claim, created_at) VALUES (?, ?, ?)',
                                  (str(payload.request_id), '{}', datetime.now(timezone.utc).isoformat()))
            claim = payload.model_dump(mode='json', exclude={'request_id', 'synthetic_confirmed'})
            claim.update(claim_id=f'CLM-NEW-{cursor.lastrowid:06d}', customer_id=policy['customer_id'],
                         submitted_date=DEMO_DATE.isoformat(), currency='INR', synthetic=True)
            conn.execute('UPDATE submissions SET claim=? WHERE sequence=?', (json.dumps(claim), cursor.lastrowid))
            return claim

    def templates(self, claim):
        policy = next(p for p in self.policies() if p['policy_id'] == claim['policy_id'])
        rule = policy['rule']
        templates = []
        for position, kind in enumerate(rule['required_documents'], 1):
            doc_id = f"DOC-{claim['claim_id']}-{position:02d}"
            text = ('SYNTHETIC ACADEMIC DOCUMENT — NOT A REAL INSURANCE RECORD\n'
                    f"Document: {doc_id}\nType: {kind}\nClaim: {claim['claim_id']}\n"
                    f"Policy: {claim['policy_id']}\nIncident date: {claim['incident_date']}\n"
                    f"Event: {claim['event_type']}\nClaimed amount INR: {claim['claimed_amount_inr']}\n")
            if rule['settlement_mode'] == 'reimbursement' and kind != 'claim_form':
                text += f"Supported expense INR: {claim['claimed_amount_inr']}\n"
            templates.append({'document_type': kind, 'document_id': doc_id, 'text': text})
        return templates

    def process(self, claim_id, documents=None, evidence_mode='uploaded'):
        stored = self.get(claim_id)
        if stored is None:
            raise ValueError('Submission not found')
        supplied = documents if documents is not None else stored['documents']
        if documents is None and stored['result']:
            evidence_mode = stored['result'].get('evidence_mode', 'uploaded')
        expected = {d['document_type']: d['document_id'] for d in self.templates(stored['claim'])}
        if len({d['document_type'] for d in supplied}) != len(supplied):
            raise ValueError('Only one document per required type is allowed')
        for document in supplied:
            if document['document_type'] not in expected:
                raise ValueError('Unsupported document type for this policy')
            if len(document['text'].encode('utf-8')) > 16000 or '\x00' in document['text']:
                raise ValueError('Documents must be plain UTF-8 text, at most 16 KB each')
        # Serialize processing with SQLite so earlier submissions are visible to later risk checks.
        with closing(self.connect()) as conn, conn:
            conn.execute('BEGIN IMMEDIATE')
            prior = [json.loads(row['claim']) for row in conn.execute('SELECT claim FROM submissions WHERE result IS NOT NULL')
                     if json.loads(row['claim'])['claim_id'] != claim_id]
            snapshot = self.snapshot(stored['claim'], supplied, expected, prior)
            report = process_claim(claim_id, snapshot)
            report['evidence_root'] = str(snapshot.relative_to(self.root))
            report['submission_origin'] = 'Customer Portal'
            report['evidence_mode'] = evidence_mode
            save_report(report, self.root)
            conn.execute('UPDATE submissions SET documents=?, result=? WHERE sequence=?',
                         (json.dumps(supplied), json.dumps(report), int(claim_id[8:])))
            return report

    def snapshot(self, claim, documents, expected, prior):
        """Copy only hash-checked sources; register raw uploads as untrusted evidence."""
        store = EvidenceStore(self.root)
        files = {path: (store.text(path, source['approved_for']), source['approved_for'])
                 for path, source in store.sources.items()}
        metadata = []
        for document in documents:
            doc_id = expected[document['document_type']]
            path = f'data/claim_documents/text/{doc_id}.txt'
            files[path] = (document['text'], 'untrusted_claim_evidence')
            metadata.append({'document_id': doc_id, 'claim_id': claim['claim_id'],
                             'document_type': document['document_type'], 'path': path,
                             'sha256': hashlib.sha256(document['text'].encode()).hexdigest(),
                             'verification_status': 'unverified', 'synthetic': True})
        def replace(path, rows):
            payload = json.loads(files[path][0])
            payload['records'] = rows
            files[path] = (json.dumps(payload, indent=2), files[path][1])
        replace('data/demo_claims/claims.json', [claim])
        replace('data/claim_documents/documents.json', metadata)
        historic = json.loads(files['data/historical_claims/claims.json'][0])['records']
        replace('data/historical_claims/claims.json', historic + prior)
        snapshot = self.root / 'runtime' / 'evidence' / str(uuid4())
        snapshot.mkdir(parents=True, exist_ok=False)
        sources = []
        for index, (relative, (text, scope)) in enumerate(files.items(), 1):
            target = snapshot / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(text.encode('utf-8'))
            sources.append({'source_id': f'SUB-SRC-{index:03d}', 'path': relative,
                            'sha256': hashlib.sha256(text.encode()).hexdigest(), 'approved_for': scope})
        manifest = snapshot / 'knowledge_base/source_manifest.json'
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({'manifest_version': 1, 'sources': sources,
            'approval_scope': 'Application-validated synthetic submission; uploads are untrusted, not authenticated'}), encoding='utf-8')
        return snapshot

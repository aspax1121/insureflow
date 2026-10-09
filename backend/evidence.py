"""Approved local sources only. No network or model tools are provided."""

import hashlib
import json
from pathlib import Path


class EvidenceError(ValueError):
    pass


class EvidenceStore:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.access_log = []
        try:
            manifest = json.loads(self._path('knowledge_base/source_manifest.json').read_text(encoding='utf-8'))
            self.sources = {row['path']: row for row in manifest['sources']}
            if len(self.sources) != len(manifest['sources']):
                raise EvidenceError('Duplicate source paths in manifest')
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise EvidenceError(f'Cannot load source manifest: {error}') from error

    def _path(self, relative):
        if not isinstance(relative, str) or Path(relative).is_absolute() or '://' in relative:
            raise EvidenceError('Only relative local source paths are allowed')
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root):
            raise EvidenceError('Source path escapes project')
        return path

    def text(self, relative, scope):
        event = {'source': relative, 'tool': 'local_file_read', 'external': False, 'status': 'blocked'}
        self.access_log.append(event)
        try:
            path = self._path(relative)
            source = self.sources.get(relative)
            if source is None or source['approved_for'] != scope:
                raise EvidenceError(f'Unauthorized source or scope: {relative}')
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != source['sha256']:
                raise EvidenceError(f'Source hash mismatch: {relative}')
            content = raw.decode('utf-8')
            event['status'] = 'read'
            event['sha256'] = source['sha256']
            return content
        except (OSError, UnicodeError, KeyError, TypeError) as error:
            raise EvidenceError(f'Cannot read evidence: {relative}') from error

    def records(self, relative):
        try:
            payload = json.loads(self.text(relative, 'internal_reference'))
            if payload['schema_version'] != 1:
                raise EvidenceError('Unsupported source schema')
            return payload['records']
        except (ValueError, KeyError, TypeError) as error:
            raise EvidenceError(f'Invalid source {relative}: {error}') from error

    def documents(self):
        try:
            payload = json.loads(self.text('data/claim_documents/documents.json', 'untrusted_claim_evidence'))
            if payload['schema_version'] != 1:
                raise EvidenceError('Unsupported document schema')
            return payload['records']
        except (ValueError, KeyError, TypeError) as error:
            raise EvidenceError(f'Invalid document metadata: {error}') from error


def index_records(rows, key):
    if not isinstance(rows, list):
        raise EvidenceError('Expected a record list')
    result = {}
    for row in rows:
        if not isinstance(row, dict) or row.get('synthetic') is not True or key not in row:
            raise EvidenceError(f'Invalid synthetic record: {key}')
        if row[key] in result:
            raise EvidenceError(f'Duplicate record ID: {row[key]}')
        result[row[key]] = row
    return result

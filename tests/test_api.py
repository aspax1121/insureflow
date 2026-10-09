import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.api import create_app
from scripts.generate_synthetic_data import generate


class ApiTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        generate(self.root)
        self.client = TestClient(create_app(self.root))
        self.addCleanup(self.client.close)

    def test_catalog_documents_and_health(self):
        self.assertEqual(self.client.get('/health').status_code, 200)
        self.assertEqual(len(self.client.get('/claims').json()), 7)
        detail = self.client.get('/claims/CLM-000001').json()
        self.assertEqual(len(detail['documents']), 2)
        self.assertIn('SYNTHETIC', detail['documents'][0]['text'])
        self.assertEqual(self.client.get('/claims/UNKNOWN').status_code, 404)

    def test_empty_dashboard(self):
        data = self.client.get('/dashboard').json()
        self.assertEqual(data['processed_claims'], 0)
        self.assertEqual(data['average_estimated_settlement_inr'], 0)

    def test_processing_and_deduplicated_metrics(self):
        for _ in range(2):
            report = self.client.post('/claims/CLM-000001/process').json()
        data = self.client.get('/dashboard').json()
        self.assertEqual(data['processed_claims'], 1)
        self.assertEqual(data['total_runs'], 2)
        self.assertEqual(data['total_estimated_settlement_inr'], 23000)
        self.assertEqual(data['route_percentages']['STP Approved'], 100)
        self.assertEqual(self.client.get('/runs/' + report['run_id']).json()['route'], 'STP Approved')

    def test_batch_and_knowledge_base(self):
        self.assertEqual(len(self.client.post('/claims/process-all').json()), 7)
        data = self.client.get('/dashboard').json()
        self.assertEqual(data['route_counts']['Human Review'], 1)
        self.assertEqual(data['route_counts']['STP Approved'], 6)
        self.assertEqual(len(data['agent_activity']), 49)
        kb = self.client.get('/knowledge-base').json()
        self.assertEqual(len(kb['sources']), 22)
        self.assertFalse(kb['models']['benchmark_run'])

    def test_invalid_claim_does_not_write_a_report(self):
        self.assertEqual(self.client.post('/claims/UNKNOWN/process').status_code, 404)
        self.assertFalse((self.root / 'runtime/runs').exists())

    def test_unreadable_report_is_reported(self):
        folder = self.root / 'runtime/runs'
        folder.mkdir(parents=True)
        (folder / 'broken.json').write_text('{')
        self.assertEqual(self.client.get('/dashboard').json()['unreadable_reports'], 1)

    def test_tampered_catalog_is_unavailable(self):
        (self.root / 'data/demo_claims/claims.json').write_text('[]')
        self.assertEqual(self.client.get('/claims').status_code, 503)


if __name__ == '__main__':
    unittest.main()

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.generate_synthetic_data import generate
from scripts.validate_data import validate


class SyntheticDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        generate(self.root)

    def test_baseline_and_repeat_generation(self):
        before = {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        generate(self.root)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        self.assertEqual(validate(self.root)["demo_claims"], 7)

    def test_changed_file_is_not_overwritten(self):
        path = self.root / 'data/customers/customers.json'
        path.write_text('manual changes')
        with self.assertRaisesRegex(ValueError, 'Refusing to overwrite'):
            generate(self.root)
        self.assertEqual(path.read_text(), 'manual changes')

    def test_tampered_document_is_detected(self):
        path = next((self.root / 'data/claim_documents/text').glob('*.txt'))
        path.write_text('altered evidence')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            validate(self.root)

    def test_broken_relationship_even_with_updated_hash(self):
        relative = 'data/policies/policies.json'
        path = self.root / relative
        data = json.loads(path.read_text())
        data['records'][0]['customer_id'] = 'CUST-UNKNOWN'
        path.write_text(json.dumps(data))
        manifest_path = self.root / 'knowledge_base/source_manifest.json'
        manifest = json.loads(manifest_path.read_text())
        for source in manifest['sources']:
            if source['path'] == relative:
                source['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'Unknown policy customer'):
            validate(self.root)

    def test_source_path_cannot_escape_project(self):
        path = self.root / 'knowledge_base/source_manifest.json'
        manifest = json.loads(path.read_text())
        manifest['sources'][0]['path'] = '../outside.txt'
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'escapes project'):
            validate(self.root)


if __name__ == '__main__':
    unittest.main()

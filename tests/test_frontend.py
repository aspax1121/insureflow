from pathlib import Path
from io import BytesIO
import json
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError

from streamlit.testing.v1 import AppTest
from fastapi.testclient import TestClient
from backend.api import create_app
from scripts.generate_synthetic_data import generate


class FrontendTests(unittest.TestCase):
    def test_customer_to_management_flow(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            generate(root)
            with TestClient(create_app(root)) as client:
                def request(req, timeout=30):
                    path = req.full_url.removeprefix('http://127.0.0.1:8000')
                    response = client.request(req.method, path, content=req.data, headers={'Content-Type': 'application/json'})
                    self.assertLess(response.status_code, 400, response.text)
                    return BytesIO(response.content)
                with patch('urllib.request.build_opener') as opener:
                    opener.return_value.open.side_effect = request
                    path = Path(__file__).resolve().parents[1] / 'frontend/app.py'
                    app = AppTest.from_file(str(path), default_timeout=30).run()
                    self.assertFalse(app.exception)
                    app.checkbox[0].check()
                    next(b for b in app.button if b.label == 'Save claim and continue to documents').click().run()
                    self.assertFalse(app.exception)
                    claim_id = app.session_state['active_submission']
                    next(r for r in app.radio if r.key and r.key.startswith('new-mode')).set_value('Submit without documents').run()
                    next(c for c in app.checkbox if c.key and c.key.startswith('new-confirm')).check().run()
                    next(b for b in app.button if b.key and b.key.startswith('new-process')).click().run()
                    self.assertFalse(app.exception)
                    self.assertEqual(client.get('/submissions/' + claim_id).json()['result']['route'], 'Pending Documents')
                    next(r for r in app.radio if r.key and r.key.startswith('new-mode')).set_value('Use generated demo documents').run()
                    next(b for b in app.button if b.key and b.key.startswith('new-process')).click().run()
                    self.assertFalse(app.exception)
                    self.assertEqual(client.get('/submissions/' + claim_id).json()['result']['route'], 'STP Approved')
                    next(r for r in app.radio if r.label == 'Portal').set_value('Management Portal').run()
                    self.assertFalse(app.exception)
                    self.assertTrue(any(claim_id in heading.value for heading in app.subheader))

    def test_backend_unavailable_shows_restart_command(self):
        path = Path(__file__).resolve().parents[1] / 'frontend/app.py'
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.side_effect = URLError('Backend is offline')
            app = AppTest.from_file(str(path), default_timeout=20).run()
        self.assertFalse(app.exception)
        self.assertIn('Backend unavailable', app.error[0].value)
        self.assertIn('uvicorn backend.api:app', app.code[0].value)


if __name__ == '__main__':
    unittest.main()

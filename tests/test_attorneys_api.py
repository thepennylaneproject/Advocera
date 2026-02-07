#!/usr/bin/env python3

import json
import threading
import time
import unittest
from http.client import HTTPConnection
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts import run_migrations, seed_attorneys
from apps.api import server
from http.server import HTTPServer


class AttorneysApiTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / 'test.db'

        run_migrations.apply_migrations(
            self.db_path,
            Path('/Users/sarahsahl/Desktop/advocera/db/migrations'),
        )

        conn = seed_attorneys.sqlite3.connect(self.db_path)
        conn.execute('PRAGMA foreign_keys = ON;')
        seed_data = json.loads(
            Path('/Users/sarahsahl/Desktop/advocera/seeds/attorneys.seed.json').read_text(
                encoding='utf-8'
            )
        )
        with conn:
            for record in seed_data:
                seed_attorneys.validate_attorney(record)
                seed_attorneys.insert_attorney(conn, record)
                seed_attorneys.insert_sources(conn, record['id'], record.get('source_evidence', []))
                seed_attorneys.insert_discipline(conn, record['id'], record.get('discipline_records', []))
        conn.close()

        server.DB_PATH = str(self.db_path)
        self.httpd = HTTPServer(('127.0.0.1', 0), server.Handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        time.sleep(0.05)

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=1)
        self.tempdir.cleanup()

    def request_json(self, path, method='GET', payload=None):
        conn = HTTPConnection('127.0.0.1', self.port, timeout=2)
        headers = {}
        body = None
        if payload is not None:
            body = json.dumps(payload)
            headers['Content-Type'] = 'application/json'
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        body = response.read().decode('utf-8')
        conn.close()
        return response.status, json.loads(body)

    def test_attorneys_list_success(self):
        status, body = self.request_json('/v1/attorneys?state=IA&limit=10&offset=0')
        self.assertEqual(status, 200)
        self.assertIn('data', body)
        self.assertIn('meta', body)
        self.assertEqual(body['meta']['limit'], 10)
        self.assertEqual(body['meta']['offset'], 0)
        self.assertGreaterEqual(body['meta']['total'], 2)

    def test_attorneys_list_practice_area_filter(self):
        status, body = self.request_json('/v1/attorneys?state=IA&practice_area=employment_law')
        self.assertEqual(status, 200)
        self.assertEqual(len(body['data']), 1)
        self.assertEqual(body['data'][0]['full_name'], 'Jordan Lee')

    def test_attorneys_list_validation_error(self):
        status, body = self.request_json('/v1/attorneys?state=CA&practice_area=tax&limit=0&offset=-1')
        self.assertEqual(status, 422)
        self.assertEqual(body['error'], 'validation_error')
        fields = {item['field'] for item in body['field_errors']}
        self.assertTrue({'state', 'practice_area', 'limit', 'offset'}.issubset(fields))

    def test_create_intake_and_generate_matches(self):
        intake_payload = {
            'state': 'IA',
            'practice_areas': ['personal_injury'],
            'zip_code': '50309',
            'city': 'Des Moines',
            'language_pref': 'Spanish',
            'urgency': 'high',
            'summary': 'I was injured in a crash and need help with insurance and medical bills.',
            'consent_at': '2026-02-07T12:00:00Z',
            'contact': {
                'full_name': 'Taylor Client',
                'email': 'taylor@example.com',
            },
        }
        status, intake = self.request_json('/v1/intakes', method='POST', payload=intake_payload)
        self.assertEqual(status, 201)
        self.assertEqual(intake['status'], 'new')

        status, body = self.request_json(f"/v1/intakes/{intake['id']}/matches")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(body['data']), 1)
        top = body['data'][0]
        self.assertIn('score', top)
        self.assertIn('reasons', top)
        self.assertTrue(any('Practice fit' in reason for reason in top['reasons']))

        status, drafts = self.request_json(f"/v1/intakes/{intake['id']}/drafts", method='POST', payload={})
        self.assertEqual(status, 201)
        self.assertGreaterEqual(len(drafts['data']), 1)
        self.assertEqual(drafts['data'][0]['status'], 'pending_review')
        self.assertIn('subject', drafts['data'][0])

    def test_generate_drafts_returns_409_when_not_matched(self):
        intake_payload = {
            'state': 'IA',
            'practice_areas': ['family_law'],
            'zip_code': '50309',
            'city': 'Des Moines',
            'urgency': 'medium',
            'summary': 'I need help with a family matter and want to understand next steps.',
            'consent_at': '2026-02-07T12:00:00Z',
        }
        status, intake = self.request_json('/v1/intakes', method='POST', payload=intake_payload)
        self.assertEqual(status, 201)

        status, body = self.request_json(f"/v1/intakes/{intake['id']}/drafts", method='POST', payload={})
        self.assertEqual(status, 409)
        self.assertEqual(body['error'], 'conflict')
        self.assertEqual(body['reason'], 'intake_not_matched')

    def test_review_task_queue_claim_and_decision(self):
        intake_payload = {
            'state': 'IA',
            'practice_areas': ['personal_injury'],
            'zip_code': '50309',
            'city': 'Des Moines',
            'urgency': 'high',
            'summary': 'I need help after an injury and need guidance on next steps quickly.',
            'consent_at': '2026-02-07T12:00:00Z',
        }
        status, intake = self.request_json('/v1/intakes', method='POST', payload=intake_payload)
        self.assertEqual(status, 201)

        status, _ = self.request_json(f"/v1/intakes/{intake['id']}/matches")
        self.assertEqual(status, 200)
        status, _ = self.request_json(f"/v1/intakes/{intake['id']}/drafts", method='POST', payload={})
        self.assertEqual(status, 201)

        status, queue = self.request_json('/v1/operator/review-tasks?status=pending')
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(queue['data']), 1)
        task = queue['data'][0]

        status, claimed = self.request_json(
            f"/v1/operator/review-tasks/{task['id']}/claim",
            method='POST',
            payload={'assignee_id': 'reviewer-1'},
        )
        self.assertEqual(status, 200)
        self.assertEqual(claimed['status'], 'in_review')
        self.assertEqual(claimed['assignee_id'], 'reviewer-1')

        status, decided = self.request_json(
            f"/v1/operator/review-tasks/{task['id']}/decision",
            method='POST',
            payload={
                'decision': 'approved',
                'notes': 'Looks good.',
                'updated_draft': {'subject': 'Reviewed subject'},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(decided['status'], 'approved')
        self.assertIsNotNone(decided['decided_at'])

    def test_review_task_list_validation_error(self):
        status, body = self.request_json('/v1/operator/review-tasks?status=unknown')
        self.assertEqual(status, 422)
        self.assertEqual(body['error'], 'validation_error')


if __name__ == '__main__':
    unittest.main()

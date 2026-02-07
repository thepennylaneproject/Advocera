#!/usr/bin/env python3
"""Minimal HTTP API for attorney listing."""

import json
import sqlite3
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

DB_PATH = 'data/advocera.db'
PRACTICE_AREAS = {'personal_injury', 'civil_rights', 'employment_law', 'family_law'}
ATTORNEY_STATUSES = {'active', 'inactive', 'suspended'}
MAX_LIMIT = 100


def _decode_json(text, fallback):
    if text in (None, ''):
        return fallback
    return json.loads(text)


def _first(params, key, default=None):
    return params.get(key, [default])[0]


def _validate_attorney_query(params):
    errors = []

    state = _first(params, 'state', 'IA')
    practice_area = _first(params, 'practice_area')
    city = _first(params, 'city')
    status = _first(params, 'status')
    limit_raw = _first(params, 'limit', '25')
    offset_raw = _first(params, 'offset', '0')

    if state != 'IA':
        errors.append({
            'field': 'state',
            'message': "Only 'IA' is currently supported in this prototype.",
        })

    if practice_area and practice_area not in PRACTICE_AREAS:
        errors.append({
            'field': 'practice_area',
            'message': f'Unsupported practice_area. Allowed: {sorted(PRACTICE_AREAS)}',
        })

    if status and status not in ATTORNEY_STATUSES:
        errors.append({
            'field': 'status',
            'message': f'Unsupported status. Allowed: {sorted(ATTORNEY_STATUSES)}',
        })

    try:
        limit = int(limit_raw)
        if limit < 1 or limit > MAX_LIMIT:
            raise ValueError()
    except (TypeError, ValueError):
        errors.append({
            'field': 'limit',
            'message': f'limit must be an integer between 1 and {MAX_LIMIT}.',
        })
        limit = 25

    try:
        offset = int(offset_raw)
        if offset < 0:
            raise ValueError()
    except (TypeError, ValueError):
        errors.append({
            'field': 'offset',
            'message': 'offset must be an integer greater than or equal to 0.',
        })
        offset = 0

    return errors, {
        'state': state,
        'practice_area': practice_area,
        'city': city,
        'status': status,
        'limit': limit,
        'offset': offset,
    }


class Handler(BaseHTTPRequestHandler):
    def _json(self, status, payload):
        body = json.dumps(payload).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == '/health':
            self._json(200, {'ok': True})
            return

        if parsed.path != '/v1/attorneys':
            self._json(404, {'error': 'not_found'})
            return

        params = parse_qs(parsed.query)
        errors, q = _validate_attorney_query(params)
        if errors:
            self._json(
                422,
                {
                    'error': 'validation_error',
                    'field_errors': errors,
                },
            )
            return

        sql = '''
        SELECT
          id, state, full_name, bar_number, city, status, admission_year, years_in_practice,
          practice_areas_json, firm_name, firm_url, office_address, counties_served_json,
          languages_json, free_consultation, contingency_fee_noted, peer_recognitions_json,
          source_profile_url, trauma_accessibility_json, intake_friction_json, risk_flags_json,
          last_verified_at
        FROM lm_attorneys
        WHERE state = ?
        '''
        args = [q['state']]

        if q['city']:
            sql += ' AND city = ?'
            args.append(q['city'])
        if q['status']:
            sql += ' AND status = ?'
            args.append(q['status'])
        sql += ' ORDER BY full_name'

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, args).fetchall()

        data = []
        for row in rows:
            practice_areas = _decode_json(row['practice_areas_json'], [])
            if q['practice_area'] and q['practice_area'] not in practice_areas:
                continue

            attorney = {
                'id': row['id'],
                'state': row['state'],
                'full_name': row['full_name'],
                'bar_number': row['bar_number'],
                'city': row['city'],
                'status': row['status'],
                'admission_year': row['admission_year'],
                'years_in_practice': row['years_in_practice'],
                'practice_areas': practice_areas,
                'firm_name': row['firm_name'],
                'firm_url': row['firm_url'],
                'office_address': row['office_address'],
                'counties_served': _decode_json(row['counties_served_json'], []),
                'languages': _decode_json(row['languages_json'], []),
                'free_consultation': bool(row['free_consultation']) if row['free_consultation'] is not None else None,
                'contingency_fee_noted': bool(row['contingency_fee_noted']) if row['contingency_fee_noted'] is not None else None,
                'peer_recognitions': _decode_json(row['peer_recognitions_json'], []),
                'source_profile_url': row['source_profile_url'],
                'trauma_accessibility': _decode_json(row['trauma_accessibility_json'], {}),
                'intake_friction': _decode_json(row['intake_friction_json'], {}),
                'risk_flags': _decode_json(row['risk_flags_json'], []),
                'last_verified_at': row['last_verified_at'],
            }

            evidence_rows = conn.execute(
                '''
                SELECT source_type, source_url, captured_at, excerpt, confidence
                FROM lm_attorney_sources
                WHERE attorney_id = ?
                ORDER BY captured_at DESC
                ''',
                (row['id'],),
            ).fetchall()
            attorney['source_evidence'] = [dict(e) for e in evidence_rows]

            discipline_rows = conn.execute(
                '''
                SELECT has_public_action, sanction_type, decision_date, citation, summary, source_url
                FROM lm_attorney_discipline
                WHERE attorney_id = ?
                ORDER BY decision_date DESC
                ''',
                (row['id'],),
            ).fetchall()
            attorney['discipline_records'] = [
                {
                    **dict(d),
                    'has_public_action': bool(d['has_public_action']),
                }
                for d in discipline_rows
            ]

            data.append(attorney)

        total = len(data)
        paged = data[q['offset']:q['offset'] + q['limit']]
        conn.close()
        self._json(
            200,
            {
                'data': paged,
                'meta': {
                    'total': total,
                    'limit': q['limit'],
                    'offset': q['offset'],
                },
            },
        )


def main():
    server = HTTPServer(('127.0.0.1', 8080), Handler)
    print('API listening on http://127.0.0.1:8080')
    server.serve_forever()


if __name__ == '__main__':
    main()

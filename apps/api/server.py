#!/usr/bin/env python3
"""Minimal HTTP API for intake, attorneys, and matching."""

import json
import sqlite3
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

DB_PATH = 'data/advocera.db'
PRACTICE_AREAS = {'personal_injury', 'civil_rights', 'employment_law', 'family_law'}
ATTORNEY_STATUSES = {'active', 'inactive', 'suspended'}
URGENCY_LEVELS = {'low', 'medium', 'high'}
MAX_LIMIT = 100


def _decode_json(text, fallback):
    if text in (None, ''):
        return fallback
    return json.loads(text)


def _first(params, key, default=None):
    return params.get(key, [default])[0]


def _parse_iso_dt(value):
    if value in (None, ''):
        return False
    try:
        datetime.fromisoformat(value.replace('Z', '+00:00'))
        return True
    except ValueError:
        return False


def _field_error(field, message):
    return {'field': field, 'message': message}


def _validate_attorney_query(params):
    errors = []

    state = _first(params, 'state', 'IA')
    practice_area = _first(params, 'practice_area')
    city = _first(params, 'city')
    status = _first(params, 'status')
    limit_raw = _first(params, 'limit', '25')
    offset_raw = _first(params, 'offset', '0')

    if state != 'IA':
        errors.append(_field_error('state', "Only 'IA' is currently supported in this prototype."))

    if practice_area and practice_area not in PRACTICE_AREAS:
        errors.append(_field_error('practice_area', f'Unsupported practice_area. Allowed: {sorted(PRACTICE_AREAS)}'))

    if status and status not in ATTORNEY_STATUSES:
        errors.append(_field_error('status', f'Unsupported status. Allowed: {sorted(ATTORNEY_STATUSES)}'))

    try:
        limit = int(limit_raw)
        if limit < 1 or limit > MAX_LIMIT:
            raise ValueError()
    except (TypeError, ValueError):
        errors.append(_field_error('limit', f'limit must be an integer between 1 and {MAX_LIMIT}.'))
        limit = 25

    try:
        offset = int(offset_raw)
        if offset < 0:
            raise ValueError()
    except (TypeError, ValueError):
        errors.append(_field_error('offset', 'offset must be an integer greater than or equal to 0.'))
        offset = 0

    return errors, {
        'state': state,
        'practice_area': practice_area,
        'city': city,
        'status': status,
        'limit': limit,
        'offset': offset,
    }


def _validate_intake_payload(payload):
    errors = []

    state = payload.get('state')
    practice_areas = payload.get('practice_areas')
    zip_code = payload.get('zip_code')
    urgency = payload.get('urgency')
    summary = payload.get('summary')
    consent_at = payload.get('consent_at')

    if state != 'IA':
        errors.append(_field_error('state', "state must be 'IA'."))

    if not isinstance(practice_areas, list) or not practice_areas:
        errors.append(_field_error('practice_areas', 'practice_areas must be a non-empty array.'))
    else:
        invalid = [p for p in practice_areas if p not in PRACTICE_AREAS]
        if invalid:
            errors.append(_field_error('practice_areas', f'Unsupported values: {invalid}'))

    if not zip_code:
        errors.append(_field_error('zip_code', 'zip_code is required.'))

    if urgency not in URGENCY_LEVELS:
        errors.append(_field_error('urgency', f'urgency must be one of {sorted(URGENCY_LEVELS)}.'))

    if not isinstance(summary, str) or len(summary.strip()) < 20:
        errors.append(_field_error('summary', 'summary must be at least 20 characters.'))

    if not _parse_iso_dt(consent_at):
        errors.append(_field_error('consent_at', 'consent_at must be a valid ISO 8601 date-time.'))

    contact = payload.get('contact')
    if contact is not None:
        if not isinstance(contact, dict):
            errors.append(_field_error('contact', 'contact must be an object.'))
        else:
            if not contact.get('full_name'):
                errors.append(_field_error('contact.full_name', 'contact.full_name is required when contact is provided.'))
            if not contact.get('email'):
                errors.append(_field_error('contact.email', 'contact.email is required when contact is provided.'))

    return errors


def _hydrate_attorney(conn, row):
    attorney = {
        'id': row['id'],
        'state': row['state'],
        'full_name': row['full_name'],
        'bar_number': row['bar_number'],
        'city': row['city'],
        'status': row['status'],
        'admission_year': row['admission_year'],
        'years_in_practice': row['years_in_practice'],
        'practice_areas': _decode_json(row['practice_areas_json'], []),
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
        {**dict(d), 'has_public_action': bool(d['has_public_action'])}
        for d in discipline_rows
    ]

    return attorney


def _score_match(intake, attorney):
    score = 0.0
    reasons = []

    intake_practice_areas = set(_decode_json(intake['practice_areas_json'], []))
    attorney_practice_areas = set(attorney['practice_areas'])
    overlap = intake_practice_areas & attorney_practice_areas
    if overlap:
        score += 30 + (5 * len(overlap))
        reasons.append(f"Practice fit: handles {', '.join(sorted(overlap))}.")

    if attorney['status'] == 'active':
        score += 20
        reasons.append('Active Iowa bar status.')
    else:
        score -= 100
        reasons.append(f"Attorney status is {attorney['status']}.")

    if intake['city'] and attorney['city'] and intake['city'].strip().lower() == attorney['city'].strip().lower():
        score += 10
        reasons.append(f"City fit: located in {attorney['city']}.")

    language_pref = intake['language_pref']
    if language_pref:
        languages = {x.lower() for x in attorney['languages']}
        if language_pref.lower() in languages:
            score += 10
            reasons.append(f"Language fit: offers {language_pref}.")

    if attorney.get('free_consultation') is True:
        score += 3
        reasons.append('Advertises free consultation.')

    has_public_action = any(d.get('has_public_action') for d in attorney['discipline_records'])
    if has_public_action:
        score -= 20
        reasons.append('Public disciplinary action found in record.')

    return max(score, 0.0), reasons


def _persist_matches(conn, intake, attorneys):
    saved = []
    for attorney in attorneys:
        score, reasons = _score_match(intake, attorney)
        if score <= 0:
            continue

        match_id = str(uuid.uuid4())
        conn.execute(
            '''
            INSERT INTO lm_matches (id, intake_id, attorney_id, score, reasons_json)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(intake_id, attorney_id) DO UPDATE SET
              score = excluded.score,
              reasons_json = excluded.reasons_json,
              updated_at = datetime('now')
            ''',
            (match_id, intake['id'], attorney['id'], score, json.dumps(reasons)),
        )

    conn.execute(
        "UPDATE lm_intakes SET status = 'matched', updated_at = datetime('now') WHERE id = ?",
        (intake['id'],),
    )

    rows = conn.execute(
        '''
        SELECT id, intake_id, attorney_id, score, reasons_json
        FROM lm_matches
        WHERE intake_id = ?
        ORDER BY score DESC, attorney_id ASC
        ''',
        (intake['id'],),
    ).fetchall()

    for row in rows:
        saved.append(
            {
                'id': row['id'],
                'intake_id': row['intake_id'],
                'attorney_id': row['attorney_id'],
                'score': row['score'],
                'reasons': _decode_json(row['reasons_json'], []),
            }
        )

    return saved


class Handler(BaseHTTPRequestHandler):
    def _json(self, status, payload):
        body = json.dumps(payload).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != '/v1/intakes':
            self._json(404, {'error': 'not_found'})
            return

        try:
            length = int(self.headers.get('Content-Length', '0'))
            raw = self.rfile.read(length).decode('utf-8')
            payload = json.loads(raw or '{}')
        except (ValueError, json.JSONDecodeError):
            self._json(422, {'error': 'validation_error', 'field_errors': [_field_error('body', 'Request body must be valid JSON.')]})
            return

        errors = _validate_intake_payload(payload)
        if errors:
            self._json(422, {'error': 'validation_error', 'field_errors': errors})
            return

        intake_id = str(uuid.uuid4())
        now = datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'

        conn = sqlite3.connect(DB_PATH)
        conn.execute('PRAGMA foreign_keys = ON;')
        with conn:
            conn.execute(
                '''
                INSERT INTO lm_intakes (
                  id, state, practice_areas_json, zip_code, city, language_pref, urgency,
                  budget_max_usd, summary, contact_json, consent_at, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, ?)
                ''',
                (
                    intake_id,
                    payload['state'],
                    json.dumps(payload['practice_areas']),
                    payload['zip_code'],
                    payload.get('city'),
                    payload.get('language_pref'),
                    payload['urgency'],
                    payload.get('budget_max_usd'),
                    payload['summary'],
                    json.dumps(payload.get('contact')) if payload.get('contact') is not None else None,
                    payload['consent_at'],
                    now,
                    now,
                ),
            )
        conn.close()

        response = {
            'id': intake_id,
            'state': payload['state'],
            'practice_areas': payload['practice_areas'],
            'zip_code': payload['zip_code'],
            'city': payload.get('city'),
            'urgency': payload['urgency'],
            'summary': payload['summary'],
            'status': 'new',
            'consent_at': payload['consent_at'],
            'created_at': now,
        }
        self._json(201, response)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == '/health':
            self._json(200, {'ok': True})
            return

        if parsed.path == '/v1/attorneys':
            params = parse_qs(parsed.query)
            errors, q = _validate_attorney_query(params)
            if errors:
                self._json(422, {'error': 'validation_error', 'field_errors': errors})
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
                attorney = _hydrate_attorney(conn, row)
                if q['practice_area'] and q['practice_area'] not in attorney['practice_areas']:
                    continue
                data.append(attorney)

            total = len(data)
            paged = data[q['offset']:q['offset'] + q['limit']]
            conn.close()
            self._json(200, {'data': paged, 'meta': {'total': total, 'limit': q['limit'], 'offset': q['offset']}})
            return

        if parsed.path.startswith('/v1/intakes/') and parsed.path.endswith('/matches'):
            parts = parsed.path.strip('/').split('/')
            if len(parts) != 4 or parts[0] != 'v1' or parts[1] != 'intakes' or parts[3] != 'matches':
                self._json(404, {'error': 'not_found'})
                return

            intake_id = parts[2]
            try:
                uuid.UUID(intake_id)
            except ValueError:
                self._json(422, {'error': 'validation_error', 'field_errors': [_field_error('intakeId', 'intakeId must be a UUID.')]})
                return

            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            intake = conn.execute(
                '''
                SELECT id, state, practice_areas_json, zip_code, city, language_pref, urgency, summary, status
                FROM lm_intakes
                WHERE id = ?
                ''',
                (intake_id,),
            ).fetchone()
            if not intake:
                conn.close()
                self._json(404, {'error': 'not_found'})
                return

            attorney_rows = conn.execute(
                '''
                SELECT
                  id, state, full_name, bar_number, city, status, admission_year, years_in_practice,
                  practice_areas_json, firm_name, firm_url, office_address, counties_served_json,
                  languages_json, free_consultation, contingency_fee_noted, peer_recognitions_json,
                  source_profile_url, trauma_accessibility_json, intake_friction_json, risk_flags_json,
                  last_verified_at
                FROM lm_attorneys
                WHERE state = ?
                ''',
                (intake['state'],),
            ).fetchall()

            attorneys = [_hydrate_attorney(conn, row) for row in attorney_rows]
            with conn:
                matches = _persist_matches(conn, intake, attorneys)
            conn.close()
            self._json(200, {'data': matches})
            return

        self._json(404, {'error': 'not_found'})


def main():
    server = HTTPServer(('127.0.0.1', 8080), Handler)
    print('API listening on http://127.0.0.1:8080')
    server.serve_forever()


if __name__ == '__main__':
    main()

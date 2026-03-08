#!/usr/bin/env python3
"""Minimal HTTP API for intake, attorneys, matching, and outreach drafts."""

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

DB_PATH = os.environ.get('DB_PATH', 'data/advocera.db')
PRACTICE_AREAS = {'personal_injury', 'civil_rights', 'employment_law', 'family_law'}
ATTORNEY_STATUSES = {'active', 'inactive', 'suspended'}
URGENCY_LEVELS = {'low', 'medium', 'high'}
REVIEW_TASK_STATUSES = {'pending', 'in_review', 'approved', 'changes_requested', 'rejected'}
REVIEW_DECISIONS = {'approved', 'changes_requested', 'rejected'}
MAX_LIMIT = 100
MAX_DRAFT_MATCHES = 3


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


def _audit_log(conn, *, intake_id, actor_id, entity_type, entity_id, action, before=None, after=None):
    conn.execute(
        '''
        INSERT INTO lm_audit_logs (
          id, intake_id, actor_id, entity_type, entity_id, action, before_json, after_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            str(uuid.uuid4()),
            intake_id,
            actor_id,
            entity_type,
            entity_id,
            action,
            json.dumps(before) if before is not None else None,
            json.dumps(after) if after is not None else None,
        ),
    )


def _serialize_row(row):
    return dict(row) if row is not None else None


def _read_json_body(handler):
    try:
        length = int(handler.headers.get('Content-Length', '0'))
        raw = handler.rfile.read(length).decode('utf-8')
        return json.loads(raw or '{}'), None
    except (ValueError, json.JSONDecodeError):
        return None, {
            'error': 'validation_error',
            'field_errors': [_field_error('body', 'Request body must be valid JSON.')],
        }


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
    before_count = conn.execute(
        'SELECT COUNT(*) FROM lm_matches WHERE intake_id = ?',
        (intake['id'],),
    ).fetchone()[0]
    before_status = intake['status']

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
    after_count = conn.execute(
        'SELECT COUNT(*) FROM lm_matches WHERE intake_id = ?',
        (intake['id'],),
    ).fetchone()[0]
    _audit_log(
        conn,
        intake_id=intake['id'],
        actor_id='system:matcher',
        entity_type='lm_intakes',
        entity_id=intake['id'],
        action='matches.generated',
        before={'status': before_status, 'match_count': before_count},
        after={'status': 'matched', 'match_count': after_count},
    )

    return _load_matches(conn, intake['id'])


def _load_matches(conn, intake_id):
    rows = conn.execute(
        '''
        SELECT id, intake_id, attorney_id, score, reasons_json
        FROM lm_matches
        WHERE intake_id = ?
        ORDER BY score DESC, attorney_id ASC
        ''',
        (intake_id,),
    ).fetchall()

    return [
        {
            'id': row['id'],
            'intake_id': row['intake_id'],
            'attorney_id': row['attorney_id'],
            'score': row['score'],
            'reasons': _decode_json(row['reasons_json'], []),
        }
        for row in rows
    ]


def _draft_content(intake, attorney, match):
    city_or_zip = intake['city'] or intake['zip_code']
    subject = f"New potential client referral: {city_or_zip}"
    top_reasons = '; '.join(match['reasons'][:2]) if match['reasons'] else 'Strong fit for this intake.'
    body = (
        f"Hello {attorney.get('full_name')},\n\n"
        f"We have a new intake for {', '.join(_decode_json(intake['practice_areas_json'], []))}. "
        f"Summary: {intake['summary']}\n\n"
        f"Why selected: {top_reasons}\n\n"
        "If you are available, please reply with your intake process and next available consultation window."
    )
    payload = {
        'intake_id': intake['id'],
        'attorney_id': attorney['id'],
        'attorney_name': attorney['full_name'],
        'practice_areas': _decode_json(intake['practice_areas_json'], []),
        'urgency': intake['urgency'],
        'score': match['score'],
        'reasons': match['reasons'],
    }
    return subject, body, payload


def _generate_drafts(conn, intake):
    if not intake['consent_at']:
        return None, 'consent_missing'

    if intake['status'] not in {'matched', 'draft_pending_review', 'in_review', 'ready_for_submit'}:
        return None, 'intake_not_matched'

    matches = _load_matches(conn, intake['id'])
    if not matches:
        return None, 'no_matches'

    top_matches = matches[:MAX_DRAFT_MATCHES]
    drafts = []

    for match in top_matches:
        before_draft = conn.execute(
            '''
            SELECT id, intake_id, attorney_id, channel, subject, body, payload_json, status
            FROM lm_outreach_drafts
            WHERE intake_id = ? AND attorney_id = ? AND channel = 'email'
            ''',
            (intake['id'], match['attorney_id']),
        ).fetchone()

        attorney_row = conn.execute(
            '''
            SELECT id, full_name
            FROM lm_attorneys
            WHERE id = ?
            ''',
            (match['attorney_id'],),
        ).fetchone()
        if not attorney_row:
            continue

        attorney = {'id': attorney_row['id'], 'full_name': attorney_row['full_name']}
        subject, body, payload = _draft_content(intake, attorney, match)
        draft_id = str(uuid.uuid4())

        conn.execute(
            '''
            INSERT INTO lm_outreach_drafts (
              id, intake_id, attorney_id, channel, subject, body, payload_json, status
            ) VALUES (?, ?, ?, 'email', ?, ?, ?, 'pending_review')
            ON CONFLICT(intake_id, attorney_id, channel) DO UPDATE SET
              subject = excluded.subject,
              body = excluded.body,
              payload_json = excluded.payload_json,
              status = 'pending_review',
              updated_at = datetime('now')
            ''',
            (draft_id, intake['id'], attorney['id'], subject, body, json.dumps(payload)),
        )
        after_draft = conn.execute(
            '''
            SELECT id, intake_id, attorney_id, channel, subject, body, payload_json, status
            FROM lm_outreach_drafts
            WHERE intake_id = ? AND attorney_id = ? AND channel = 'email'
            ''',
            (intake['id'], attorney['id']),
        ).fetchone()
        _audit_log(
            conn,
            intake_id=intake['id'],
            actor_id='system:draft_generator',
            entity_type='lm_outreach_drafts',
            entity_id=after_draft['id'],
            action='draft.upserted',
            before=_serialize_row(before_draft),
            after=_serialize_row(after_draft),
        )

    before_status = intake['status']
    conn.execute(
        "UPDATE lm_intakes SET status = 'draft_pending_review', updated_at = datetime('now') WHERE id = ?",
        (intake['id'],),
    )
    _audit_log(
        conn,
        intake_id=intake['id'],
        actor_id='system:draft_generator',
        entity_type='lm_intakes',
        entity_id=intake['id'],
        action='intake.status_updated',
        before={'status': before_status},
        after={'status': 'draft_pending_review'},
    )

    _sync_review_tasks(conn, intake['id'])

    rows = conn.execute(
        '''
        SELECT id, intake_id, attorney_id, channel, subject, body, payload_json, status
        FROM lm_outreach_drafts
        WHERE intake_id = ?
        ORDER BY updated_at DESC
        ''',
        (intake['id'],),
    ).fetchall()

    for row in rows:
        drafts.append(
            {
                'id': row['id'],
                'intake_id': row['intake_id'],
                'attorney_id': row['attorney_id'],
                'channel': row['channel'],
                'subject': row['subject'],
                'body': row['body'],
                'payload_json': _decode_json(row['payload_json'], {}),
                'status': row['status'],
            }
        )

    return drafts, None


def _parse_intake_subresource_path(path, resource):
    if not path.startswith('/v1/intakes/') or not path.endswith('/' + resource):
        return None
    parts = path.strip('/').split('/')
    if len(parts) != 4 or parts[0] != 'v1' or parts[1] != 'intakes' or parts[3] != resource:
        return None
    return parts[2]


def _parse_review_task_subresource_path(path, resource):
    prefix = '/v1/operator/review-tasks/'
    suffix = '/' + resource
    if not path.startswith(prefix) or not path.endswith(suffix):
        return None
    parts = path.strip('/').split('/')
    if len(parts) != 5 or parts[0] != 'v1' or parts[1] != 'operator' or parts[2] != 'review-tasks' or parts[4] != resource:
        return None
    return parts[3]


def _review_task_to_dict(row):
    return {
        'id': row['id'],
        'draft_id': row['draft_id'],
        'assignee_id': row['assignee_id'],
        'checklist_json': _decode_json(row['checklist_json'], {}),
        'status': row['status'],
        'decided_at': row['decided_at'],
    }


def _sync_review_tasks(conn, intake_id):
    rows = conn.execute(
        '''
        SELECT id
        FROM lm_outreach_drafts
        WHERE intake_id = ? AND status = 'pending_review'
        ''',
        (intake_id,),
    ).fetchall()
    for row in rows:
        before_task = conn.execute(
            '''
            SELECT id, draft_id, assignee_id, checklist_json, status, decided_at
            FROM lm_review_tasks
            WHERE draft_id = ?
            ''',
            (row['id'],),
        ).fetchone()
        conn.execute(
            '''
            INSERT INTO lm_review_tasks (id, draft_id, checklist_json, status)
            VALUES (?, ?, ?, 'pending')
            ON CONFLICT(draft_id) DO UPDATE SET
              status = CASE
                WHEN lm_review_tasks.status IN ('approved', 'rejected') THEN lm_review_tasks.status
                ELSE 'pending'
              END,
              updated_at = datetime('now')
            ''',
            (str(uuid.uuid4()), row['id'], json.dumps({'ready_for_review': True})),
        )
        after_task = conn.execute(
            '''
            SELECT id, draft_id, assignee_id, checklist_json, status, decided_at
            FROM lm_review_tasks
            WHERE draft_id = ?
            ''',
            (row['id'],),
        ).fetchone()
        _audit_log(
            conn,
            intake_id=intake_id,
            actor_id='system:review_queue',
            entity_type='lm_review_tasks',
            entity_id=after_task['id'],
            action='review_task.synced',
            before=_serialize_row(before_task),
            after=_serialize_row(after_task),
        )


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

        if parsed.path == '/v1/intakes':
            payload, error = _read_json_body(self)
            if error:
                self._json(422, error)
                return

            errors = _validate_intake_payload(payload)
            if errors:
                self._json(422, {'error': 'validation_error', 'field_errors': errors})
                return

            intake_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')

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
                _audit_log(
                    conn,
                    intake_id=intake_id,
                    actor_id='system:intake_api',
                    entity_type='lm_intakes',
                    entity_id=intake_id,
                    action='intake.created',
                    before=None,
                    after={
                        'status': 'new',
                        'state': payload['state'],
                        'practice_areas': payload['practice_areas'],
                    },
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
            return

        intake_id = _parse_intake_subresource_path(parsed.path, 'drafts')
        if intake_id:
            try:
                uuid.UUID(intake_id)
            except ValueError:
                self._json(422, {'error': 'validation_error', 'field_errors': [_field_error('intakeId', 'intakeId must be a UUID.')]})
                return

            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            intake = conn.execute(
                '''
                SELECT id, state, practice_areas_json, zip_code, city, language_pref, urgency, summary, status, consent_at
                FROM lm_intakes
                WHERE id = ?
                ''',
                (intake_id,),
            ).fetchone()
            if not intake:
                conn.close()
                self._json(404, {'error': 'not_found'})
                return

            with conn:
                drafts, block_reason = _generate_drafts(conn, intake)
            conn.close()

            if block_reason:
                self._json(409, {'error': 'conflict', 'reason': block_reason})
                return

            self._json(201, {'data': drafts})
            return

        task_id = _parse_review_task_subresource_path(parsed.path, 'claim')
        if task_id:
            try:
                uuid.UUID(task_id)
            except ValueError:
                self._json(422, {'error': 'validation_error', 'field_errors': [_field_error('taskId', 'taskId must be a UUID.')]})
                return

            payload, error = _read_json_body(self)
            if error:
                self._json(422, error)
                return
            assignee_id = payload.get('assignee_id') or 'operator-local'

            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                '''
                SELECT id, draft_id, assignee_id, checklist_json, status, decided_at
                FROM lm_review_tasks
                WHERE id = ?
                ''',
                (task_id,),
            ).fetchone()
            if not row:
                conn.close()
                self._json(404, {'error': 'not_found'})
                return

            if row['status'] not in {'pending', 'in_review'}:
                conn.close()
                self._json(409, {'error': 'conflict', 'reason': 'task_not_claimable'})
                return

            before_task = _serialize_row(row)
            intake_for_task = conn.execute(
                'SELECT intake_id FROM lm_outreach_drafts WHERE id = ?',
                (row['draft_id'],),
            ).fetchone()
            with conn:
                conn.execute(
                    '''
                    UPDATE lm_review_tasks
                    SET assignee_id = ?, status = 'in_review', updated_at = datetime('now')
                    WHERE id = ?
                    ''',
                    (assignee_id, task_id),
                )
                updated = conn.execute(
                    '''
                    SELECT id, draft_id, assignee_id, checklist_json, status, decided_at
                    FROM lm_review_tasks
                    WHERE id = ?
                    ''',
                    (task_id,),
                ).fetchone()
                _audit_log(
                    conn,
                    intake_id=(intake_for_task['intake_id'] if intake_for_task else None),
                    actor_id=assignee_id,
                    entity_type='lm_review_tasks',
                    entity_id=task_id,
                    action='review_task.claimed',
                    before=before_task,
                    after=_serialize_row(updated),
                )
            conn.close()
            self._json(200, _review_task_to_dict(updated))
            return

        task_id = _parse_review_task_subresource_path(parsed.path, 'decision')
        if task_id:
            try:
                uuid.UUID(task_id)
            except ValueError:
                self._json(422, {'error': 'validation_error', 'field_errors': [_field_error('taskId', 'taskId must be a UUID.')]})
                return

            payload, error = _read_json_body(self)
            if error:
                self._json(422, error)
                return

            decision = payload.get('decision')
            notes = payload.get('notes')
            updated_draft = payload.get('updated_draft')
            errors = []
            if decision not in REVIEW_DECISIONS:
                errors.append(_field_error('decision', f'decision must be one of {sorted(REVIEW_DECISIONS)}.'))
            if updated_draft is not None and not isinstance(updated_draft, dict):
                errors.append(_field_error('updated_draft', 'updated_draft must be an object when provided.'))
            if errors:
                self._json(422, {'error': 'validation_error', 'field_errors': errors})
                return

            task_status = decision
            draft_status = 'approved' if decision == 'approved' else ('pending_review' if decision == 'changes_requested' else 'failed')
            decided_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')

            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            task = conn.execute(
                '''
                SELECT id, draft_id, assignee_id, checklist_json, status, decided_at
                FROM lm_review_tasks
                WHERE id = ?
                ''',
                (task_id,),
            ).fetchone()
            if not task:
                conn.close()
                self._json(404, {'error': 'not_found'})
                return

            if task['status'] not in {'pending', 'in_review'}:
                conn.close()
                self._json(409, {'error': 'conflict', 'reason': 'task_not_decidable'})
                return

            checklist = _decode_json(task['checklist_json'], {})
            checklist['decision'] = decision
            checklist['notes'] = notes
            checklist['updated_draft'] = updated_draft
            draft_before = conn.execute(
                '''
                SELECT id, intake_id, attorney_id, channel, subject, body, payload_json, status
                FROM lm_outreach_drafts
                WHERE id = ?
                ''',
                (task['draft_id'],),
            ).fetchone()
            before_task = _serialize_row(task)

            with conn:
                if isinstance(updated_draft, dict):
                    fields = []
                    values = []
                    if 'subject' in updated_draft:
                        fields.append('subject = ?')
                        values.append(updated_draft['subject'])
                    if 'body' in updated_draft:
                        fields.append('body = ?')
                        values.append(updated_draft['body'])
                    if 'payload_json' in updated_draft:
                        fields.append('payload_json = ?')
                        values.append(json.dumps(updated_draft['payload_json']))
                    if fields:
                        values.extend([task['draft_id']])
                        conn.execute(
                            f"UPDATE lm_outreach_drafts SET {', '.join(fields)}, updated_at = datetime('now') WHERE id = ?",
                            tuple(values),
                        )

                conn.execute(
                    '''
                    UPDATE lm_outreach_drafts
                    SET status = ?, updated_at = datetime('now')
                    WHERE id = ?
                    ''',
                    (draft_status, task['draft_id']),
                )
                conn.execute(
                    '''
                    UPDATE lm_review_tasks
                    SET checklist_json = ?, status = ?, decided_at = ?, updated_at = datetime('now')
                    WHERE id = ?
                    ''',
                    (json.dumps(checklist), task_status, decided_at, task_id),
                )
                updated_task = conn.execute(
                    '''
                    SELECT id, draft_id, assignee_id, checklist_json, status, decided_at
                    FROM lm_review_tasks
                    WHERE id = ?
                    ''',
                    (task_id,),
                ).fetchone()
                draft_after = conn.execute(
                    '''
                    SELECT id, intake_id, attorney_id, channel, subject, body, payload_json, status
                    FROM lm_outreach_drafts
                    WHERE id = ?
                    ''',
                    (task['draft_id'],),
                ).fetchone()
                _audit_log(
                    conn,
                    intake_id=draft_after['intake_id'],
                    actor_id=(task['assignee_id'] or 'operator-local'),
                    entity_type='lm_outreach_drafts',
                    entity_id=task['draft_id'],
                    action='draft.review_decision_applied',
                    before=_serialize_row(draft_before),
                    after=_serialize_row(draft_after),
                )
                _audit_log(
                    conn,
                    intake_id=draft_after['intake_id'],
                    actor_id=(task['assignee_id'] or 'operator-local'),
                    entity_type='lm_review_tasks',
                    entity_id=task_id,
                    action='review_task.decided',
                    before=before_task,
                    after=_serialize_row(updated_task),
                )
            conn.close()
            self._json(200, _review_task_to_dict(updated_task))
            return

        self._json(404, {'error': 'not_found'})

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == '/health':
            self._json(200, {'ok': True})
            return

        if parsed.path == '/v1/operator/audit-logs':
            params = parse_qs(parsed.query)
            intake_id = _first(params, 'intake_id')
            limit_raw = _first(params, 'limit', '100')

            if not intake_id:
                self._json(
                    422,
                    {'error': 'validation_error', 'field_errors': [_field_error('intake_id', 'intake_id is required.')]},
                )
                return
            try:
                uuid.UUID(intake_id)
            except ValueError:
                self._json(
                    422,
                    {'error': 'validation_error', 'field_errors': [_field_error('intake_id', 'intake_id must be a UUID.')]},
                )
                return
            try:
                limit = int(limit_raw)
                if limit < 1 or limit > 500:
                    raise ValueError()
            except ValueError:
                self._json(
                    422,
                    {'error': 'validation_error', 'field_errors': [_field_error('limit', 'limit must be an integer between 1 and 500.')]},
                )
                return

            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                '''
                SELECT id, intake_id, actor_id, entity_type, entity_id, action, before_json, after_json, created_at
                FROM lm_audit_logs
                WHERE intake_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                ''',
                (intake_id, limit),
            ).fetchall()
            conn.close()
            self._json(
                200,
                {
                    'data': [
                        {
                            'id': row['id'],
                            'intake_id': row['intake_id'],
                            'actor_id': row['actor_id'],
                            'entity_type': row['entity_type'],
                            'entity_id': row['entity_id'],
                            'action': row['action'],
                            'before': _decode_json(row['before_json'], None),
                            'after': _decode_json(row['after_json'], None),
                            'created_at': row['created_at'],
                        }
                        for row in rows
                    ]
                },
            )
            return

        if parsed.path == '/v1/operator/review-tasks':
            params = parse_qs(parsed.query)
            status = _first(params, 'status', 'pending')
            if status not in REVIEW_TASK_STATUSES:
                self._json(
                    422,
                    {
                        'error': 'validation_error',
                        'field_errors': [_field_error('status', f'status must be one of {sorted(REVIEW_TASK_STATUSES)}.')],
                    },
                )
                return

            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                '''
                SELECT id, draft_id, assignee_id, checklist_json, status, decided_at
                FROM lm_review_tasks
                WHERE status = ?
                ORDER BY updated_at ASC
                ''',
                (status,),
            ).fetchall()
            conn.close()
            self._json(200, {'data': [_review_task_to_dict(row) for row in rows]})
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

        intake_id = _parse_intake_subresource_path(parsed.path, 'matches')
        if intake_id:
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

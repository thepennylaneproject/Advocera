#!/usr/bin/env python3
"""Load attorney seed data into SQLite, enforcing evidence provenance."""

import argparse
import json
import sqlite3
import uuid
from pathlib import Path


REQUIRED_ATTORNEY_FIELDS = ('id', 'state', 'full_name', 'status', 'practice_areas')


def _bool_to_int(value):
    if value is None:
        return None
    return 1 if bool(value) else 0


def validate_attorney(record: dict) -> None:
    for field in REQUIRED_ATTORNEY_FIELDS:
        if record.get(field) in (None, ''):
            raise ValueError(f'Missing required field: {field}')

    evidence = record.get('source_evidence', [])
    if not evidence:
        raise ValueError(f"Attorney {record['id']} is missing source_evidence")

    for i, source in enumerate(evidence, 1):
        for field in ('source_type', 'source_url', 'captured_at'):
            if source.get(field) in (None, ''):
                raise ValueError(
                    f"Attorney {record['id']} source_evidence[{i}] missing {field}"
                )

    for i, d in enumerate(record.get('discipline_records', []), 1):
        if d.get('source_url') in (None, ''):
            raise ValueError(
                f"Attorney {record['id']} discipline_records[{i}] missing source_url"
            )


def insert_attorney(conn: sqlite3.Connection, record: dict) -> None:
    conn.execute(
        '''
        INSERT INTO lm_attorneys (
          id, state, full_name, bar_number, city, status, admission_year, years_in_practice,
          practice_areas_json, firm_name, firm_url, office_address, counties_served_json,
          languages_json, free_consultation, contingency_fee_noted, peer_recognitions_json,
          source_profile_url, trauma_accessibility_json, intake_friction_json, risk_flags_json,
          last_verified_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
          state=excluded.state,
          full_name=excluded.full_name,
          bar_number=excluded.bar_number,
          city=excluded.city,
          status=excluded.status,
          admission_year=excluded.admission_year,
          years_in_practice=excluded.years_in_practice,
          practice_areas_json=excluded.practice_areas_json,
          firm_name=excluded.firm_name,
          firm_url=excluded.firm_url,
          office_address=excluded.office_address,
          counties_served_json=excluded.counties_served_json,
          languages_json=excluded.languages_json,
          free_consultation=excluded.free_consultation,
          contingency_fee_noted=excluded.contingency_fee_noted,
          peer_recognitions_json=excluded.peer_recognitions_json,
          source_profile_url=excluded.source_profile_url,
          trauma_accessibility_json=excluded.trauma_accessibility_json,
          intake_friction_json=excluded.intake_friction_json,
          risk_flags_json=excluded.risk_flags_json,
          last_verified_at=excluded.last_verified_at,
          updated_at=datetime('now')
        ''',
        (
            record['id'],
            record['state'],
            record['full_name'],
            record.get('bar_number'),
            record.get('city'),
            record['status'],
            record.get('admission_year'),
            record.get('years_in_practice'),
            json.dumps(record.get('practice_areas', [])),
            record.get('firm_name'),
            record.get('firm_url'),
            record.get('office_address'),
            json.dumps(record.get('counties_served', [])),
            json.dumps(record.get('languages', [])),
            _bool_to_int(record.get('free_consultation')),
            _bool_to_int(record.get('contingency_fee_noted')),
            json.dumps(record.get('peer_recognitions', [])),
            record.get('source_profile_url'),
            json.dumps(record.get('trauma_accessibility', {})),
            json.dumps(record.get('intake_friction', {})),
            json.dumps(record.get('risk_flags', [])),
            record.get('last_verified_at'),
        ),
    )


def insert_sources(conn: sqlite3.Connection, attorney_id: str, sources: list[dict]) -> None:
    conn.execute('DELETE FROM lm_attorney_sources WHERE attorney_id = ?', (attorney_id,))
    for source in sources:
        conn.execute(
            '''
            INSERT INTO lm_attorney_sources (
              id, attorney_id, source_type, source_url, captured_at, excerpt, confidence, evidence_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                str(uuid.uuid4()),
                attorney_id,
                source['source_type'],
                source['source_url'],
                source['captured_at'],
                source.get('excerpt'),
                source.get('confidence'),
                json.dumps(source),
            ),
        )


def insert_discipline(conn: sqlite3.Connection, attorney_id: str, discipline_records: list[dict]) -> None:
    conn.execute('DELETE FROM lm_attorney_discipline WHERE attorney_id = ?', (attorney_id,))
    for record in discipline_records:
        conn.execute(
            '''
            INSERT INTO lm_attorney_discipline (
              id, attorney_id, has_public_action, sanction_type, decision_date, citation, summary, source_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                str(uuid.uuid4()),
                attorney_id,
                _bool_to_int(record.get('has_public_action')),
                record.get('sanction_type'),
                record.get('decision_date'),
                record.get('citation'),
                record.get('summary'),
                record['source_url'],
            ),
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', default='data/advocera.db')
    parser.add_argument('--seed', default='seeds/attorneys.seed.json')
    args = parser.parse_args()

    seed_path = Path(args.seed)
    data = json.loads(seed_path.read_text(encoding='utf-8'))
    if not isinstance(data, list):
        raise SystemExit('Seed file must contain a JSON array of attorney records')

    conn = sqlite3.connect(args.db)
    conn.execute('PRAGMA foreign_keys = ON;')

    count = 0
    with conn:
        for record in data:
            validate_attorney(record)
            insert_attorney(conn, record)
            insert_sources(conn, record['id'], record.get('source_evidence', []))
            insert_discipline(conn, record['id'], record.get('discipline_records', []))
            count += 1

    conn.close()
    print(f'Seeded {count} attorneys from {seed_path}')


if __name__ == '__main__':
    main()

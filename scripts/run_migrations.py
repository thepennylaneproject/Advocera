#!/usr/bin/env python3
"""Apply SQL migrations to a local SQLite database."""

import argparse
import sqlite3
from pathlib import Path


def apply_migrations(db_path: Path, migrations_dir: Path) -> None:
    migrations = sorted(migrations_dir.glob('*.sql'))
    if not migrations:
        raise SystemExit(f'No migration files found in {migrations_dir}')

    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA foreign_keys = ON;')
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS lm_schema_migrations (
          filename TEXT PRIMARY KEY,
          applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        '''
    )

    applied = {
        row[0]
        for row in conn.execute('SELECT filename FROM lm_schema_migrations').fetchall()
    }

    for migration in migrations:
        if migration.name in applied:
            continue
        sql = migration.read_text(encoding='utf-8')
        with conn:
            conn.executescript(sql)
            conn.execute(
                'INSERT INTO lm_schema_migrations (filename) VALUES (?)',
                (migration.name,),
            )
        print(f'Applied {migration.name}')

    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', default='data/advocera.db')
    parser.add_argument('--migrations-dir', default='db/migrations')
    args = parser.parse_args()

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    apply_migrations(db_path, Path(args.migrations_dir))


if __name__ == '__main__':
    main()

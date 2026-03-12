# Advocera — Agent Instructions

## Cursor Cloud specific instructions

### Overview

Advocera is a Python 3 stdlib-only backend API (zero external dependencies) for legal intake and attorney matching. Single service: an HTTP server on port 8080 backed by SQLite.

### Running the application

```bash
# 1. Apply migrations (idempotent, safe to re-run)
python3 scripts/run_migrations.py --db data/advocera.db

# 2. Seed sample attorneys (idempotent via upsert)
python3 scripts/seed_attorneys.py --db data/advocera.db --seed seeds/attorneys.seed.json

# 3. Start API server (127.0.0.1:8080)
python3 apps/api/server.py
```

### Running tests

```bash
python3 -m unittest tests/test_attorneys_api.py -v
```

Tests are self-contained: each test creates a temporary SQLite DB, runs migrations, seeds data, and starts its own HTTP server on an ephemeral port. No external setup required.

### Key caveats

- There is no linter configured in this repo (no `pyproject.toml`, `setup.cfg`, `ruff.toml`, or similar). No lint command to run.
- There is no `requirements.txt` or `pyproject.toml` — every import is Python stdlib. The `package-lock.json` at root is a vestigial empty file with no purpose.
- The `DB_PATH` env var overrides the default database location (`data/advocera.db`). The server reads this at module load time.
- No `__init__.py` files exist in `apps/`, `apps/api/`, `scripts/`, or `tests/`. Tests must be run from the workspace root (`/workspace`) so Python resolves package imports correctly.
- The migration runner creates the `data/` directory automatically if missing.

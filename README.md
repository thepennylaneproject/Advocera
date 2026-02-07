# Advocera

## Local Data Prototype

This repo now includes a runnable local prototype for LM-201:
- SQLite migration for `lm_attorneys`, `lm_attorney_sources`, `lm_attorney_discipline`
- strict seed loader with evidence validation
- minimal `GET /v1/attorneys` API endpoint

## Run

```bash
python3 scripts/run_migrations.py --db data/advocera.db
python3 scripts/seed_attorneys.py --db data/advocera.db --seed seeds/attorneys.seed.json
python3 apps/api/server.py
```

Then query:

```bash
curl "http://127.0.0.1:8080/v1/attorneys?state=IA&practice_area=personal_injury"
```

Run tests:

```bash
python3 -m unittest tests/test_attorneys_api.py
```

## Notes

- `practice_area`, `city`, `status` filters are supported on `GET /v1/attorneys`.
- `state` defaults to `IA`.
- Seed loading enforces at least one `source_evidence` record per attorney and requires provenance fields (`source_type`, `source_url`, `captured_at`).

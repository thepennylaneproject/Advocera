# Advocera — Human-in-the-loop legal intake and attorney matching for people in crisis

> Part of <a href="https://thepennylaneproject.org">The Penny Lane Project</a> — technology that serves the individual.

## What This Is

Advocera is a backend platform that helps people facing time-sensitive legal situations find and connect with attorneys. It is designed for users who are overwhelmed, injured, or traumatized — people who need calm, structured support rather than a high-pressure sales funnel. Operators review every match and outreach draft before anything reaches a real attorney, keeping a human in the loop at every critical step.

## Current Status

**Alpha** — Core backend features are working end-to-end: intake submission, rule-based attorney matching, outreach draft generation, operator review queue, and full audit logging. Frontend and production deployment are not yet implemented and are actively in development.

## Technical Overview

- **Frontend:** Not yet implemented (planned: React)
- **Backend:** Python 3 stdlib HTTP server (`http.server`); no external framework
- **Database:** SQLite (local prototype); migration scripts included
- **AI:** Not yet integrated (planned: LLM-assisted outreach drafts)
- **Deployment:** Local prototype only; production deployment in progress

## Architecture

JAMstack-inspired separation of concerns with a standalone Python API backend and SQLite storage layer. All migrations are versioned SQL files applied via a CLI script. The API is fully covered by integration tests. Human-in-the-loop review is enforced at the data layer — no outreach draft can reach submission without an operator approval record.

## Development

```bash
# Apply database migrations
python3 scripts/run_migrations.py --db data/advocera.db

# Load sample attorney data
python3 scripts/seed_attorneys.py --db data/advocera.db --seed seeds/attorneys.seed.json

# Start the API server (binds to 127.0.0.1:8080)
python3 apps/api/server.py
```

Example queries:

```bash
# List attorneys by practice area
curl "http://127.0.0.1:8080/v1/attorneys?state=IA&practice_area=personal_injury"

# Submit an intake
curl -X POST "http://127.0.0.1:8080/v1/intakes" \
  -H "Content-Type: application/json" \
  -d '{"state":"IA","practice_areas":["personal_injury"],"zip_code":"50309","city":"Des Moines","urgency":"high","summary":"I was injured in a crash and need legal help with medical bills.","consent_at":"2026-02-07T12:00:00Z"}'

# Get matches and generate outreach drafts for an intake
curl "http://127.0.0.1:8080/v1/intakes/<intake-id>/matches"
curl -X POST "http://127.0.0.1:8080/v1/intakes/<intake-id>/drafts" -H "Content-Type: application/json" -d "{}"

# Operator review queue
curl "http://127.0.0.1:8080/v1/operator/review-tasks?status=pending"
curl "http://127.0.0.1:8080/v1/operator/audit-logs?intake_id=<intake-id>"
```

Run tests:

```bash
python3 -m unittest tests/test_attorneys_api.py
```

## License

All rights reserved. &copy; The Penny Lane Project.

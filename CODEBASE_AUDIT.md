# Advocera — Codebase Intelligence Audit

---

## SECTION 1: PROJECT IDENTITY

### 1. Project Name
**Advocera** (also referenced internally as "Still Here" in `AGENT.md`)

Defined in `package-lock.json`:
```json
{ "name": "advocera" }
```

### 2. Repository URL
`https://github.com/thepennylaneproject/Advocera`
(inferred from repository context; no explicit remote URL stored in tracked config files)

### 3. One-Line Description

*From `AGENT.md` (exact quote):*
> "Still Here isn't about law. It's about not disappearing before the clock runs out."

**Cleaner version:** Advocera is a human-in-the-loop legal intake and attorney-matching platform for people navigating time-sensitive legal situations under cognitive and emotional stress.

### 4. Project Status
**`Alpha`** — Core backend features (intake, attorney directory, rule-based matching, draft generation, operator review queue, audit logging) are working end-to-end. Frontend components are not yet implemented (explicitly listed as open backlog items LM-102, LM-103, LM-204, LM-303). The API is exercised by passing integration tests.

### 5. Commit Dates
- **First commit:** 2026-03-04 (commit `22cc235`, "pre-audit merge")
- **Most recent commit:** 2026-03-07 (commit `7b69d56`, "Initial plan")

### 6. Total Number of Commits
**2 commits** (shallow clone confirmed; full history may exist upstream)

### 7. Deployment Status
**Not deployed.** No `netlify.toml`, `vercel.json`, `Dockerfile`, CI/CD config, or production URL references exist in the repository. The server binds to `127.0.0.1:8080`, confirming local-prototype intent only.

### 8. Live URLs
`[NOT FOUND IN CODEBASE — REQUIRES MANUAL INPUT]`

---

## SECTION 2: TECHNICAL ARCHITECTURE

### 1. Primary Languages and Frameworks

| Language | Version | Usage |
|---|---|---|
| Python | 3.x (stdlib only; no `pyproject.toml` or `requirements.txt` present) | API server, migrations, seed loader, tests |

No external framework is used. The API server is built entirely on Python's built-in `http.server` and `sqlite3` modules.

The `package-lock.json` file exists but declares no JavaScript dependencies (`"packages": {}`). There is no JavaScript/TypeScript frontend in the repository.

### 2. Full Dependency List

**All dependencies are Python standard library only:**

| Category | Module | Purpose |
|---|---|---|
| Core framework | `http.server`, `urllib.parse` | HTTP request handling |
| Database | `sqlite3` | Embedded relational storage |
| Serialization | `json` | JSON encode/decode |
| Identifiers | `uuid` | UUID generation for all entity IDs |
| Date/time | `datetime` | ISO 8601 timestamp generation |
| Path handling | `pathlib.Path` | File path resolution |
| Testing | `unittest`, `threading`, `http.client`, `tempfile` | Test harness |
| CLI | `argparse` | Migration and seed scripts |

No third-party packages (pip, npm, etc.) are declared or used.

### 3. Project Structure

```
advocera/
├── apps/
│   └── api/
│       └── server.py         # Full HTTP API implementation (~1,083 lines)
├── db/
│   └── migrations/           # Ordered SQL migration files (SQLite)
│       ├── 0001_lm201_attorney_tables.sql
│       ├── 0002_lm203_intakes_matches.sql
│       ├── 0003_lm301_outreach_drafts.sql
│       ├── 0004_lm302_review_tasks.sql
│       └── 0005_lm401_audit_logs.sql
├── scripts/
│   ├── run_migrations.py     # CLI: apply SQL migrations to a SQLite db file
│   └── seed_attorneys.py     # CLI: load attorney JSON seed with provenance validation
├── seeds/
│   └── attorneys.seed.json   # 2-attorney sample dataset for local dev/testing
├── tests/
│   └── test_attorneys_api.py # Integration tests (9 tests, all passing)
├── AGENT.md                  # Agent behavior guardrails and product philosophy
├── AGENT_STYLE_REPO_CONVENTIONS.md  # Repo conventions for legal-match features
├── api-contracts.yaml        # OpenAPI 3.0.3 contract for all endpoints
├── data-implementation-plan.md     # Iowa attorney data pipeline design doc
├── sprint-1-backlog.md       # Sprint 1 tickets (LM-101 through LM-403)
├── README.md                 # Quick-start and curl examples
└── package-lock.json         # Placeholder (no JS dependencies)
```

### 4. Architecture Pattern
**Monolith / Embedded local prototype.**

The entire backend is a single Python file (`apps/api/server.py`) implementing an HTTP server with `BaseHTTPRequestHandler`. There is no framework, no middleware layer, no dependency injection, and no frontend. Data flow:

```
HTTP Request
    → Handler.do_GET / do_POST (route dispatch by path string matching)
    → Input validation (_validate_*, _parse_*)
    → SQLite connection (sqlite3.connect, PRAGMA foreign_keys ON)
    → Business logic (_score_match, _generate_drafts, _sync_review_tasks, etc.)
    → _audit_log (side-effect: immutable log entry)
    → JSON response (_json helper)
```

All state lives in a single SQLite database file at `data/advocera.db` (configurable via `DB_PATH`).

### 5. Database / Storage Layer

**Database:** SQLite (file-based, no server required)
**ORM:** None — raw SQL via `sqlite3` module
**Migration system:** Custom sequential file runner (`scripts/run_migrations.py`) with `lm_schema_migrations` tracking table

#### Tables

| Table | Purpose | Key Columns |
|---|---|---|
| `lm_attorneys` | Iowa attorney directory | `id`, `state`, `full_name`, `bar_number`, `city`, `status` (active/inactive/suspended), `admission_year`, `years_in_practice`, `practice_areas_json`, `firm_name`, `firm_url`, `office_address`, `counties_served_json`, `languages_json`, `free_consultation`, `contingency_fee_noted`, `peer_recognitions_json`, `source_profile_url`, `trauma_accessibility_json`, `intake_friction_json`, `risk_flags_json`, `last_verified_at` |
| `lm_attorney_sources` | Provenance evidence per attorney | `id`, `attorney_id` (FK), `source_type`, `source_url`, `captured_at`, `excerpt`, `confidence`, `evidence_json` |
| `lm_attorney_discipline` | Disciplinary records per attorney | `id`, `attorney_id` (FK), `has_public_action`, `sanction_type`, `decision_date`, `citation`, `summary`, `source_url` |
| `lm_intakes` | User legal intake submissions | `id`, `state`, `practice_areas_json`, `zip_code`, `city`, `language_pref`, `urgency`, `budget_max_usd`, `summary`, `contact_json`, `consent_at`, `status` |
| `lm_matches` | Attorney–intake match scores | `id`, `intake_id` (FK), `attorney_id` (FK), `score`, `reasons_json` — UNIQUE on `(intake_id, attorney_id)` |
| `lm_outreach_drafts` | Generated outreach email drafts | `id`, `intake_id` (FK), `attorney_id` (FK), `channel`, `subject`, `body`, `payload_json`, `status` — UNIQUE on `(intake_id, attorney_id, channel)` |
| `lm_review_tasks` | Operator review queue | `id`, `draft_id` (FK, UNIQUE), `assignee_id`, `checklist_json`, `status`, `decided_at` |
| `lm_audit_logs` | Immutable action log | `id`, `intake_id` (FK, nullable), `actor_id`, `entity_type`, `entity_id`, `action`, `before_json`, `after_json` |
| `lm_schema_migrations` | Migration tracking | `filename`, `applied_at` |

All JSON array/object fields are stored as TEXT (serialized JSON), consistent with SQLite's schema-less flexibility.

### 6. API Layer

All endpoints are under `/v1`. No authentication is implemented in the prototype.

| Route | Method | Purpose | Auth Required |
|---|---|---|---|
| `/health` | GET | Health check | No |
| `/v1/attorneys` | GET | List attorneys with filters (`state`, `practice_area`, `city`, `status`, `limit`, `offset`) | No |
| `/v1/intakes` | POST | Create a new intake (captures case summary, consent, practice areas, urgency) | No |
| `/v1/intakes/{intakeId}/matches` | GET | Score and persist attorney matches for an intake; returns ranked list | No |
| `/v1/intakes/{intakeId}/drafts` | POST | Generate outreach email drafts for top-matched attorneys | No |
| `/v1/operator/review-tasks` | GET | List review tasks filtered by `status` (default: `pending`) | No |
| `/v1/operator/review-tasks/{taskId}/claim` | POST | Claim a review task (assign operator) | No |
| `/v1/operator/review-tasks/{taskId}/decision` | POST | Submit review decision (`approved`, `changes_requested`, `rejected`) | No |
| `/v1/operator/audit-logs` | GET | List audit log entries by `intake_id` | No |

Validation errors return `422` with `{ "error": "validation_error", "field_errors": [...] }`.
Conflict conditions return `409` with `{ "error": "conflict", "reason": "..." }`.
Not-found returns `404` with `{ "error": "not_found" }`.

The OpenAPI 3.0.3 contract in `api-contracts.yaml` documents all schemas and responses.

### 7. External Service Integrations
**None.** The prototype uses no external APIs, services, or network calls. All data is local SQLite.

### 8. AI/ML Components
**None implemented in this codebase.** The matching engine (`_score_match`) is a deterministic rule-based scorer, not an ML model. Planned AI usage is referenced conceptually in `data-implementation-plan.md` (automated crawling, signal extraction) but no prompt, chain, or model integration exists in the current code.

### 9. Authentication and Authorization Model
**None implemented.** The server has no authentication layer, session management, or permission system. The `actor_id` field in audit logs is populated with hardcoded strings like `'system:matcher'`, `'system:draft_generator'`, `'operator-local'`, or caller-supplied values (not validated).

`[NOT FOUND IN CODEBASE — REQUIRES MANUAL INPUT for production auth design]`

### 10. Environment Variables

| Variable | Purpose |
|---|---|
| *(none declared)* | `DB_PATH` is a module-level constant in `server.py`, not an env var |

No environment variables are read from the environment in any file. `DB_PATH` defaults to `'data/advocera.db'` and is overridden in tests via direct attribute assignment (`server.DB_PATH = str(self.db_path)`).

`[NOT FOUND IN CODEBASE — environment variable strategy not yet implemented]`

---

## SECTION 3: FEATURE INVENTORY

| # | Feature | Description | Status | Key Files | Dependencies |
|---|---|---|---|---|---|
| 1 | **Intake submission** | User submits a case summary with practice area, urgency, zip code, language preference, and consent | `Functional` | `apps/api/server.py` (`do_POST /v1/intakes`, `_validate_intake_payload`), `db/migrations/0002_lm203_intakes_matches.sql`, `api-contracts.yaml` | None |
| 2 | **Attorney directory** | Operator/system can query Iowa attorneys by practice area, city, and status with pagination | `Functional` | `apps/api/server.py` (`do_GET /v1/attorneys`, `_validate_attorney_query`, `_hydrate_attorney`), `db/migrations/0001_lm201_attorney_tables.sql` | Attorney seed data |
| 3 | **Attorney seed loader** | Load structured attorney JSON with source provenance validation into SQLite | `Functional` | `scripts/seed_attorneys.py`, `seeds/attorneys.seed.json` | Migration must be applied first |
| 4 | **Rule-based match scoring** | Score attorneys against intake on practice fit, city, bar status, language; persist to `lm_matches` | `Functional` | `apps/api/server.py` (`_score_match`, `_persist_matches`, `do_GET /v1/intakes/{id}/matches`) | Intake, Attorney directory |
| 5 | **Outreach draft generation** | Generate templated email drafts for top 3 matches; gate on consent and matched status | `Functional` | `apps/api/server.py` (`_generate_drafts`, `_draft_content`, `do_POST /v1/intakes/{id}/drafts`) | Match scoring |
| 6 | **Operator review queue** | Operators list, claim, and decide on outreach drafts before any submission | `Functional` | `apps/api/server.py` (`_sync_review_tasks`, `do_GET /v1/operator/review-tasks`, `do_POST .../claim`, `do_POST .../decision`) | Draft generation |
| 7 | **Audit logging** | Every create/update/review action writes an immutable before/after log entry | `Functional` | `apps/api/server.py` (`_audit_log`), `db/migrations/0005_lm401_audit_logs.sql` | All mutation endpoints |
| 8 | **Intake UI (one-question flow)** | Multi-step, low-cognitive-load intake form | `Scaffolded` | `sprint-1-backlog.md` (LM-102) — *not yet built* | Intake API |
| 9 | **Intake confirmation screen** | Post-submit "what happens next" confirmation | `Scaffolded` | `sprint-1-backlog.md` (LM-103) — *not yet built* | Intake UI |
| 10 | **Top-3 attorney shortlist UI** | Frontend display of ranked attorney matches | `Scaffolded` | `sprint-1-backlog.md` (LM-204) — *not yet built* | Match scoring API |
| 11 | **Reviewer workspace UI** | Side-by-side operator review view with editable draft | `Scaffolded` | `sprint-1-backlog.md` (LM-303) — *not yet built* | Review queue API |
| 12 | **Pilot metrics endpoint** | KPI endpoint: `time_to_first_draft`, `review_edit_rate`, `submit_success_rate` | `Scaffolded` | `sprint-1-backlog.md` (LM-403) — *not yet built* | Audit logs |

---

## SECTION 4: DESIGN SYSTEM & BRAND

### 1. Color Palette
`[NOT FOUND IN CODEBASE]` — No frontend, no CSS, no Tailwind config, no design tokens exist in the repository. `AGENT_STYLE_REPO_CONVENTIONS.md` describes the intended design language (see §4.4) but defines no specific colors.

### 2. Typography
`[NOT FOUND IN CODEBASE]` — No fonts loaded; no frontend exists.

### 3. Component Library
`[NOT FOUND IN CODEBASE]` — No UI components exist. The backlog references a frontend (LM-102, LM-103, LM-204, LM-303) but none is present.

### 4. Design Language
As specified in `AGENT_STYLE_REPO_CONVENTIONS.md` (§4):
> "Visual style should read as calm, paper-like, and in-progress rather than dashboard-heavy."

Key design principles (documented, not yet implemented in UI):
- One clear primary CTA per screen
- Generous spacing, low visual noise
- No bright alert colors unless blocking risk
- No infinite scroll in critical flows

Tone: **Calm. Grounded. Respectful. Non-performative.**

### 5. Responsive Strategy
`[NOT FOUND IN CODEBASE]` — No frontend implemented.

### 6. Dark Mode
`[NOT FOUND IN CODEBASE]` — No frontend implemented.

### 7. Brand Assets
`[NOT FOUND IN CODEBASE]` — No logos, illustrations, or icon files in repository.

---

## SECTION 5: DATA & SCALE SIGNALS

### 1. User Model
The `lm_intakes` table captures per-intake user data:
- `state`, `practice_areas_json`, `zip_code`, `city`, `language_pref`, `urgency`, `budget_max_usd`, `summary`
- Optional `contact_json` (object with `full_name`, `email`, `phone`)
- `consent_at` (required; gates all outreach)

User journey from intake to value:
1. Submit intake (`POST /v1/intakes`) → status: `new`
2. Retrieve matches (`GET /v1/intakes/{id}/matches`) → status: `matched`
3. Generate drafts (`POST /v1/intakes/{id}/drafts`) → status: `draft_pending_review`
4. Operator claims task → status: `in_review`
5. Operator approves → draft status: `approved`
6. (Submission endpoint: not yet implemented) → status: `ready_for_submit` / `closed`

No user account, session, or authentication model exists in the prototype.

### 2. Content / Data Volume
- Seed file: **2 attorneys** (sample dataset for local dev only)
- System is designed to query all attorneys per state during matching (no pre-filtering by practice area in SQL; filtering happens in Python after hydration), which would not scale beyond a few hundred records without query optimization

### 3. Performance Considerations
- **Pagination:** Implemented on `GET /v1/attorneys` (`limit`/`offset` params, max 100)
- **No caching:** Every request opens a new SQLite connection
- **Practice area filtering:** Done in Python post-fetch (not in SQL `WHERE` clause) — O(n) over all attorney rows for that state
- **No rate limiting, no connection pooling, no async I/O**
- `MAX_DRAFT_MATCHES = 3` caps draft generation to top 3 matches

### 4. Analytics / Tracking
No analytics integration exists. The planned pilot metrics endpoint (LM-403) would derive KPIs from `lm_audit_logs` but is not yet implemented.

### 5. Error Handling
- **Validation errors:** Field-level `422` responses with `{ "field": "...", "message": "..." }` objects
- **Conflict errors:** `409` with explicit `reason` string (`consent_missing`, `intake_not_matched`, `no_matches`, `task_not_claimable`, `task_not_decidable`)
- **Not found:** `404` with `{ "error": "not_found" }`
- **JSON parse errors:** Caught with `try/except (ValueError, json.JSONDecodeError)`
- No centralized error logger, no Sentry/Rollbar, no stdout error reporting beyond HTTP server's default request logging
- `datetime.utcnow()` deprecation warning present (Python 3.12+)

### 6. Testing
**9 integration tests in `tests/test_attorneys_api.py`**, all passing.

| Test | Coverage |
|---|---|
| `test_attorneys_list_success` | `GET /v1/attorneys` happy path, pagination meta |
| `test_attorneys_list_practice_area_filter` | Practice area filter correctness |
| `test_attorneys_list_validation_error` | Multi-field validation errors on `GET /v1/attorneys` |
| `test_create_intake_and_generate_matches` | Full intake → match → draft happy path |
| `test_generate_drafts_returns_409_when_not_matched` | Draft conflict guard (intake not matched) |
| `test_review_task_queue_claim_and_decision` | Full review queue: list → claim → approve |
| `test_review_task_list_validation_error` | Invalid status param on review tasks |
| `test_audit_logs_query_by_intake_id` | Audit log creation and queryability |
| `test_audit_logs_validation_error` | Missing `intake_id` param validation |

No unit tests for individual helper functions. No tests for edge cases in `_score_match`, draft content generation, or error paths beyond the ones listed.

---

## SECTION 6: MONETIZATION & BUSINESS LOGIC

### 1. Pricing / Tier Structure
`[NOT FOUND IN CODEBASE]` — No pricing logic, plan definitions, or feature gating.

### 2. Payment Integration
`[NOT FOUND IN CODEBASE]` — No Stripe, PayPal, or any payment processing.

### 3. Subscription / Billing Logic
`[NOT FOUND IN CODEBASE]`

### 4. Feature Gates
`[NOT FOUND IN CODEBASE]` — The one implemented gate is **consent**: `POST /v1/intakes/{id}/drafts` returns `409 consent_missing` if `consent_at` is absent. This is a safety/legal gate, not a monetization gate.

### 5. Usage Limits
- `MAX_LIMIT = 100` — maximum `limit` param on attorney list
- `MAX_DRAFT_MATCHES = 3` — maximum outreach drafts generated per intake
- `500` — maximum audit log entries per query
- No rate limiting on any endpoint

---

## SECTION 7: CODE QUALITY & MATURITY SIGNALS

### 1. Code Organization
The codebase has a clear, deliberate separation of concerns:
- **Data migrations:** `db/migrations/` (SQL-only, versioned)
- **Seed loading:** `scripts/seed_attorneys.py` (validation + insertion, no business logic)
- **API/business logic:** `apps/api/server.py` (all request handling, validation, scoring, drafting, audit)
- **Tests:** `tests/` (integration-level only)

Within `server.py` there is no layering (no service/repository pattern), but helper functions are well-named and single-purpose. The file is long (~1,083 lines) and would benefit from modularization as features grow.

### 2. Patterns and Conventions
- **Naming:** `lm_` prefix for all database tables (Legal Match namespace); underscore-prefixed helpers indicate internal-use functions
- **Validation:** Centralized `_validate_*` functions returning `field_errors` lists before any DB access
- **Audit:** `_audit_log` called at every mutation point with before/after snapshots
- **Upsert pattern:** `INSERT ... ON CONFLICT DO UPDATE` used consistently for idempotent operations on matches, drafts, and review tasks
- **Row factory:** `sqlite3.Row` used for dict-like row access

No dependency injection, no repository pattern, no factory classes.

### 3. Documentation
- **README.md:** Clear quick-start with `curl` examples for every endpoint
- **AGENT.md:** Thorough behavioral guardrails for AI agents with explicit do/don't rules
- **AGENT_STYLE_REPO_CONVENTIONS.md:** Detailed repo conventions mapping product philosophy to code rules
- **api-contracts.yaml:** Complete OpenAPI 3.0.3 spec for all endpoints and schemas
- **sprint-1-backlog.md:** Structured sprint tickets with acceptance criteria
- **data-implementation-plan.md:** Iowa attorney data pipeline design with source priority and scoring model

Inline comments are minimal in `server.py`. No docstrings on helper functions. No architecture diagram.

### 4. TypeScript Usage
**Not applicable** — project is Python only. No TypeScript in the repository.

### 5. Error Handling Patterns
- Consistent `try/except` around JSON parsing and UUID validation
- Custom error response shapes (`validation_error`, `conflict`, `not_found`) are consistent
- No custom exception classes
- No user-facing error messages (API-only responses)
- `datetime.utcnow()` is deprecated in Python 3.12+ and will generate warnings; `datetime.now(datetime.UTC)` should be used instead

### 6. Git Hygiene
- 2 commits total in shallow clone
- Commit messages are terse ("pre-audit merge", "Initial plan")
- No branching strategy visible, no PR history accessible
- No `.github/pull_request_template.md` despite being referenced in `AGENT_STYLE_REPO_CONVENTIONS.md` §10

### 7. Technical Debt Flags
- **Hardcoded developer paths in tests** (fixed in this audit): `tests/test_attorneys_api.py` contained `/Users/sarahsahl/Desktop/advocera/` causing all tests to fail in any environment other than the original developer's machine
- **`datetime.utcnow()` deprecation:** Two uses in `server.py` (lines 582, 772) should be replaced with `datetime.now(datetime.UTC)`
- **Practice area filtering in Python, not SQL:** `_validate_attorney_query` accepts `practice_area` but the SQL query does not filter by it — filtering is done in Python after fetching all attorneys for the state. This is O(n) and will not scale
- **No `__init__.py` files:** `apps/api/` and `scripts/` directories lack `__init__.py`, relying on Python path conventions that work via the project root
- **`lm_attorney_snapshots` table** referenced in `data-implementation-plan.md` but has no migration file
- **Pilot metrics endpoint (LM-403):** Described in backlog, not implemented
- **No submission endpoint:** Draft status `approved` → `submitted` flow has no implementation
- **`DB_PATH` as global module constant:** Makes the module stateful; test harness overrides it directly via attribute assignment

### 8. Security Posture
- **Input validation:** Field-level validation on all inputs; practice areas and states constrained to explicit enums
- **SQL injection:** Protected — all queries use parameterized statements (`?` placeholders) throughout
- **No authentication/authorization:** Any caller can create intakes, generate drafts, and approve review tasks
- **No CORS configuration:** Server does not set CORS headers (would be needed for browser clients)
- **No HTTPS:** Server binds to `http://127.0.0.1:8080` — TLS not configured
- **Secrets management:** No secrets in code; no credentials of any kind (appropriate for prototype with no external integrations)
- **`draft.review_decision_applied` dynamic SQL:** Uses `f"UPDATE lm_outreach_drafts SET {', '.join(fields)}..."` — safe because `fields` contains only hardcoded string literals (`'subject = ?'`, `'body = ?'`, `'payload_json = ?'`), not user input; acceptable

---

## SECTION 8: ECOSYSTEM CONNECTIONS

### 1. Shared Code or Patterns with Sister Projects
`[NOT FOUND IN CODEBASE]` — No imports from or references to Relevnt, Codra, Ready, Mythos, embr, passagr, or other Penny Lane Project repositories.

The `lm_` table prefix is documented as a legal-match namespace in `AGENT_STYLE_REPO_CONVENTIONS.md`, which notes: *"Existing `agents.md` remains authoritative for immigration snapshot workflows"* — suggesting the same repository was previously (or concurrently) used for an immigration pipeline under different conventions.

### 2. Shared Dependencies or Infrastructure
`[NOT FOUND IN CODEBASE — REQUIRES MANUAL INPUT]` — No Supabase, Netlify, or shared infrastructure config in code.

### 3. Data Connections
`[NOT FOUND IN CODEBASE]` — No cross-project data reads or writes. Fully isolated SQLite database.

### 4. Cross-References
- `AGENT_STYLE_REPO_CONVENTIONS.md` references `/Users/sarahsahl/Desktop/AGENT.md` and `/Users/sarahsahl/Desktop/STYLE_AND_VOICE_GUARDRAILS.md` as external source documents not present in the repository

---

## SECTION 9: WHAT'S MISSING (CRITICAL)

### 1. Gaps for a Production-Ready Product

| Gap | Description |
|---|---|
| **Authentication & authorization** | No user accounts, operator login, session management, or permission model |
| **Frontend** | Zero UI code — entire intake, match review, and operator workspace is API-only |
| **Submission endpoint** | Draft approval has no downstream: no email sending, form submission, or notification |
| **HTTPS / TLS** | Server runs on plain HTTP; unacceptable for handling sensitive legal and personal data |
| **Real attorney data** | Only 2 seed attorneys; no ingestion pipeline for Iowa OPR, Iowa Bar, or court records |
| **Pilot metrics endpoint** | LM-403 not implemented; no KPI visibility |
| **Error logging / alerting** | No structured logging, no error aggregation |
| **Data re-verification cadence** | Referenced in `data-implementation-plan.md` but not implemented |
| **Connection pooling / async** | Single-threaded HTTP server with per-request SQLite connections; cannot serve concurrent users |
| **Statute-of-limitations tracking** | Not modeled despite being the core urgency driver per `AGENT.md` |

### 2. Gaps for Investor Readiness

| Gap | Description |
|---|---|
| **No live demo** | No deployed instance, no screenshots, no video walkthrough |
| **No user metrics** | No analytics, no cohort data, no conversion funnel |
| **No pilot results** | No evidence of real user intake or attorney engagement |
| **No revenue model in code** | No pricing, no billing, no monetization logic |
| **No `.github/pull_request_template.md`** | Referenced in conventions doc but absent from repo |
| **Shallow git history** | 2 commits obscures actual development timeline |

### 3. Gaps in the Codebase Itself

| Gap | Description |
|---|---|
| **Hardcoded developer paths in tests** | Fixed in this audit (was: `/Users/sarahsahl/Desktop/advocera/`) |
| **`lm_attorney_snapshots` migration missing** | Referenced in `data-implementation-plan.md`, no SQL file |
| **`datetime.utcnow()` deprecation** | Two uses in `server.py`; should be `datetime.now(datetime.UTC)` |
| **Practice area SQL filter missing** | Post-fetch Python filtering is O(n) — SQL WHERE clause should be added |
| **No `__init__.py` files** | `apps/api/` and `scripts/` are implicit namespace packages |
| **No `requirements.txt` or `pyproject.toml`** | Python version and environment not formally pinned |
| **`DB_PATH` global mutation in tests** | Fragile test isolation pattern |

### 4. Recommended Next Steps (Prioritized)

1. **Build and deploy a minimal frontend** (intake flow only) — Without a UI, no real user can be reached. A simple multi-step form (LM-102, LM-103) would enable a closed pilot with a small cohort and demonstrate user experience.

2. **Expand the Iowa attorney dataset** — The matching logic is functional but meaningless with 2 attorneys. Implement the Iowa OPR ingestion pipeline described in `data-implementation-plan.md` to build a corpus of 50–200 real, verified attorneys.

3. **Add authentication and operator workspace** — The reviewer queue (LM-303) is the human-in-the-loop control point. Without it, no attorney outreach can safely proceed. A simple session-based auth for operators would unlock the review-to-submission path.

4. **Implement the submission path** — The approved draft has nowhere to go. Even a basic email send (via SMTP or SendGrid) would close the loop from intake to attorney contact and make a pilot measurable.

5. **Deploy to a persistent environment** — A Fly.io, Railway, or similar deployment with HTTPS, environment variable management, and persistent SQLite (or migrate to PostgreSQL) would transform this from a local prototype into a demoable, investor-showable product.

---

## SECTION 10: EXECUTIVE SUMMARY

**Advocera** (also operating under the "Still Here" product philosophy) is a legal intake and attorney-matching platform built for people in acute distress — individuals who have been injured, traumatized, or are navigating time-sensitive legal situations and cannot effectively advocate for themselves. The product's core insight is that the primary failure mode for this population is not lack of legal information but cognitive and emotional overwhelm that causes people to disappear before the statute-of-limitations clock runs out. Advocera intervenes by reducing intake friction to a minimum, matching clients to verified Iowa attorneys based on practice fit, geography, language, and accessibility signals, and routing outreach through a human-in-the-loop review queue before any contact is made with an attorney.

The technical foundation is a clean, deliberately minimal Python backend — no framework dependencies, no external services, pure SQLite — that implements the full data pipeline from intake submission through attorney matching, outreach draft generation, operator review, and audit logging. The schema is well-designed: foreign key constraints, explicit status enums, provenance-enforced attorney records, and immutable before/after audit logs at every mutation point. The API is fully specified in OpenAPI 3.0.3. The matching engine applies a transparent, explainable rule-based scoring model with plain-language reasoning persisted alongside every match. All nine integration tests pass. The repository also contains unusually thorough product-philosophy documentation (`AGENT.md`, `AGENT_STYLE_REPO_CONVENTIONS.md`) that reflects genuine thinking about trauma-informed design — rare in early-stage codebases.

Honestly assessed, Advocera is a strong backend prototype that has not yet crossed into a demoable product. There is no frontend, no deployed instance, no real attorney data beyond two seed records, and no submission path after an operator approves a draft. The next milestone — a closed pilot with real Iowa users — requires three things: a minimal intake UI, a real attorney dataset ingested from Iowa OPR, and a deployment with HTTPS. Those three additions would transform this from a compelling technical proof-of-concept into an evidence-backed pitch for a problem that is large, underfunded, and genuinely underserved.

---

```
---
AUDIT METADATA
Project: Advocera
Date: 2026-03-07
Agent: GitHub Copilot (claude-sonnet-4-5)
Codebase access: full repo (read-only clone)
Confidence level: high — all claims verified directly from source files; inferences are marked
Sections with gaps: 1.8 (live URL), 2.7 (external services), 2.8 (AI/ML), 2.9 (auth), 2.10 (env vars), 4.1–4.7 (design system), 6.1–6.3 (monetization), 8.2–8.3 (shared infra)
Total files analyzed: 22
---
```

# Legal Match Iowa MVP - Sprint 1 Backlog

Sprint length: 2 weeks  
State scope: Iowa (`IA`)  
Practice areas: `personal_injury`, `civil_rights`, `employment_law`, `family_law`  
Delivery model: Human-in-the-loop (no auto-submit)

## Epic 1: Stress-Reducing Intake UX

### LM-101 - Intake API and persistence
- Type: Backend
- Story points: 5
- Description: Create a public intake endpoint that captures plain-language case details and consent.
- Acceptance criteria:
  - `POST /v1/intakes` accepts and validates required fields.
  - Intake is stored with status `new` and `state='IA'`.
  - `consent_at` is required and stored.
  - Validation errors return `422` with field-level issues.

### LM-102 - Intake UI (one-question flow)
- Type: Frontend
- Story points: 5
- Description: Build multi-step intake with low-cognitive-load copy and progress indicator.
- Acceptance criteria:
  - One primary question per screen.
  - Includes `I'm not sure` options where uncertainty is common.
  - User can save and continue in-session.
  - Submits successfully to `POST /v1/intakes`.

### LM-103 - Intake confirmation state
- Type: Frontend
- Story points: 2
- Description: Show a calming completion screen that sets expectations for next steps.
- Acceptance criteria:
  - Shows `what happens next` timeline.
  - Shows user-safe copy: no legal advice language.
  - Shows intake id/reference number.

## Epic 2: Iowa Attorney Directory + Matching

### LM-201 - Attorney table + source snapshot ingestion
- Type: Backend
- Story points: 5
- Description: Add data model for attorney records and source snapshots.
- Acceptance criteria:
  - `lm_attorneys` supports bar number, city, status, admission year, practice areas, language list.
  - `lm_attorneys` supports intake and accessibility indicators (`free consultation`, `contingency noted`, intake friction fields).
  - `lm_attorneys` supports risk metadata (`discipline_records`, `risk_flags`) with source-backed provenance.
  - `lm_attorney_sources` stores source URL + captured evidence payload per extracted claim.
  - Duplicate prevention on `(state, bar_number)`.

### LM-202 - Attorney list API
- Type: Backend
- Story points: 3
- Description: Expose attorney retrieval endpoint with Iowa and practice-area filters.
- Acceptance criteria:
  - `GET /v1/attorneys` supports filters for `state`, `practice_area`, `city`, `status`.
  - Default query is scoped to Iowa.
  - Response includes source-link metadata.

### LM-203 - Rule-based match scoring
- Type: Backend
- Story points: 5
- Description: Score attorneys against intake needs and persist reasons.
- Acceptance criteria:
  - Matching factors: practice fit, distance/city fit, active bar status, language fit.
  - Persists top matches in `lm_matches` with `reasons_json`.
  - Supports re-run without duplicate rows for same intake + attorney.

### LM-204 - Top-3 shortlist UI
- Type: Frontend
- Story points: 3
- Description: Display only the top 3 by default to reduce cognitive overload.
- Acceptance criteria:
  - Renders top 3 cards first.
  - Each card has plain-language `Why this lawyer` reasons.
  - Optional `Show more` reveals additional ranked options.

## Epic 3: HITL Outreach Workspace

### LM-301 - Draft generation endpoint
- Type: Backend
- Story points: 3
- Description: Generate editable outreach drafts (email/form payload style).
- Acceptance criteria:
  - `POST /v1/intakes/:id/drafts` creates draft rows tied to intake + attorney.
  - Draft includes channel, subject, body template, structured payload.
  - Status initialized as `pending_review`.

### LM-302 - Reviewer queue API
- Type: Backend
- Story points: 3
- Description: Add queue endpoints for operators to claim and review tasks.
- Acceptance criteria:
  - `GET /v1/operator/review-tasks` lists pending tasks.
  - `POST /v1/operator/review-tasks/:id/claim` assigns reviewer.
  - `POST /v1/operator/review-tasks/:id/decision` supports `approved|changes_requested|rejected`.

### LM-303 - Reviewer workspace UI
- Type: Frontend
- Story points: 5
- Description: Side-by-side review view with intake context + attorney info + editable draft.
- Acceptance criteria:
  - Reviewer can edit draft fields before approval.
  - Approval checklist required before final decision.
  - Every decision writes an audit event.

## Epic 4: Safety, Audit, and Pilot Readiness

### LM-401 - Audit logging middleware
- Type: Backend
- Story points: 3
- Description: Persist immutable action logs for create/update/review/submit actions.
- Acceptance criteria:
  - Logs include actor, entity, action, before/after payload.
  - Critical actions cannot bypass logging.
  - Logs are queryable by intake id.

### LM-402 - Consent + disclaimer enforcement
- Type: Backend/Frontend
- Story points: 2
- Description: Block outreach actions if consent is missing.
- Acceptance criteria:
  - No draft generation or submission without `consent_at`.
  - UI copy includes non-advice disclaimer.
  - Blocked attempts recorded in audit log.

### LM-403 - Pilot metrics endpoint
- Type: Backend
- Story points: 3
- Description: Expose Sprint 1 KPI endpoint.
- Acceptance criteria:
  - Returns `time_to_first_draft`, `review_edit_rate`, `submit_success_rate`.
  - Filterable by date range.
  - Values derived from `lm_*` tables only.

## Definition of Done (Sprint 1)
- All LM-101 to LM-403 acceptance criteria pass.
- OpenAPI contract updated and committed.
- DB migration applied in local dev and checked into repo.
- At least one Iowa seed dataset load path exists for attorneys.
- Basic happy-path integration test: intake -> matching -> draft -> review decision.

# Data Implementation Plan (Iowa Attorney Dataset)

## Goal
Build a verifiable Iowa attorney dataset for matching that separates hard facts (licensure/discipline) from inferred quality signals (trauma/accessibility/intake friction).

## Source Priority
1. Iowa OPR registry (`iowa_opr`) for license status and admission year.
2. Iowa Supreme Court discipline decisions + Iowa Bar summaries (`discipline_decision`) for sanctions.
3. Iowa Bar Find-A-Lawyer (`iowa_bar_find_a_lawyer`) for self-reported practice area/location.
4. Firm websites (`firm_site`) for intake details, language accessibility, trauma-aware phrasing.
5. Court/directory enrichment (`iowa_courts_online`, `directory`) for case depth and recognition metadata.

## Core Tables
- `lm_attorneys`
  - identity, licensure, practice areas, geography, contact/accessibility, and derived flags.
- `lm_attorney_sources`
  - immutable evidence rows with `source_type`, `source_url`, `captured_at`, `excerpt`, optional confidence.
- `lm_attorney_discipline`
  - one-to-many disciplinary actions by attorney with citation/date/sanction/source.
- `lm_attorney_snapshots`
  - optional denormalized JSON snapshots for repeatability and audit.

## Ingestion Pipeline
1. Seed Iowa candidates by practice area and city from opt-in directories.
2. Resolve attorney identity and verify active Iowa licensure in OPR.
3. Crawl firm profile/contact pages for intake and accessibility signals.
4. Attach disciplinary history from Iowa Supreme Court/Bar summaries.
5. Persist evidence rows for each extracted claim.
6. Compute derived fields and risk indicators after evidence is stored.

## Scoring Model (for `/intakes/{id}/matches`)
- Base fit score
  - practice fit, city/distance fit, active status, language fit.
- Supportive indicators (positive)
  - free consult, low-friction intake, accessibility options, vulnerable-client language.
- Risk adjustments (negative)
  - suspension/reprimand recency and severity, stale verification.
- Output
  - always provide plain-language reasons plus source-backed audit trail.

## Data Quality Rules
- Never label trauma-informed as certified unless explicitly evidenced.
- Keep inferred flags separate from disciplinary facts.
- Store every surfaced claim with at least one evidence URL.
- Re-verify high-sensitivity fields (`status`, `discipline`) on schedule before outreach.

## Suggested Cadence
- Daily: licensure/discipline re-check for attorneys in active shortlist pools.
- Weekly: full source refresh for Iowa attorney corpus.
- On-demand: refresh immediately when an operator flags data mismatch.

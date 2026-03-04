# Advocera / Still Here - Repo Conventions

This document maps `/Users/sarahsahl/Desktop/AGENT.md` and `/Users/sarahsahl/Desktop/STYLE_AND_VOICE_GUARDRAILS.md` into executable repository conventions for legal-match features.

## 1) Scope and precedence
- These conventions apply to Legal Match workstreams (`docs/legal-match`, `lm_*` schema, legal-intake/matching/review flows).
- Existing `agents.md` remains authoritative for immigration snapshot workflows.
- If conventions conflict, legal-match code follows this file and immigration pipeline code follows `agents.md`.

## 2) Product behavior conventions (required)
- Default to low-cognitive-load flows: one primary action per step.
- Do not require users to compare large option sets at once.
- Show top 3 attorney matches first; hide long lists behind `Show more`.
- Always provide a pause path: users can stop and return without data loss.
- Never make legal outcome promises in UI or automation.

## 3) Copy and tone conventions (required)
- Use plain language with short sentences.
- No exclamation points in critical flows (intake, match, outreach, review).
- Avoid urgency copy that induces panic.
- Avoid legal bravado and guarantee language.
- Approved tone: calm, grounded, respectful, non-performative.

## 4) Design conventions (required)
- Visual style should read as calm, paper-like, and in-progress rather than dashboard-heavy.
- Keep one clear primary CTA per screen.
- Preserve generous spacing and low visual noise.
- Avoid bright alert colors unless there is real blocking risk.
- Do not use infinite scroll in critical user flows.

## 5) Workflow and safety conventions (required)
- Human-in-the-loop approval is mandatory before any outbound submission.
- Consent gate is mandatory before draft generation/submission.
- Every attorney field displayed must retain source provenance.
- Every review decision and submission attempt must be audit logged.
- If uncertainty is high, defer and request human review rather than forcing completion.

## 6) Data/schema conventions
- Legal-match tables use `lm_` prefix.
- Domain enum values are explicit and constrained (state, practice area, status).
- Mutations in critical entities (`lm_intakes`, `lm_outreach_drafts`, `lm_review_tasks`) require audit entries.
- Source evidence payload is required for imported attorney/source rows.

## 7) API conventions
- Public endpoints return actionable, minimal payloads first.
- Validation failures must be field-level and non-judgmental (`422`).
- Risky operations return explicit block reasons (for example, missing consent).
- No endpoint may imply legal advice or legal outcome prediction.

## 8) QA acceptance gates
A ticket is not done unless all are true:
- UX gate: primary path can be completed with one major choice per screen.
- Copy gate: no banned language patterns in touched screens.
- Safety gate: consent + HITL checks enforced.
- Evidence gate: displayed attorney data has source linkage.
- Audit gate: create/update/review/submit actions produce logs.

## 9) Banned language patterns for review
- "guaranteed", "we guarantee", "you will win", "best lawyer for you"
- panic phrases like "act now or lose everything"
- motivational/hustle slogans in critical product flows

## 10) PR review protocol for legal-match changes
- Every legal-match PR must include the checklist in `.github/pull_request_template.md`.
- At least one reviewer must explicitly confirm cognitive-load and tone checks.
- PRs lacking consent/audit coverage cannot merge.

Created below. Save as `MVP_TASKS.md` in `verification-agent`.

````markdown
# MVP_TASKS — Verification Agent

Delivery board for v1, aligned to: **Plan → Execute → Adapt → Follow-up**.

## Status Legend
- `TODO` not started
- `DOING` in progress
- `DONE` complete
- `BLOCKED` waiting dependency

---

## Milestone 0 — Repo/Foundation

### VA-001 — Create project skeleton
- **Status:** TODO
- **Scope:** `src/`, `tests/`, `configs/`, `docs/`
- **Acceptance:**
  - Basic runnable app entrypoint exists
  - Local run instructions added to README

### VA-002 — Add config + env contract
- **Status:** TODO
- **Scope:** thresholds, retention days, consent default, logging level
- **Acceptance:**
  - `.env.example` present
  - App fails fast on missing required env vars

---

## Milestone 1 — Core Agent Loop

### VA-010 — Define strict state schema
- **Status:** TODO
- **Scope:** `input`, `evidence`, `signals`, `risk_score`, `risk_level`, `reasons`, `next_step`, `confidence`
- **Acceptance:**
  - Schema validation errors return safe error response
  - Final output fully derivable from state

### VA-011 — Implement phase runner
- **Status:** TODO
- **Scope:** `plan -> execute -> adapt -> follow_up`
- **Acceptance:**
  - Every run emits phase transition logs
  - Adapt phase is invoked when evidence conflicts

### VA-012 — Add out-of-scope guard
- **Status:** TODO
- **Scope:** reject unsupported inputs with safe fallback
- **Acceptance:**
  - Unsupported input returns non-crashing, user-safe message

---

## Milestone 2 — Tooling Contracts

### VA-020 — `check_source_credibility`
- **Status:** TODO
- **Acceptance:**
  - Input/output schema documented
  - Returns normalized credibility signals

### VA-021 — `detect_manipulation_language`
- **Status:** TODO
- **Acceptance:**
  - Detects urgency/fear/authority-pressure patterns
  - Returns explainable evidence snippets

### VA-022 — `cross_check_claims`
- **Status:** TODO
- **Acceptance:**
  - Produces consistency/conflict result with references
  - Handles “insufficient evidence” explicitly

### VA-023 — `privacy_risk_check`
- **Status:** TODO
- **Acceptance:**
  - Flags payment/credential/PII solicitation cues
  - Returns concrete user safety warning text

### VA-024 — Tool adapter interface
- **Status:** TODO
- **Acceptance:**
  - Agent calls only via stable tool interfaces
  - Tool internals can be swapped without agent changes

---

## Milestone 3 — Scoring + Policy

### VA-030 — Weighted scoring engine
- **Status:** TODO
- **Scope:** risk score + Low/Medium/High banding
- **Acceptance:**
  - Thresholds stored in config
  - High-harm cues have explicit heavier weights

### VA-031 — Confidence model
- **Status:** TODO
- **Scope:** confidence from signal quality + agreement
- **Acceptance:**
  - Low-confidence cannot output “Low risk”
  - Confidence included in state and telemetry

### VA-032 — HITL escalation policy
- **Status:** TODO
- **Scope:** emit “Needs human verification” when required
- **Acceptance:**
  - Escalation appears in final output for flagged cases

---

## Milestone 4 — Response UX

### VA-040 — Enforce response template
- **Status:** TODO
- **Template:**
  1. Trust Summary
  2. Risk Level
  3. Top 3 Reasons
  4. Suggested Next Step
- **Acceptance:**
  - No response emitted without reasons
  - Output remains plain-language and concise

### VA-041 — Safe next-step library
- **Status:** TODO
- **Scope:** reusable guidance snippets by risk band
- **Acceptance:**
  - High-risk guidance includes “do not share/pay yet”

---

## Milestone 5 — Privacy & Data Controls

### VA-050 — PII redaction pipeline
- **Status:** TODO
- **Scope:** phone/email/account-like masking before persistence
- **Acceptance:**
  - Redaction tests pass on seeded examples

### VA-051 — Consent-gated history storage
- **Status:** TODO
- **Acceptance:**
  - History persists only when consent flag is true
  - Retention policy auto-deletes expired records

### VA-052 — Data minimization audit
- **Status:** TODO
- **Acceptance:**
  - Stored payload fields are documented and justified

---

## Milestone 6 — Telemetry & Evaluation

### VA-060 — Run telemetry
- **Status:** TODO
- **Track:** latency, tool success/failure, confidence distribution, risk-band distribution
- **Acceptance:**
  - One telemetry record per run with run_id

### VA-061 — Disagreement review queue
- **Status:** TODO
- **Scope:** capture uncertain/conflicting cases for weekly tuning
- **Acceptance:**
  - Exportable queue exists for manual review

### VA-062 — Weekly metrics report
- **Status:** TODO
- **Scope:** comprehension proxy, risky-action prevention proxy, repeat usage
- **Acceptance:**
  - Script generates weekly markdown/CSV report

---

## Milestone 7 — Test Suite

### VA-070 — Unit tests (schema, tools, scoring)
- **Status:** TODO
- **Acceptance:**
  - Core modules covered with deterministic tests

### VA-071 — Seeded scenario tests (minimum 5)
- **Status:** TODO
- **Examples:** obvious scam, mixed-signal post, credible source, missing source, outdated claim
- **Acceptance:**
  - Expected risk bands match documented thresholds

### VA-072 — Response contract tests
- **Status:** TODO
- **Acceptance:**
  - All outputs include 4 required blocks

### VA-073 — Privacy tests
- **Status:** TODO
- **Acceptance:**
  - PII redaction and consent-gated storage tests pass

---

## Milestone 8 — Pilot Readiness

### VA-080 — Pilot domain configuration
- **Status:** TODO
- **Scope:** one domain only (scam-like forwarded messages)
- **Acceptance:**
  - Domain boundary enforced in config

### VA-081 — Baseline KPI capture
- **Status:** TODO
- **Acceptance:**
  - Pre-pilot baseline recorded for all agreed KPIs

### VA-082 — Go/No-Go checklist
- **Status:** TODO
- **Acceptance:**
  - All MVP acceptance criteria mapped and signed off

---

## Suggested Execution Order (Critical Path)

1. VA-001, VA-002  
2. VA-010, VA-011, VA-012  
3. VA-020..024  
4. VA-030, VA-031, VA-032  
5. VA-040, VA-041  
6. VA-050..052  
7. VA-060..062  
8. VA-070..073  
9. VA-080..082

---

## Definition of Done (MVP)

- All tasks in Milestones 1–8 are `DONE`
- Seeded scenario tests pass
- Output contract is stable and user-readable
- Privacy and consent controls validated
- Pilot baseline + first weekly report generated
````
# Project Execution Governance
Version: 2.0
Effective date: 2026-11-19
Repository: `mamunfb/universal-binance-ai-backend`

## 1. Purpose and authority

This document is the active policy for software engineering work in this repository. It replaces the former paired SPOT/FUTURES development-phase lock system.

The repository contains two canonical market-analysis specifications:
- `master-prompts/MASTER_PROMPT_01_SPOT.md`
- `master-prompts/MASTER_PROMPT_02_FUTURES.md`

Those prompts govern the behavior, research quality, market-specific calculations, safety, outputs and **20-step analytical sequence** of their respective analysis workflows. They do not govern the order in which software packages must be implemented.

For engineering workflow, use this document and `docs/PROJECT_PROGRESS_LEDGER.md`. If an old scope/audit/ledger passage says to pair engineering phases, unlock a numbered phase, block all later phases, or perform a complete codebase audit at every session, that passage is superseded.

## 2. Core operating model

1. Work on **one active task/work package at a time**. Finish, verify and record it before switching to another package, unless the user explicitly changes priority.
2. Choose the next package using actual dependencies, risk, user priority and available evidence—not a numbered SPOT/FUTURES phase gate.
3. Do not create a new task lock merely because another task is incomplete. A task may be started when its real prerequisites are satisfied.
4. A dependency may be marked BLOCKED only when a concrete prerequisite is missing. Record the exact dependency and the smallest action needed to resolve it.
5. SPOT and FUTURES implementation tasks may be scheduled independently. Keep their market-specific adapters, data, units, calculations and semantics separate; share only genuinely market-neutral utilities.
6. Keep the repository's existing architecture and build on it. Do not replace the application with a new project without explicit approval.
7. The 20 analytical phases in each canonical market prompt remain in their own specified order during a market-analysis run. This is not a software-development lock and does not force engineering packages into paired phase numbers.

## 3. Work package lifecycle and statuses

Use exactly these statuses in the progress ledger:

| Status | Meaning |
|---|---|
| `UNASSESSED` | Evidence has not yet been reviewed sufficiently to assign a reliable implementation status. |
| `NOT_STARTED` | Scope and prerequisites are understood; no accepted implementation work has begun. |
| `IN_PROGRESS` | Work is actively being implemented or investigated. |
| `BLOCKED` | A specific external/input/technical dependency prevents safe progress; blocker and resolution are recorded. |
| `VERIFICATION` | Implementation is ready for the applicable tests, review, runtime checks or acceptance evidence. |
| `COMPLETED` | Acceptance criteria are met and evidence is recorded. This is a technical baseline, not a claim of production deployment or user/business approval. |
| `REOPENED` | A confirmed defect/regression materially affects previously completed work; only the affected scope is reopened. |

Allowed transitions:
- `UNASSESSED → NOT_STARTED / IN_PROGRESS / BLOCKED` after evidence review.
- `NOT_STARTED → IN_PROGRESS / BLOCKED`.
- `IN_PROGRESS → BLOCKED / VERIFICATION`.
- `BLOCKED → IN_PROGRESS / NOT_STARTED` when its recorded blocker is resolved or scope is reset.
- `VERIFICATION → IN_PROGRESS / BLOCKED / COMPLETED`.
- `COMPLETED → REOPENED` only with a documented trigger and evidence.
- `REOPENED → IN_PROGRESS / VERIFICATION / COMPLETED / BLOCKED`.

Do not mark a package COMPLETED based only on code presence, a successful commit, a green unrelated workflow, or a test count copied from an older commit.

## 4. Definition of done — evidence-based

A package is COMPLETED only when all applicable criteria below are satisfied:

1. **Scope:** package goal, included work, exclusions, dependencies and acceptance criteria are explicit.
2. **Implementation:** intended changes are present; no unrelated changes are bundled without explanation.
3. **Correctness:** relevant normal, boundary, malformed-input, partial-data and failure paths are considered where applicable.
4. **Verification:** run the tests and checks appropriate to the changed risk surface. Record exact commands, results, environment and commit SHA. If a test could not be run, say so and do not imply it passed.
5. **Regression:** run targeted tests for affected behavior and adjacent contracts. A full suite is required when change scope/risk warrants it or CI requires it—not automatically for every documentation or isolated change.
6. **Security/data integrity:** assess relevant auth, secrets, privacy, financial arithmetic, market separation, data provenance, persistence, concurrency and failure handling.
7. **Evidence:** record changed files, test/CI links and run IDs, results, known limitations, unresolved risks, and the commit SHA to which the evidence applies.
8. **Review:** compare the result with the package acceptance criteria and the applicable canonical prompt requirements.
9. **Documentation:** update the progress ledger and relevant technical/audit documentation.

If live provider access, credentials, deployment access or a real-device environment is unavailable, distinguish code/test verification from live verification. A package can be completed only if that unavailable verification is explicitly outside its acceptance scope or is separately recorded as a remaining package; never imply it occurred.

## 5. Session startup — targeted, not repetitive full audits

At the beginning of a session:

1. Read this governance document and the progress ledger.
2. Read the relevant sections of the canonical SPOT and/or FUTURES prompt for the package being resumed. Read each prompt in full when first establishing or materially revising its implementation contract, or when the package spans the whole specification.
3. Inspect current branch, HEAD commit, working tree if available, open PR state, relevant CI runs/jobs and current files/tests for the active package.
4. Read the relevant audit history and prior package evidence. Reconcile it with current repository state; chat memory is not proof.
5. Review known open defects and dependencies that materially affect this package.
6. Define the exact task, acceptance criteria and verification plan before editing.

Do **not** repeat a full codebase audit or rerun every historical test on every session. Use a risk-based, change-focused review. Expand the inspection only when the change crosses module boundaries, touches security/data integrity, reveals a broader defect, or evidence indicates a systemic issue.

### First adoption / migration rule

Before ordinary feature work under this policy, perform one baseline reconciliation:
- map the old phase/audit evidence to the new work packages;
- inspect relevant code and current CI evidence;
- assign each package a status based on evidence;
- preserve unknowns as UNASSESSED;
- identify the single first package to work on.

Do not mechanically translate old phase statuses into new package completion. The former Phase 01 IN_PROGRESS state does not automatically determine the status of any new package.

## 6. Work execution protocol

For the active package:

1. State the task and acceptance criteria.
2. Inspect only the necessary source, interfaces, dependencies, tests and history, expanding when evidence warrants.
3. Implement the smallest coherent change that meets the agreed scope.
4. Add or update regression tests where behavior changes.
5. Run targeted verification; run broader checks when risk or CI policy requires.
6. Inspect the diff for unintended changes, secrets, unsafe behavior and Spot/Futures contamination.
7. Update package status and evidence in the ledger.
8. Commit to the authorized work branch and verify the commit/readback.
9. Report what changed, what did not, exact test/CI outcomes, limitations and next package.

If work is blocked, stop only the blocked task. Continue only with a different task if the user approves the change of active task or the task is already within the agreed package plan and has no dependency conflict. Do not pretend a blocked task is complete.

## 7. Regression and reopening policy

A completed package is an accepted baseline. Do not routinely re-audit or re-implement it during every later task.

Reopen a completed package only when there is concrete evidence of:
- a reproducible defect or regression;
- a security/privacy vulnerability;
- a data-integrity or persistence corruption issue;
- a material API/contract incompatibility;
- incorrect financial/market calculations or Spot/Futures cross-contamination;
- a changed upstream requirement that invalidates its acceptance criteria.

When reopening:
1. Mark only the affected package REOPENED and record the evidence, severity and impact.
2. Identify dependent packages that are demonstrably affected; reopen only those necessary.
3. Fix the issue and add regression coverage where practical.
4. Rerun the targeted tests and any broader checks required by risk.
5. Record a new commit and evidence; return the package to COMPLETED only after verification.
6. Preserve the previous completion record and history. Never erase or rewrite the fact that the earlier baseline passed its then-current checks.

A new feature request, preference change or unrelated enhancement is not automatically a regression and should be tracked as a new task.

## 8. Suggested work-package map

The following is a planning taxonomy, not a mandatory serial phase gate. The ledger must reflect actual evidence and dependencies.

- **WP-00 — Baseline repository audit and migration:** reconcile branch/PR/CI/code evidence and map old findings into this package model.
- **WP-01 — CI/CD and build reliability:** workflows, runners, dependency/build reproducibility and actionable CI evidence.
- **WP-02 — Backend architecture and API foundations:** service boundaries, API contracts, error handling and lifecycle.
- **WP-03 — Database, persistence and data integrity:** schemas, migrations, transactions, idempotency, retention and recovery.
- **WP-04 — Binance Spot research capabilities:** complete applicable Spot prompt requirements.
- **WP-05 — Binance Futures research capabilities:** USDⓈ-M and COIN-M capabilities, preserving their distinct semantics.
- **WP-06 — Market-data infrastructure:** collection, coverage, rate limits, timestamps, freshness, failure ledgers and source provenance.
- **WP-07 — News, on-chain, tokenomics and AI research intelligence:** source quality, verification, provider limitations and model traceability.
- **WP-08 — Risk, safety and research guardrails:** qualification, sizing, uncertainty, red-team, signal lifecycle and no-execution constraints.
- **WP-09 — Frontend and institutional dashboard:** UI contracts, charts, responsive behavior, accessibility and error states.
- **WP-10 — Authentication and application security:** auth boundaries, secrets, abuse protection, dependency/security review.
- **WP-11 — Cross-system integration:** API/UI/MCP/AI-client integration and contract compatibility.
- **WP-12 — Full QA and performance:** risk-based integration, browser/device, accessibility, load, memory and performance evidence.
- **WP-13 — Staging deployment and verification:** staging-only deployment, smoke tests, observability and rollback evidence.
- **WP-14 — Production readiness and deployment:** readiness review and explicit user authorization before any production action.

Packages may be split into smaller independently verifiable tasks. Do not claim a broad package complete while material sub-tasks remain open; either keep it IN_PROGRESS or split it transparently.

## 9. Safety and authorization boundaries

These are hard controls and are not relaxed by the task-based model:

- Research-only: do not implement or invoke order placement, cancellation, modification, withdrawal, wallet signing or live trade execution.
- Never fabricate prices, news, sources, timestamps, probabilities, rankings, backtest results or test outcomes.
- Do not silently omit symbols/contracts, failed endpoints, missing datasets or requirements. Report coverage and limitations.
- Keep Spot long-only rules separate from Futures long/short and contract-specific rules. Do not mix prices, units, fees, margin, funding, liquidation or contract calculations.
- Never commit secrets, API keys, passwords, tokens or environment files.
- Do not modify `main`, merge a PR, deploy to production, alter production databases/secrets, or enable trading/execution without explicit user authorization for that specific action.
- Use a dedicated work branch and preserve the existing application architecture.
- A successful staging deployment is not production approval.

## 10. Reporting standard

Every meaningful work increment must report:
- active package and status;
- branch, commit SHA and PR link where available;
- exact files/components changed;
- exact tests/checks run and their results;
- CI run/job state tied to the relevant commit (queued/running is not passed);
- defects fixed, risks, limitations and blockers;
- whether main, PR merge, production, databases, secrets or execution capabilities were untouched;
- next concrete task.

## 11. Retired policy

The following former controls are retired for software engineering:
- paired SPOT Phase N then FUTURES Phase N implementation;
- Phase N+1 LOCKED until both markets' Phase N is complete;
- blanket prohibition on work belonging to a later numbered analytical phase;
- mandatory full-codebase audit and full-suite execution at the start of every session;
- a single paired phase ledger as the engineering source of truth.

Historical documents may retain these words as evidence of the previous policy. They must not be treated as active instructions. The canonical market-analysis prompts retain their own 20-step analytical sequencing.

## 12. Change control

Any future change to this governance must:
- be explicitly requested or approved by the user;
- update this document, the progress ledger and resume prompt together;
- state which old instructions are superseded;
- preserve historical evidence;
- be checked for conflicting active references before completion.


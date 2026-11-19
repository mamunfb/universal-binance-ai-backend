# Project Execution Governance
## Strict Sequential Execution + Locked Completion + Regression Gate + Controlled Reopening

**Status:** Authoritative project-work policy  
**Applies to:** Repository engineering, implementation, testing, QA, documentation, staging, and deployment work  
**Policy owner:** Repository owner  
**Default rule:** One active work package at a time

This document is the single source of truth for how future project work must be planned, executed, verified, recorded, and resumed. It replaces any older informal interpretation of a “lock system” for project tasks. If another project note conflicts with this policy, follow this document unless the repository owner explicitly approves a written exception.

> **Important scope boundary:** This is a software-project execution policy. It does not authorize live trading, order placement, withdrawals, production deployment, merging to `main`, database-destructive operations, or changes to secrets. This repository is research-only; its existing safety boundaries remain in force.

---

## 1. Strict sequential execution

1. Divide the project into numbered work packages, then into small, verifiable tasks and subtasks.
2. Work on only **one active main work package** at a time.
3. Finish, test, document, and verify the active package before starting the next package.
4. Do not skip unfinished subtasks or silently move incomplete work into a later package.
5. If work is blocked by an external dependency, missing permission, unavailable service, or failing test, mark it **BLOCKED**, record the exact reason and evidence, and stop work that depends on it.
6. Independent investigation or documentation may continue only when it does not bypass the blocked package or create conflicting changes. The active package must remain clearly identified.
7. At the beginning of every resumed session, read this policy and the Master Progress Ledger, inspect the current branch and working state, and continue from the first unfinished task. Do not assume that a previous session completed work without checking its evidence.

## 2. Completion gate: when a work package may be locked

A work package is not complete merely because code was written or a commit was created. It may be marked **COMPLETED & LOCKED** only when all applicable requirements below are satisfied:

- All planned tasks and subtasks are implemented, or explicitly documented as not applicable with a reason approved by the repository owner.
- Required automated and manual tests have actually been executed.
- Test results, commands, environment/context, and relevant run links or logs are recorded.
- Relevant regression checks pass.
- Required review, security checks, data-integrity checks, and documentation updates are complete for that package.
- No unresolved Critical or High severity defect remains within the package's scope.
- Any accepted lower-severity issue is listed with its impact, workaround (if any), and follow-up decision; it must not be hidden.
- The Git branch, commit SHA, changed files, and evidence are recorded.
- The completion summary accurately distinguishes verified results from untested or unavailable checks.

If any required check was not run, the package must remain **IN VERIFICATION**, **INCOMPLETE**, or **BLOCKED** as appropriate. Never report an unexecuted test as passed.

## 3. What LOCKED means

After the completion gate passes, mark the package **COMPLETED & LOCKED**.

LOCKED means:

- Its verified completion record and commit/evidence references are preserved as the accepted baseline.
- Do not repeat the entire implementation or full audit without a specific reason.
- Do not make unrelated edits to the completed package.
- Do not erase, rewrite, or silently replace its historical completion evidence.
- Future work may rely on the verified baseline, subject to the regression gate below.

LOCKED does **not** mean that the code can never change or that a defect should be ignored. A completed package can be reopened under the controlled rules in Section 5.

## 4. Regression Gate: how to treat earlier completed work

When starting or changing a later package, do **not** automatically rerun every earlier package's full audit. Instead:

1. Identify which earlier components, APIs, schemas, workflows, configuration, or user-facing behaviours the new change could affect.
2. Define a proportionate regression test set for those affected areas before or during implementation.
3. Run the relevant tests and record the results.
4. Keep unrelated completed packages LOCKED when there is no evidence that they were affected.
5. If a regression fails, stop the dependent work, investigate the failure, and use the controlled reopening process.

Examples:

- A database schema or migration change requires relevant migration, persistence, data-integrity, and dependent API tests.
- An API contract change requires relevant backend, API integration, and dependent frontend/client tests.
- A dashboard change requires the affected UI, responsive-layout, accessibility, runtime, and API-integration checks.
- A CI workflow or build configuration change requires the affected workflow/build checks to be executed.
- A security or authentication change requires the relevant authorization, rejection, and regression tests.

A regression check is not a substitute for the full completion gate when the package itself is being completed or reopened.

## 5. Controlled REOPEN: when an earlier package may be reopened

Reopen an earlier package only when there is a concrete, recorded reason, such as:

- A reproducible regression caused by later work.
- A newly discovered defect that belongs to that package.
- A Critical or High security, privacy, reliability, or data-integrity issue.
- Evidence showing that a previous test result or completion claim was incorrect or insufficient.
- A necessary requirement change approved by the repository owner.

Use this process:

1. **Record the finding:** describe the observed behaviour, expected behaviour, reproduction steps, severity, and evidence.
2. **Identify the owner package:** determine which previously completed package contains the defect or must be changed.
3. **Reopen only what is necessary:** change that package's status to **REOPENED** and record why. Do not reopen every earlier package by default.
4. **Map dependencies:** identify later packages or components that rely on the affected behaviour. Pause only work that could be invalidated by the issue.
5. **Fix the root cause:** implement the smallest safe correction; avoid unrelated refactoring.
6. **Re-verify:** run the direct fix tests, relevant regression tests, and any required security/data-integrity checks.
7. **Preserve history:** record the new commit SHA, test evidence, and a short reopening/fix report. Keep the previous completion record for traceability; do not erase it.
8. **Re-lock:** once the applicable completion gate passes, mark the package **COMPLETED & LOCKED** again.
9. **Resume sequential work:** continue with the first unfinished, unblocked package.

If the fix changes an interface or behaviour used by other completed packages, run targeted regression tests for those dependent packages. Reopen a dependent package only if its own implementation or completion evidence must change.

## 6. Work package status vocabulary

Use these statuses consistently in the Master Progress Ledger:

| Status | Meaning |
|---|---|
| NOT STARTED | Work has not begun. |
| IN PROGRESS | The package is the current active work. |
| IN VERIFICATION | Implementation is done; required verification is still running or incomplete. |
| BLOCKED | Work cannot safely proceed; the reason and required unblock action are recorded. |
| REOPENED | A previously locked package has a documented issue requiring correction and re-verification. |
| COMPLETED & LOCKED | All applicable completion-gate requirements have passed and evidence is recorded. |

Do not use “done”, “green”, or “passed” as a substitute for evidence. A workflow being queued, skipped, cancelled, or failing to obtain a runner is not a passing CI run.

## 7. Master Progress Ledger (required)

Maintain one durable ledger in the repository, recommended path: `docs/PROJECT_PROGRESS_LEDGER.md`.

For every package, record:

- Package number, title, objective, scope, and dependencies.
- Task/subtask checklist and current status.
- Active branch and base branch.
- Implementation summary and changed file paths.
- Commit SHA(s) and pull request link(s), if any.
- Test names/commands, environment, timestamps, and exact outcomes.
- CI workflow/run links and whether jobs actually executed.
- Regression checks performed and affected components.
- Audit/security findings, severity, resolution, and accepted exceptions.
- Evidence links or artifact locations.
- Completion decision, date, and reviewer/approval where required.
- Reopen history, root cause, corrective commit, and re-lock evidence.

Update the ledger as work progresses, not only at the end. Preserve historical entries; append new evidence rather than silently rewriting past results.

## 8. Suggested top-level work-package roadmap

Use this as an initial planning structure, not as a claim that any package is already complete. At the initial audit, reconcile it with the repository's actual code, open pull requests, documented scope, and current evidence. Split packages into smaller tasks as needed.

1. **Repository and project-state audit** — branches, PRs, architecture, scope, existing evidence, and unfinished work.
2. **CI/CD and build reliability** — workflow configuration, runner execution, build/test failures, and reproducible CI evidence.
3. **Backend architecture and API foundations** — service boundaries, configuration, API contracts, and error handling.
4. **Database and data integrity** — schema/migrations, transactions, persistence, consistency, backup/restore strategy, and migration tests.
5. **Spot research capabilities** — implement and verify the approved Spot research scope and its documented phases.
6. **Futures research capabilities** — implement and verify the approved USDⓈ-M/COIN-M research scope and its documented phases.
7. **Market-data infrastructure** — exchange adapters, REST/WebSocket ingestion, collectors, freshness, coverage, and failure handling.
8. **AI/research intelligence** — evidence aggregation, analysis services, source verification, and uncertainty reporting.
9. **Risk, safety, and research guardrails** — validation, data-quality controls, safe defaults, and explicit non-execution boundaries.
10. **Frontend and dashboard** — UI, charts, API integration, responsive layouts, and user-facing states.
11. **Authentication and application security** — identity, authorization, secret handling, rate limits, and security hardening.
12. **Cross-system integration** — backend, database, market-data providers, AI adapters, and frontend integration.
13. **Full QA and performance audit** — functional, regression, accessibility, mobile, performance, resilience, and security verification.
14. **Staging deployment and verification** — only after approval; build, configuration, migrations, smoke tests, and rollback readiness.
15. **Production readiness and deployment** — formal readiness review, explicit owner approval, controlled deployment, health monitoring, and post-deploy verification.

The roadmap order may be adjusted only when repository evidence shows a dependency or safety reason. Record the reason in the ledger before changing the order. Keep the one-active-package rule.

## 9. Safety, permissions, and deployment boundaries

- Never merge a pull request, push directly to `main`, deploy to production, change DNS, modify production secrets, perform destructive database operations, or enable live trading without explicit repository-owner approval.
- Use a dedicated working branch for changes. Keep unrelated work out of the branch.
- Do not enable exchange order placement, withdrawals, signing, or trading execution. The repository's research-only boundary remains in force unless the owner explicitly changes the project scope through a separate, reviewed decision.
- Do not expose secrets in code, logs, commits, reports, or screenshots.
- If a required permission or external action is unavailable, mark the task BLOCKED and explain exactly what is needed.
- A successful code change is not proof of a successful deployment. Deployment must be verified from the target platform and live health checks.

## 10. Required end-of-task report

At the end of each work session, report:

1. Active package and task.
2. What changed (or what was investigated).
3. Files changed and commit SHA, if a commit was created.
4. Tests actually executed and exact results.
5. Tests not executed and why.
6. CI status with run links and runner/job execution evidence.
7. Current package status.
8. Any blockers, risks, or required owner decisions.
9. The exact next task to resume.

Never claim that work continued between sessions or in the background unless an actual tool or automation performed it.

---

## Final execution rule

**Plan one package → implement its tasks → run required tests → verify evidence → record the result → mark COMPLETED & LOCKED → move to the next package.**

For later packages, run only the regression checks relevant to the change. If a real defect is found, reopen only the affected package (and pause dependent work where necessary), fix it, verify it, preserve the history, re-lock it, and then resume.

**The goal is not to repeatedly redo completed work. The goal is to build the system step by step on verified baselines, with clear evidence, controlled reopening, and no unsupported success claims.**

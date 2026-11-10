# MASTER RESUME PROMPT — UNIVERSAL BINANCE AI BACKEND
## Repository-driven, paired SPOT + FUTURES implementation controller

You are continuing an existing software engineering project. Do not start from assumptions and do not ask the user to re-explain the workflow. The repository is the persistent source of truth.

## Mandatory first actions — before coding
1. Open and read these two canonical specifications in full:
   - `master-prompts/MASTER_PROMPT_01_SPOT.md`
   - `master-prompts/MASTER_PROMPT_02_FUTURES.md`
2. Read the complete project scope and execution contract:
   - `docs/UNIVERSAL_PROJECT_SCOPE_AND_EXECUTION_CONTROL.md`
3. Read the live implementation audit and paired phase ledger:
   - `docs/MASTER_PROMPT_IMPLEMENTATION_AUDIT.md`
4. Inspect the current repository branch, working tree, latest commits, open PR, CI runs/jobs and actual code/tests relevant to the current phase.
5. Reconcile the repository evidence. Do not rely on old chat summaries or assume a task is complete because a previous assistant said so.

## Mandatory pre-coding audit of all existing work — do this before writing new feature code

This step is compulsory at the beginning of every session, including a resumed session. Do not start by adding the next feature.

1. Audit the code already present in the repository, not just the files you expect to edit. First map the architecture and dependencies; then inspect the relevant modules, API routes, providers, configuration, persistence, background jobs, tests and security-sensitive paths.
2. Compare existing implementation line by line against:
   - the two canonical master prompts;
   - the complete project scope;
   - the current phase's accepted requirements and recorded evidence;
   - the actual API contracts and data semantics used by the code.
3. Run the existing test suite and relevant lint, type, static-analysis, import/build and security checks that the repository supports. Inspect failures and warnings; do not assume old green CI proves the current code is correct.
4. Look specifically for logic errors, incorrect formulas/units, Spot/Futures cross-contamination, wrong endpoint/parameter/response assumptions, incomplete pagination, fixed scan caps, silent symbol/contract skips, missing error accounting, stale data treated as live, timezone/timestamp errors, unsafe defaults, secret leakage, race conditions, unhandled exceptions, broken API contracts, weak tests and documentation/code mismatches.
5. For every finding, record severity, affected file/line or component, reproducible evidence, impact, and proposed correction. Separate confirmed defects from suspected risks.
6. Correct confirmed defects in existing work before adding new feature implementation, prioritizing defects that affect the current authorized phase, shared foundations, security, data integrity or previously accepted functionality. Add regression tests for every correction where practical, then rerun the relevant tests.
7. Do not use this audit as permission to implement a later phase early. If a defect is inseparable from current-phase correctness or threatens security/data integrity, fix it now and document why. If it belongs exclusively to a locked later-phase feature, record it in the audit as DEFERRED / PHASE N LOCKED; do not implement that feature yet.
8. If a defect cannot be safely corrected because evidence, credentials, provider access or requirements are missing, mark it BLOCKED and explain exactly what is needed. Never make speculative edits just to make tests pass.
9. Only after the audit findings are classified, in-scope confirmed defects are corrected, regression checks pass (or blockers are recorded), and the user has been told the audit result may new current-phase feature coding begin.

Required pre-coding audit output to the user:
- codebase areas inspected and checks run;
- confirmed bugs found, with severity and evidence;
- fixes applied and regression tests;
- suspected risks / unverified items;
- deferred findings tied to locked phases;
- blockers;
- explicit statement that the pre-coding audit is complete or incomplete.

## Determine the exact restart point
- Find the lowest-numbered phase for which either SPOT or FUTURES is not COMPLETE.
- Resume that same phase; do not jump forward.
- Within a phase, SPOT is always first, then FUTURES.
- If SPOT is COMPLETE but FUTURES is not, continue FUTURES for that same phase.
- If either side is BLOCKED, stop implementation at that phase, document the exact blocker and required resolution, and do not advance the other market to a later phase.
- Phase N+1 remains LOCKED until both SPOT Phase N and FUTURES Phase N are COMPLETE with evidence.
- When all 20 paired phases are complete, execute the post-Phase-20 final closure checklist in the project scope. Do not declare overall completion before that closure passes.

## Non-negotiable rules
- The two canonical master prompts are the governing detailed specifications. Read and obey every applicable section, including configuration, global rules, API architecture, all 20 phases, phase protocol, output continuity, research quality, safety, pre-flight, re-validation and final command.
- The project scope document captures the complete work perimeter from the very first section through final closeout. It is not limited to the 20 phases.
- Do not replace the existing application with a new project. Preserve the architecture and extend it.
- Keep Spot and Futures adapters, calculations, statuses and market-specific requirements separate. Share only neutral utilities.
- This is research-only: never add order execution, cancellation, modification, withdrawal or signing functionality.
- No fabricated data, prices, news, sources, timestamps, probabilities, rankings, trade dates or entry windows.
- Never silently skip symbols/contracts, failed endpoints, missing datasets or requirements.
- No fixed scan cap where the canonical prompt requires the complete eligible universe.
- Do not mark work complete based only on code presence or green tests. Check every canonical requirement and its output/evidence.
- Before any new feature coding in every session, audit the code written so far for correctness, run available checks, fix confirmed in-scope defects and add regression tests. Do not build new work on top of known broken code.
- Do not implement later-phase features early. You may inspect later code for dependencies; only fix what is strictly needed by the current authorized phase.
- Never modify main or merge the PR without explicit user authorization.
- Keep the canonical prompt files unchanged unless the user explicitly supplies new canonical versions.

## Per-phase work protocol
For current Phase N, first complete the mandatory pre-coding audit above. Then:
A. Extract every SPOT Phase N task, subtask and output from the Spot canonical prompt. Make a checklist; implement only this market-specific phase; test all normal, partial, failure and missing-data paths; review exact outputs and evidence.
B. Then extract every FUTURES Phase N task, subtask and output from the Futures canonical prompt. Implement USD-M/COIN-M distinctions as required; test and review the same way.
C. Run paired integration/regression checks and validate provider/source timestamps, rate limits, coverage accounting and failure ledgers.
D. Update the paired ledger and audit with requirement-level status, code references, tests, evidence, limitations and commit SHA.
E. Mark the combined phase COMPLETE and unlock Phase N+1 only if both market-specific checklists are fully accepted. Otherwise stop and retain IN_PROGRESS/BLOCKED.

Statuses are exactly: NOT_STARTED, IN_PROGRESS, BLOCKED, COMPLETE.

## Required session opening report
Before making changes, tell the user briefly:
- branch and PR;
- current earliest incomplete phase;
- SPOT status and FUTURES status;
- last verified commit/CI status;
- the exact next task being resumed;
- whether any blocker exists;
- the pre-coding audit plan and relevant checks to run.
Do not begin new feature coding until the pre-coding audit and required in-scope corrections are complete.
Then continue work without asking the user to repeat known instructions.

## Required session closing report
After each meaningful work increment:
- summarize exactly what changed and what did not change;
- list files/commits/PR links;
- report actual test commands/results and CI state (do not call queued/running CI passed);
- show updated Spot/Futures/combined phase statuses and next-phase lock;
- identify outstanding requirements and blockers;
- state the exact restart point for the next session.

## Current known checkpoint (must be re-verified against GitHub before use)
- Repository: `mamunfb/universal-binance-ai-backend`
- Work branch: `work/dual-master-prompt-audit`
- Draft PR: https://github.com/mamunfb/universal-binance-ai-backend/pull/1
- Active phase: Phase 01 only.
- SPOT Phase 01: IN_PROGRESS.
- FUTURES Phase 01: IN_PROGRESS.
- Phase 02: LOCKED.
- The latest known audit commit was `b0c907ee48dbae9c86340d1c5b2e6622379d2344`; this is historical context, not proof of current HEAD or CI status.
- Phase 16 experimental work was reverted/deferred. Do not restore it until Phase 16 is authorized for both markets.

## Start command
Start now by completing the mandatory first actions and repository reconciliation. Then resume the exact earliest incomplete paired phase. Do not merely explain a plan; perform the authorized repository work, tests and documentation updates.
# MASTER RESUME PROMPT — UNIVERSAL BINANCE AI BACKEND
## Task-based engineering controller with separate SPOT/FUTURES analysis specifications

You are continuing an existing software engineering project. The repository is the persistent source of truth. Do not ask the user to repeat established requirements, and do not assume prior chat claims are current evidence.

## 1. Read the active controls first

1. Read `docs/PROJECT_EXECUTION_GOVERNANCE.md` in full.
2. Read `docs/PROJECT_PROGRESS_LEDGER.md` and identify the active package and its recorded evidence.
3. Read the relevant parts of `master-prompts/MASTER_PROMPT_01_SPOT.md` and/or `master-prompts/MASTER_PROMPT_02_FUTURES.md`. Read both in full when first establishing or materially revising their implementation contract.
4. Read the relevant sections of `docs/UNIVERSAL_PROJECT_SCOPE_AND_EXECUTION_CONTROL.md` and `docs/MASTER_PROMPT_IMPLEMENTATION_AUDIT.md`. Treat old paired-phase locks and per-session full-audit mandates in historical records as superseded.
5. Inspect current branch, HEAD, working-tree status where available, open PR, recent commits, relevant CI runs/jobs, and code/tests for the active package.
6. Reconcile repository evidence. A historical checkpoint or previous assistant message is not proof of current branch state or passing tests.

## 2. Keep the two sequencing systems separate

- The Spot and Futures master prompts each define their own 20-step **market-analysis workflow**. Preserve each prompt's internal order and every market-specific requirement when implementing or running that analysis.
- Software development follows the task/work-package governance. There is no paired engineering phase sequence, no “Phase N+1 LOCKED” rule, and no rule that SPOT engineering must finish before FUTURES engineering (or vice versa).
- Never merge Spot and Futures market semantics. Keep USDⓈ-M linear and COIN-M inverse distinctions explicit.

## 3. Choose one active engineering task

1. Read the current ledger and continue its active package if it remains valid.
2. If no package is active, select one next task using user priority, dependencies, risk and repository evidence.
3. Work on one package at a time. Split broad packages into small, verifiable tasks when useful.
4. Do not infer package status from old phase numbers. If migration is incomplete, keep uncertain packages UNASSESSED and reconcile evidence first.
5. A real dependency can block a task; record the exact missing input/access and smallest resolution. Do not impose artificial locks on unrelated tasks.

## 4. Targeted session review — no blanket full audit

Before editing:
- inspect the files, interfaces, tests and dependencies materially related to the active task;
- review relevant prior audit findings and verify whether they still apply;
- check current CI evidence for the relevant commit;
- expand review to adjacent/system-wide areas only when change risk, security, data integrity or a discovered defect warrants it.

Do not repeat a full repository audit or run the entire test suite at every session by default. Select verification based on changed behavior and risk. Run broader suites when integration impact, CI policy or a defect justifies them.

## 5. Implement, verify and record

For the active task:
1. Confirm scope and acceptance criteria before coding.
2. Preserve existing architecture; make the smallest coherent change.
3. Add/update regression tests for changed behavior where practical.
4. Run targeted tests, lint, type/build/static/security checks as applicable.
5. Inspect the final diff for unintended changes, secrets, unsafe behavior and Spot/Futures cross-contamination.
6. Record exact commands, environment, results, commit SHA and CI job state. Never report queued/running as passed; never copy a test count from another commit.
7. Update `docs/PROJECT_PROGRESS_LEDGER.md` and relevant audit/technical docs.
8. Commit to the authorized work branch and verify the remote readback.
9. Report exactly what changed, what did not, test/CI evidence, limitations and next task.

## 6. Completion and regression rules

A package may become COMPLETED only when its applicable acceptance criteria and evidence in `PROJECT_EXECUTION_GOVERNANCE.md` are satisfied. Code presence or a green unrelated test suite is insufficient.

A completed package is a stable baseline. Do not rerun every old audit for every new package. If a concrete defect, regression, security issue, data-integrity failure, material contract break or incorrect financial/market calculation is found:
- reopen only the affected package;
- reopen dependent packages only when evidence shows they are affected;
- add a regression test where practical;
- rerun targeted and risk-appropriate broader checks;
- preserve the previous completion history and record the new evidence.

Do not reopen completed work for unrelated enhancements; create a new task instead.

## 7. Hard safety and permission boundaries

- This is a research-only project. Never add or invoke order placement, cancellation, modification, withdrawals, wallet signing or live trade execution.
- Never fabricate prices, news, sources, timestamps, probabilities, rankings, backtest results or test outcomes.
- Report incomplete market coverage, missing data, failed endpoints and stale data explicitly.
- Keep Spot long-only and Futures contract-specific rules separate.
- Never commit API keys, passwords, tokens or environment files.
- Do not modify `main`, merge a PR, deploy to production, change production databases/secrets, or enable execution without explicit user authorization for that exact action.
- Preserve historical audit evidence. Do not erase past test failures or rewrite an old result as if it never happened.

## 8. Session opening report

Before making changes, briefly report:
- current branch, HEAD and PR state;
- active package and status;
- the exact next task and acceptance criteria;
- relevant latest CI evidence and any blocker;
- files/components to inspect and planned targeted checks.

Do not invent an active package or claim the baseline migration is complete when the ledger says UNASSESSED.

## 9. Session closing report

After each meaningful increment, report:
- exact changes and unchanged boundaries;
- files, commit SHA and PR link;
- actual test commands/results and CI run/job state;
- updated package status and evidence;
- remaining risks/blockers;
- exact next task.

## 10. Start command

Start by reconciling the active package against the current repository and CI evidence. If the ledger is still in its initial migration state, perform WP-00 first. Then continue one package at a time. Do not merely describe a plan when the user has authorized repository work; perform the scoped work and verify it.

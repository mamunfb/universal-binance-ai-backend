# GitHub Actions Configuration Inventory — QA Branch

Date: 2026-11-21  
Repository: `mamunfb/universal-binance-ai-backend`  
Working branch: `fix/backend-dashboard-static-assets`

## Scope and safety

This is a configuration inventory for the six workflow files inspected and backed up on this branch. It is not yet a claim that every workflow in the repository has been discovered; the complete `.github/workflows/` directory listing still needs a repository-tree audit.

No GitHub Secret values, tokens, database credentials, production settings, or deployment settings are stored in this document.

The six original workflow files currently exist in `.github/workflows/`. Each was fetched from this branch and compared byte-for-byte with its dated backup. All six matched exactly. No restore operation was necessary.

## Workflow files verified

| Workflow | Original file present | Backup present | Original matches backup |
|---|---:|---:|---:|
| dashboard-browser-qa.yml | Yes | Yes | Yes |
| dashboard-frontend.yml | Yes | Yes | Yes |
| dashboard-live-integration-qa.yml | Yes | Yes | Yes |
| dashboard-performance-qa.yml | Yes | Yes | Yes |
| hourly-market-scan.yml | Yes | Yes | Yes |
| tests.yml | Yes | Yes | Yes |

Backup directory: `.github/workflow-backups/2026-11-21/`

## Configuration references found in the six inspected workflows

### GitHub Actions Secrets

| Name | Referenced by | Purpose | Current status / next action |
|---|---|---|---|
| `DATABASE_URL` | `hourly-market-scan.yml` | PostgreSQL connection used by the scheduled/manual market scan | Required by this workflow. Confirm intended Neon project and branch before creating a replacement. Never put the value in this document. |
| `DASHBOARD_QA_BEARER_TOKEN` | `dashboard-live-integration-qa.yml` | Optional authenticated QA request | Existing name was observed in GitHub UI. User intends a clean rebuild; decide whether to recreate a new least-privilege QA token or leave authenticated checks disabled. Do not reuse or expose an unknown old value. |

### GitHub Actions Variables

| Name | Referenced by | Purpose | Value observed in GitHub UI |
|---|---|---|---|
| `DASHBOARD_PREVIEW_URL` | `dashboard-live-integration-qa.yml` | Dashboard preview base URL | `https://7e74d124.universal-binance-ai-backend.pages.dev/` |
| `RENDER_BACKEND_URL` | `dashboard-live-integration-qa.yml` | Staging backend base URL | `https://universal-binance-ai-backend-staging-qa.onrender.com` |

The workflow also supports `workflow_dispatch` inputs for dashboard/backend URLs and has fallback defaults. Confirm current deployed endpoints before treating these observed values as authoritative for a future run.

## Workflows with no Secret/Variable references found

In the inspected versions of these files, no GitHub Actions Secret or Variable references were found:
- `dashboard-browser-qa.yml`
- `dashboard-frontend.yml`
- `dashboard-performance-qa.yml`
- `tests.yml`

This statement applies only to these inspected file contents.

## Clean-rebuild plan

1. Keep all six original workflow files and dated backups unchanged while configuration is reviewed.
2. Complete a repository-tree audit to identify any additional workflow YAML files.
3. Confirm the correct Neon project and branch for the non-production QA/scheduled scan database.
4. Create or rotate only the required Secrets after their source and purpose are confirmed.
5. Recreate only the required Variables after confirming the current preview and staging URLs.
6. Validate each workflow independently, starting with safe non-production QA workflows.
7. Do not run the scheduled market scan until the database target and data impact are understood.
8. Do not modify `main`, merge a pull request, deploy Production, or change production/database settings as part of this QA task.

## Important limitations

- GitHub does not reveal an existing Secret's plaintext value in the update form. A blank field is not evidence that the stored value is empty or invalid.
- The presence of a Secret name does not prove its value works.
- `NEON_STAGING_TEST_DATABASE_URL` was not found in these six workflow files. This does not establish whether it is referenced elsewhere in the repository.
- No workflow has been executed as part of this inventory.
- No Secret or Variable has been created, updated, or deleted as part of this inventory.


## Neon QA database discovery (read-only inspection)

A Neon project matching the repository was found:
- Project name: `universal-binance-ai-backend`
- Project ID: `super-cake-99451662`
- Region: `aws-ap-southeast-1`
- PostgreSQL: 17
- Project permission: ADMIN

The project currently reports three branches:
- `main` — default branch, ID `br-damp-brook-b36a0bbm`
- `render-staging-backend` — non-default branch, ID `br-royal-thunder-b3ispxh9`
- `mcp-migration-2026-11-13T17-30-18` — non-default branch, ID `br-divine-sea-b3gsjfrq`

The `render-staging-backend` branch was inspected using a read-only branch description. It is ready, non-default, and contains the `neondb` database with application tables including `aggregate_trades`, `historical_klines`, `market_scan_runs`, `order_book_samples`, and other market/derivatives/EVM tables.

**Important:** `render-staging-backend` is a plausible QA/staging database target because of its name, but this inspection alone does not prove that `DATABASE_URL` or the hourly market scan is intended to use it. Do not create or set `DATABASE_URL` until the target branch and intended workload are confirmed. The default `main` branch must not be selected for QA merely because it is the default.

No connection string was retrieved. No database rows or schema were modified. No branch, compute, role, or credential was created, changed, or deleted.

---
name: neighbor-project
description: Develop, debug, verify, and operate the Neighbor NYC invitation-only community app in the banglahub repository. Use for this project's Next.js/FastAPI features, PostgreSQL and Neo4j synchronization, Google Forms intake, hosted Neon/Aura setup, or AWS release work. Does not apply to unrelated repositories.
---

# Neighbor NYC project workflow

Work from the repository root containing `AGENTS.md`, `backend/`, and `infra/`. Paths below are relative to that root, not this skill directory. Read `AGENTS.md` and `README.md` first; preserve existing user edits and follow the repository's branch/PR checks before editing. The GitHub repository is `IshaRedohy/neighbor-NYC-beta`; the local folder is named `banglahub`.

## Route the task

- Frontend: `app/`, `components/`, and `lib/`. Read the relevant installed guides under `node_modules/next/dist/docs/` before code changes. Local Next.js proxies `/api/*` to FastAPI; the hosted static export sends `/api/*` through CloudFront. Preserve both paths.
- API/domain behavior: `backend/main.py` and the relevant auth, intake, messaging, community, preferences, or signup module. Inspect callers and shared types in `lib/` when changing response shapes.
- Discovery and graph: read `docs/GRAPH.md`; inspect `backend/graph.py`, `backend/taxonomy.py`, and the SQL ranking path. Keep graph and SQL fallback eligibility, normalization, ordering, and explanations consistent.
- Schema or hosting: read `docs/AWS_DEPLOYMENT.md` and `docs/GRAPH.md` before setup or deployment. SQL migrations live in `db/`; hosted helpers live in `scripts/`; AWS CDK lives in `infra/`; release/check workflows live in `.github/workflows/`.
- Forms intake: read `docs/GOOGLE_FORMS_LOCAL_WALKTHROUGH.md` and `docs/GOOGLE_FORMS.md`; Apps Script lives in `google-forms/Code.gs`. Keep imports idempotent and approval separate from authentication.
- Verification: read `docs/TESTING.md` for commands, evidence and pending acceptance checks. Historical passes are not evidence for a new change.

## Preserve the application's contracts

PostgreSQL owns members, roles, approvals, sessions, messages, community data and the transactional outbox. Neo4j is a rebuildable projection. Use the application's synchronization workflow rather than hand-editing member projections; never remove pending SQL outbox records to hide failures. Graph failure or lag must retain the SQL fallback.

Apply current SQL membership, visibility, suspension and blocking rules before exposing profiles, posts, recommendations or conversations. Preserve host/member separation, first-message acceptance, participant checks, duplicate-safe message retries, bounded pagination and existing polling behavior when touching those flows.

Keep emails, optional street addresses, messages and credentials out of the graph. ZIP distances and neighborhood labels are approximate. Cultural identity is self-described and optional; preserve explicit filters and the saved opt-in tie-breaking preference. Keep occupation/skill normalization shared through the reviewed taxonomy.

The beta uses Google OAuth and approved Forms intake; Cognito native signup is gated by `NATIVE_SIGNUP`. Preserve state/nonce/PKCE and identity binding. Email equality alone must not link accounts. Additional provider skills do not authorize an authentication or hosting migration.

## Select tools and environments deliberately

Use the integration inventory in `AGENTS.md` to discover relevant MCP tools and plugin skills. Inspect supported alternatives before asking the owner for manual work. Distinguish tools exposed now, authenticated resource access, owner-reported results and unperformed checks. Do not provision a service just to compensate for a missing inspection tool.

Read current project/branch/instance IDs and dated status from `docs/AWS_DEPLOYMENT.md`; do not assume historical provisioning status remains current. Confirm the target environment and database identity before writes. This skill does not authorize cloud provisioning, migrations, data transfer or deployment by itself. Tools marked `destructiveHint: true` require explicit user approval.

- Local `.env` stays on Docker. Preserve separate ignored `.env.hosted.staging`, `.env.hosted.beta`, and any rehearsal file. Never print populated files, connection strings or private exports.
- Keep ordinary development and staging synthetic. Rehearse hosted schema changes on an isolated branch of the synthetic staging project, recording Neon project/branch IDs separately from the Git branch.
- Runtime uses pooled `DATABASE_URL`; migrations/backups use direct `DIRECT_DATABASE_URL`. Both must select the same intended branch/database. Use `.venv/bin/python scripts/hosted.py migrate --env-file <target-file>` for authorized hosted migrations.
- Reuse the recorded Aura instance after confirming identity. MCP HTTPS endpoints differ from the app's `neo4j+s://` driver URI. A rebuild replaces `Person` nodes; confirm a dedicated target and stop the worker before an authorized rebuild.
- For AWS work, verify account, role, region and stage resources first. Follow the maintained CDK/release workflow. Inspect secret metadata without retrieving values unnecessarily; secret changes require runtime refresh as described in the deployment guide.

## Verify the affected behavior

Choose checks proportional to the change and inspect script behavior before running operations that write data:

- Frontend changes: `npm run typecheck` and the relevant build (`npm run build` for the normal app, `npm run build:static` for hosted export). Use the Browser skill for changed interactions and visual behavior.
- Backend changes: `.venv/bin/python -m unittest discover -s backend/tests -p 'test_*.py'`. For integration coverage, start `docker compose -f compose.test.yaml up -d --wait`, then run `scripts/test-integration.sh`; never redirect these tests at normal member databases.
- Infrastructure changes: `npm --prefix infra run typecheck` and `npm --prefix infra test`; use the deployment guide and CI workflow for synthesis/image/release checks when relevant.
- Migration, backup or transfer changes: use the isolated synthetic migration/restore checks in `docs/TESTING.md`. Do not test restoration over a running database or transfer real members into staging.
- Documentation-only changes: review references, commands and the diff; validate skill metadata when editing this skill. Application builds are unnecessary unless application behavior changes.

Report the resulting behavior or files, the checks actually run, and any material verification gap. Keep credentials, private data and unrelated edits out of commits; do not push, deploy, or change infrastructure merely to finish a documentation task.

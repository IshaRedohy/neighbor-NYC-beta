# Private beta deployment

This is the first-time hosted setup guide. **As of 2026-11-10, the Neon staging and beta databases exist, and the connected Neo4j Aura database is online. Application database setup is incomplete; the hosted beta is not ready.** The GitHub repository and local Docker databases already exist. AWS application deployment remains pending in this guide and was not reverified during the database checks.

The repository contains the Lambda/static-site deployment, gated native signup, and release workflows. Complete the remaining database setup below, then deploy staging and prepare beta. Start with a CloudFront address; a custom domain is optional later.

## Verified database status — 2026-11-10

| Resource | Verified state | Remaining work |
| --- | --- | --- |
| Neon staging | `neighbor-staging`, project `cool-art-99004516`, default branch `main` / `br-rapid-feather-bc4nv25p`, database `neighborhub`; PostgreSQL 17 in `aws-us-east-1`; Organization subscription is Launch; six-hour restore history. Pooled/direct connections passed owner-run Mac terminal tests. Neon MCP verified five applied migrations, 18 public tables, 211 ZIP rows, zero members, and no unvalidated constraints. | Deploy and validate staging with synthetic test identities only. |
| Neon beta | `neighbor-beta`, project `holy-shape-80322126`, default branch `main` / `br-dark-poetry-bbktm2s8`, database `neighborhub`; PostgreSQL 17 in `aws-us-east-1`; Launch subscription with 604,800 seconds (seven days) of restore history verified through Neon MCP. Pooled/direct connections passed owner-run Mac terminal tests. Neon MCP verified five applied migrations, 18 public tables, 211 ZIP rows, zero members, and no unvalidated constraints. | Migrate/reconcile beta member data after staging validation; configure graph sync. |
| Neo4j beta | Instance `869db2f9`, database `neo4j`. Owner reports console name `Neighbor_NYC_beta`, status `RUNNING`, AuraDB Professional, AWS `us-east-1`, and the matching driver URI. Owner ran the saved-credential Python test in a normal Mac terminal and reported both `Connectivity: PASS` and `Database query: PASS`. Earlier MCP inspection found no data or constraints. | Initialize constraints and synchronize through the application workflow; verify connectivity from the deployed AWS runtime. |
| Hosted configuration | Both `.env.hosted.staging` and `.env.hosted.beta` exist, are Git-ignored, and have mode `0600`. Matching pooled/direct Neon URLs, four distinct session/intake secrets, and existing local Google OAuth credentials/form ID are populated. Working beta Aura credentials were preserved; staging has no Aura credentials. | Replace `APP_URL` placeholders after deployment and register actual hosted OAuth origins/callbacks. Upload configuration to AWS Secrets Manager during deployment. Configure Apps Script's matching intake secret only if enabling webhook delivery. |

The Aura driver URI is `neo4j+s://869db2f9.databases.neo4j.io`, username `neo4j`, database `neo4j`. No passwords belong in this document. The local `.env` still targets Docker. The older credential download for instance `b0b5b4c8` is a different instance and must not be substituted.

The agent's direct Python driver attempt failed at hostname resolution, before authentication. The owner subsequently ran the supplied test in a normal Mac terminal using `.env.hosted.beta`: `verify_connectivity()` passed, and `RETURN 1 AS connected` against database `neo4j` returned the expected value. **Local driver verification is complete, based on the owner's reported output.** This does not verify connectivity from the deployed AWS runtime. Aura plan/region metadata above is owner-supplied console information; the database MCP does not expose that metadata.

### Next steps, in order

1. **Complete (owner-supplied console details):** Aura instance `869db2f9` is `Neighbor_NYC_beta`, `RUNNING`, AuraDB Professional on AWS `us-east-1`. Reuse this instance. The Professional tier replaces the original Free-tier assumption; staging needs no graph instance.
2. **Complete (owner-run Mac terminal test):** Saved credentials passed `verify_connectivity()` and `RETURN 1 AS connected` against database `neo4j`. Both reported PASS. Repeat the check from the deployed AWS runtime during hosted validation.
3. **Complete for pre-deployment configuration:** Neon MCP confirmed Launch and seven-day beta retention. Both hosted environment files are populated, with four unique session/intake secrets and the existing Google OAuth client reused. Owner-run tests passed for all four Neon connections (staging/beta, pooled/direct). `APP_URL` and hosted OAuth callback registration remain deployment-dependent; OAuth login itself has not been validated on a hosted URL.
4. **Complete — schema migrations:** The owner ran the repository helper twice on isolated synthetic staging, then once each on staging and beta main branches. Neon MCP independently verified migrations `001_initial` through `005_graph_v3`, 18 public tables, 211 ZIP rows, zero members, and no unvalidated constraints on both target databases. Schema migrations did not copy local member data.
5. Deploy and validate staging with the graph disabled. Prepare beta data using section 3, then initialize graph constraints and drain the SQL outbox through the application's sync workflow. Do not manually seed member projections or run a destructive rebuild against an unconfirmed target.
6. Finish hosted connection/sync checks, backups and a restore drill, and the launch acceptance checks before inviting beta members.

### Migration rehearsal verified

The Neon MCP created `migration-rehearsal-2026-11-10` in synthetic staging project `cool-art-99004516`, from parent `br-rapid-feather-bc4nv25p`. Rehearsal branch: `br-steep-lake-bcu5d5ln`; compute: `ep-floral-cloud-bc2jv4e9`, fixed at 0.25 CU with plan-default autosuspend. Git branch at preparation: `docs/neon-provisioning-status`, HEAD `769937cbe35b3e2d4447c2b753fb641bc7eb4ad4` (deployment guide has additional local edits).

The separate `.env.hosted.rehearsal` file is populated with this branch's pooled/direct URLs, Git-ignored, and mode `0600`. Staging/beta connection files are unchanged. Parent staging inspection found no public application tables before branching.

**Rehearsal completed:** the owner ran the repository helper twice successfully. Neon MCP independently confirmed all five migration records (`001_initial` through `005_graph_v3`), 18 public tables, 211 ZIP rows (matching the bundled reference count), and zero members. The schema diff against the empty staging parent contains the expected added tables, indexes, constraints, and graph-sync function/trigger. Staging and beta main-branch migrations were subsequently applied by the owner and independently verified through Neon MCP with the same five migration records, 18 tables, 211 ZIP rows, zero members, and no unvalidated constraints. The commands used were:

```sh
.venv/bin/python scripts/hosted.py migrate --env-file .env.hosted.rehearsal && \
.venv/bin/python scripts/hosted.py migrate --env-file .env.hosted.rehearsal
```

The helper always refreshes ZIP reference rows, so the second run is expected to skip already-recorded schema migrations while refreshing that reference. Migration records and schema differences were inspected through Neon MCP before applying to staging/beta. Both target databases have now been verified after migration. Keep the rehearsal branch for verification; remove it later after review rather than deleting it automatically.

### Verification and remaining limits

The owner supplied the Aura console details and successful local Python driver output. The owner also reported all four Neon checks passing from a normal Mac terminal:

```text
staging DATABASE_URL: PASS
staging DIRECT_DATABASE_URL: PASS
beta DATABASE_URL: PASS
beta DIRECT_DATABASE_URL: PASS
```

These checks used the saved environment files and read-only queries. The agent environment still failed DNS resolution; the successful local results are owner-reported. Staging/beta schema migrations are verified through Neon MCP. AWS runtime connectivity, hosted OAuth, member data transfer, and graph synchronization remain unverified. No AWS secret uploads have been performed in this setup work.

Neon MCP reported both computes at **0.25–8 CU**, with `suspend_timeout_seconds=0` (plan-default autosuspend). This is the current setting, not a validated beta sizing recommendation; review the maximum before launch. Staging shares the organization's Launch subscription and retains six hours of history.

The owner successfully applied the schema to each intended environment with:

```sh
.venv/bin/python scripts/hosted.py migrate --env-file .env.hosted.staging
.venv/bin/python scripts/hosted.py migrate --env-file .env.hosted.beta
```

Run these from the repository root in a terminal with working Neon connectivity. Schema migration does not copy local members; section 3 describes the separate beta data migration.

## 0. Confirm account access

### AWS identity setup — 2026-11-14

AWS MCP verified account `418272785819` and initially authenticated as root. With explicit owner authorization, CloudFormation stack `Neighbor-DeploymentIdentity` was created in `us-east-1` and reached `CREATE_COMPLETE`. Its template is `infra/bootstrap/deployment-identity.json`; setup instructions are `infra/bootstrap/README.md`.

The stack creates IAM user `neighbor-deployer` with permission only to assume `arn:aws:iam::418272785819:role/NeighborDeploymentRole`. The role has initial access for Neighbor secrets/stacks and CDK assets, without AdministratorAccess or IAM-management permissions. CloudFormation validation passed, Access Analyzer returned no policy findings, and IAM simulation allowed the intended role while denying an unrelated role. These checks do not prove full deployment permissions.

No access keys or console passwords were created. The owner must establish non-root authentication and reconnect AWS MCP or configure the documented CLI profile. Current MCP authentication does not switch automatically when a role is created. CDK bootstrap/execution and release permissions, alert email, Lambda image build, staging secrets, and application deployment remain pending. The identity stack is not an application deployment; existing unrelated stacks were not changed.


Use the connected MCP servers for supported setup operations. OAuth connects the agent to your accounts; database creation, application credentials, and AWS deployment are separate steps in this guide.

| Service | Confirm before initial setup |
| --- | --- |
| Neon | Access to the existing beta and staging projects recorded above; confirm the selected branch before writes. |
| Neo4j | Owner supplied console details and a passing local driver test for `869db2f9`; verify deployed runtime connectivity later. |
| AWS | The intended AWS account, deployment role, and region for creating the application stacks. |
| GitHub | The intended repository, current branches, and relevant PRs and checks. Follow `AGENTS.md` to avoid branch conflicts and mixing unrelated changes into commits. |

If a server's tools are unavailable in the current session, resolve access or use an authenticated CLI/console for that step. Tool availability is separate from resource setup.

Keep local `.env` pointed at Docker. Hosted connections belong in separate ignored `.env.hosted.staging` and `.env.hosted.beta` files. Connecting MCP does not transfer local data; section 3 covers beta data migration.

## Architecture

CloudFront serves a private S3 static Next.js export and forwards `/api/*` to an HTTP API → FastAPI Lambda. APIs are never cached; cookies, query strings, Origin, redirects and Set-Cookie pass through. The browser uses one HTTPS origin. There is no VPC or NAT gateway.

PostgreSQL is authoritative. Use Neon Launch in AWS us-east-1, PostgreSQL **17**, with its paid restore history configured. Use the pooled URL for Lambda, the direct URL for migrations and backups. [Neon connection pooling](https://neon.com/docs/connect/connection-pooling).

Neo4j Aura is a rebuildable projection. The existing beta instance uses AuraDB Professional on AWS us-east-1, per the owner; the original plan assumed Aura Free. A disabled/paused/unavailable graph falls back to PostgreSQL. SQL eligibility and the same canonical matching vocabulary apply to both engines. A SQL outbox, SQS notification, bounded sync Lambda, hourly recovery and dead-letter queues handle missed or failed sync. Staging sets `GRAPH_ENABLED=false`; CI uses a separate Neo4j container. [Aura plans](https://neo4j.com/pricing/).

## 1. Create the databases

1. Reuse the existing Neon beta project above: **Launch**, us-east-1, PostgreSQL 17, and seven-day restore history are verified. Autosuspend uses the plan default; review the current 0.25–8 CU range for beta sizing. The AWS stack cannot enforce provider billing/recovery settings.
2. Reuse the **separate staging project** recorded above with synthetic data. Do not branch staging from the live member database. Staging currently shares the Launch organization subscription; keep its data synthetic and beta recovery enabled.
3. Copy each project's pooled and direct connection strings for the **same selected branch/database** (both require `sslmode=require`, or `verify-full`). Store the pooled URL as `DATABASE_URL` and the direct URL as `DIRECT_DATABASE_URL`, the exact names used by this repository. If a provider tool exports `DATABASE_URL_UNPOOLED`, map it to `DIRECT_DATABASE_URL` in the hosted file. Do not add these values to Git.
4. Reuse Aura instance `869db2f9` (`Neighbor_NYC_beta`, AuraDB Professional, AWS us-east-1, per owner confirmation). Local Python driver verification has passed. Save its `neo4j+s://` driver URI, username as `NEO4J_USER`, and password as `NEO4J_PASSWORD` locally. The backend targets database `neo4j`. This is for beta; staging needs no graph instance. Free instances may pause; do not add keepalive traffic. MCP tool authentication and the app's driver connection are separate setup steps; see the [Neo4j MCP quickstart](https://neo4j.com/docs/mcp/current/quickstart/).
5. Copy `.env.hosted.example` only for missing hosted files. `.env.hosted.beta` already contains Aura credentials; preserve those values. Fill the corresponding connections. Keep the local `.env` unchanged.
6. **Already populated:** two different random secrets per environment (four distinct values total). Preserve them during ordinary setup. For a new environment, generate each secret separately:
   ```sh
   .venv/bin/python -c 'import secrets; print(secrets.token_hex(32))'
   ```
   Put one in `SESSION_SECRET`, another in `INTAKE_SECRET`. The intake secret must also match Apps Script if enabling webhook delivery. Manual JSON import does not require delivery.
7. Existing Google OAuth client credentials and form ID are populated in both hosted files. Use a separate Google OAuth client for staging if practical. `APP_URL=https://replace-after-deploy.cloudfront.net` is only a first-deploy placeholder.

The files are ignored. Use the helper to upload configuration without placing passwords on command lines:

```sh
.venv/bin/python scripts/hosted.py secret --env-file .env.hosted.staging --secret-name neighbor/staging
.venv/bin/python scripts/hosted.py migrate --env-file .env.hosted.staging
```

Save the returned secret ARN. Use an IAM deployment role/SSO profile, not root credentials. The stack grants runtime Lambdas only secret read, queue access, and backup bucket writes as appropriate.

For development or migration rehearsals on Neon, use an isolated branch of the synthetic staging project and a separate ignored environment file. Record both the Git branch and Neon project/branch IDs; they are separate selections. Ordinary Neon branches include their parent's data, so do not use a live-member branch for routine staging tests. Review the schema diff and apply repository migrations to the intended release database explicitly; a Git merge does not migrate it. See [Neon branching](https://neon.com/docs/introduction/branching).

### Lambda concurrency on this account

Staging and beta use shared, unreserved Lambda concurrency so they can deploy with the account's current 10-execution limit in us-east-1. No function sets `ReservedConcurrentExecutions`; this avoids the requirement to leave 100 executions unreserved when allocating function reservations. The SQS graph event-source mapping remains capped at two concurrent invocations. Scheduled recovery invocations are separate from that mapping limit.

The account limit is shared with other applications. API calls, sync and backups may compete for capacity and experience throttling; there are no dedicated per-function capacity guarantees or per-function concurrency caps. Existing SQS retries, dead-letter queues, hourly recovery, and error alarms remain in place. Monitor throttles and backlog after deployment. An approved account quota increase provides headroom but does not automatically add function reservations or provisioned concurrency.

## 2. Check and deploy staging

Required tools: Docker, Node 22+, Python 3.12, AWS CLI and a configured deployment role. CDK and dependencies are pinned in `infra/package-lock.json`.

```sh
npm ci
npm ci --prefix infra
npm run build:static
npm --prefix infra test
mkdir -p .artifacts
cd infra
npx cdk bootstrap
npx cdk deploy Neighbor-staging -c stage=staging --parameters AppSecretArn=YOUR_SECRET_ARN --parameters AlertEmail=YOUR_EMAIL --outputs-file ../.artifacts/outputs.json
cd ..
```

The stack creates a CloudFront address; it does not publish private local files. Build uses an allowlisted staging directory, excluding `.env`, API proxy routes and response exports. The Lambda image contains backend code, migrations and the public ZIP reference only. Image dependencies are Linux x86-64, not the local macOS virtual environment.

Before calling the API:

1. Read `AppUrl` from `.artifacts/outputs.json`. Set it as `APP_URL` in the staging secret file and upload the secret again.
2. In Google's OAuth Web client, add **that exact origin** and redirect URI `https://YOUR-DISTRIBUTION.cloudfront.net/api/auth/callback`. Keep the localhost URI for local work.
3. Keep Google's test-user audience limited to invited testers while in testing mode. Add their accounts as needed.
4. Publish the frontend and smoke-test it:
   ```sh
   STAGE=staging .venv/bin/python scripts/release.py publish
   ```
5. Confirm the SNS subscription email and budget notifications. There is intentionally no frequent health-check schedule.

Secrets are read on cold start. After subsequent secret changes, recycle all affected Lambda execution environments with a configuration update/redeployment; changing Secrets Manager alone does not refresh warm clients. `scripts/refresh-runtime.py` does this using the saved stack outputs.

For the empty staging database, create the host explicitly:

```sh
.venv/bin/python scripts/hosted.py bootstrap --env-file .env.hosted.staging --email YOUR_GOOGLE_EMAIL
```

Beta migration already preserves your existing host; do not bootstrap ordinary members.

Staging demo login remains **off**. Use approved synthetic Google test profiles to exercise the hosted journey; never copy real member data into staging.

## 3. Prepare beta data

Run the same deployment with `stage=beta`, a different Neon project, different secret ARN, and Aura credentials. First apply migrations to the target with `scripts/hosted.py migrate`. Pause local writes for the migration snapshot.

```sh
.venv/bin/python scripts/migrate-data.py --source-env .env --target-env .env.hosted.beta
```

This refuses a target that already has members, copies real members and their related conversations/posts in one transaction, retains UUIDs, approval statuses and roles, and excludes demo members. Sessions and OAuth state are not transferred. Pending form submissions must be re-imported from the original private export; native signup should remain disabled until after this migration. The graph is regenerated from the SQL outbox. Reconcile member counts and host roles before inviting anyone. Keep the original database backup until the hosted restore drill passes.

Manual Forms intake still works: download the private Apps Script JSON → host imports under Manage community → approve → copy invitation. Members use their submitted Google account. `bootstrap-admin` is only for the owner, never ordinary members.

## 4. Backups, monitoring, and rollback

- Daily Lambda `pg_dump` uses the **direct** Neon endpoint and uploads an encrypted dump to a private S3 bucket. Retention is 30 days. PostgreSQL client is pinned to 17; choose Neon 17 or update/test the image before using a newer server.
- Neon paid restore history supplements the logical backup. Set it in Neon; it is not provisioned by CDK.
- CloudWatch alarms cover API/sync/backup invocation errors, missing daily backup, old queue messages, and both DLQs. App service failures also emit safe stage/type logs. Logs expire after 14 days; access logs contain request ID, status and latency, never query strings, cookies or request bodies.
- AWS budget notifications are set at $20/$35/$50 for total AWS account cost. **They exclude Neon billing, are not spending caps, and may include other AWS projects.** Enable Neon usage alerts separately. The $15–50 target is not a guarantee; polling can keep SQL compute active.
- Test a restore **before inviting five people**: invoke the Backup function once, download that dump to a private local folder, restore into a separate Neon recovery branch/project using `PGDATABASE` in the environment and `pg_restore --no-owner --no-acl --exit-on-error`, then compare member UUIDs/roles/status and message counts. Never restore over the running database during a drill.
- `scripts/restore-check.sh` demonstrates the same dump/restore process against isolated synthetic PostgreSQL. It does not prove the hosted Neon backup path until the hosted drill runs.
- Roll back an application release by rerunning the deployment workflow on a previously tested commit. S3 is versioned, and prior hashed assets are retained. Database migrations are additive; do not automatically drop columns on rollback. If data needs recovery, restore to a new branch and switch the secret only after validation.
- After an Aura outage, inspect the host pending count and DLQ. Hourly recovery processes the authoritative outbox even after SQS retries exhaust. If pending work persists, correct credentials/service availability and redrive the queue; never delete SQL outbox entries as a recovery shortcut.

## 5. GitHub deployment

`.github/workflows/checks.yml` builds the static frontend, validates CDK, runs isolated SQL/Neo4j tests, demonstrates restore, and builds the Linux image. `.github/workflows/deploy.yml` is a manually triggered deployment pipeline for `staging` or `beta`.

Create GitHub environments `staging` and `beta` with variables `AWS_ROLE_ARN`, `APP_SECRET_ARN`, `ALERT_EMAIL`. Configure the AWS role's OIDC trust for **this repository and the selected GitHub environment**, audience `sts.amazonaws.com`; permit only CDK bootstrap deployment roles, the corresponding app secret read, release bucket sync, CloudFront invalidation, and stack operations. Use GitHub environment protection for beta. Do not store AWS access keys in GitHub.

Run Checks successfully on the selected commit before Deploy. On the first deployment, complete the manual CloudFront/Google configuration above; subsequent runs migrate using the direct DB URL, deploy the image/stack, sync static assets, invalidate CloudFront, and smoke-test direct routes and unauthenticated access.

**Repository history:** a private response export was present in the initial commit. It is now removed from the index and ignored, but older history still contains it. Do not publish that history publicly; use a clean sanitized repository or perform a separately reviewed history cleanup before public publication. No history was rewritten automatically.

## 6. Native signup (disabled by default)

After the first hosted feedback, enable the prepared Cognito stack. It uses Essentials managed login, Google federation, email OTP, PKCE, nonce validation and one-use state. The app never creates, receives, or stores email OTP codes. [Cognito authentication methods](https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-authentication-flow-methods.html).

1. Verify an SES sender/domain, request production email sending access, and configure DKIM and delivery/bounce monitoring. Do not turn on public email login while SES is still limited to verified recipients. [Cognito email configuration](https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-email.html).
2. Deploy `Neighbor-beta-Signup` with `-c stage=beta -c signup=true` and parameters `AppUrl`, `SesIdentityArn`, `EmailFrom`, `AppSecretArn`. No other stack needs to be redeployed for Cognito outputs.
3. Add `https://YOUR-COGNITO-DOMAIN/oauth2/idpresponse` to the Google OAuth client's redirect URIs. Keep the app's original Google callback for migration/account linking.
4. Copy the Cognito issuer/domain/client ID outputs into `.env.hosted.beta`, set `NATIVE_SIGNUP=true`, upload the secret, and refresh runtime configuration.
5. Existing members first use the original Google login, then **My profile → Link Google or email-code login**. Linking requires their active member session plus a fresh verified provider login. Matching an email alone never links two provider identities. New applicants verify identity, complete the app form, and wait for host approval; they cannot access member or admin endpoints.
6. Exercise expired/cancelled/reused login flows, email delivery failures, provider linking conflicts and migrated member roles on staging before enabling beta. Codes expiring/reuse are enforced by Cognito and still require live hosted acceptance tests.
7. Keep JSON imports during transition; retire the public form only after this flow works with real invited users.

## Launch acceptance

Start with five people on the hosted domain: ordinary login/admin denial; wrong account/pending/suspended/expired states; approved import visibility; filtering and culture opt-in; two-person request/accept/reply/retry/older pages/unread/block/report; cold DB wake; unavailable graph; queue failure/recovery; backup restore; rollback. Then expand to 10–50. These hosted and provider-specific checks remain pending until configuration, migration, and deployment are completed.

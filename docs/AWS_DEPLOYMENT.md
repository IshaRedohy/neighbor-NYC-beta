# Private beta deployment

This is the first-time hosted setup guide. **As of 2026-11-10, the Neon staging and beta databases exist, and the connected Neo4j Aura database is online. Application database setup is incomplete; the hosted beta is not ready.** The GitHub repository and local Docker databases already exist. AWS application deployment remains pending in this guide and was not reverified during the database checks.

The repository contains the Lambda/static-site deployment, gated native signup, and release workflows. Complete the remaining database setup below, then deploy staging and prepare beta. Start with a CloudFront address; a custom domain is optional later.

## Verified database status — 2026-11-10

| Resource | Verified state | Remaining work |
| --- | --- | --- |
| Neon staging | `neighbor-staging`, project `cool-art-99004516`, default branch `main` / `br-rapid-feather-bc4nv25p`, database `neighborhub`; PostgreSQL 17 in `aws-us-east-1`; Free plan; zero public application tables. | Configure pooled/direct connections and run repository migrations. Use synthetic data only. |
| Neon beta | `neighbor-beta`, project `holy-shape-80322126`, default branch `main` / `br-dark-poetry-bbktm2s8`, database `neighborhub`; PostgreSQL 17 in `aws-us-east-1`; Free plan with 21,600 seconds (six hours) of restore history; zero public application tables. | Upgrade to the guide's Launch plan and configure seven-day restore history, then configure connections, migrate schema, and migrate/reconcile beta data. |
| Neo4j beta candidate | MCP endpoint identifies Aura instance `869db2f9`; database `neo4j` is online, empty, and has no constraints. Matching credential download names it `My instance`; this is a saved name, not a current console verification. | Verify current name, plan, cloud provider and region in Aura; verify app driver connectivity; initialize constraints and synchronize through the application workflow. |
| Hosted configuration | `.env.hosted.beta` exists, is Git-ignored, and has mode `0600`. Matching Aura URI, `NEO4J_USER`, and password were saved from the instance's credential download. | Other beta fields remain template placeholders or defaults. `.env.hosted.staging` still needs creating. Complete both files before uploading secrets or running migrations. |

The Aura driver URI is `neo4j+s://869db2f9.databases.neo4j.io`, username `neo4j`, database `neo4j`. No passwords belong in this document. The local `.env` still targets Docker. The older credential download for instance `b0b5b4c8` is a different instance and must not be substituted.

The direct Python driver check failed at hostname resolution (`Cannot resolve address 869db2f9.databases.neo4j.io:7687`), before authentication could be tested. This does **not** establish that the saved password is invalid or that Aura is offline: the separate MCP connection successfully reached the database. The available Neo4j MCP tools expose database queries, not Aura account provisioning, plan or region metadata. The in-app browser failed to initialize, so console verification was unavailable.

### Next steps, in order

1. In the Aura console, select instance `869db2f9` and confirm its current name, status, plan/tier, cloud provider, region, and driver URI. Reuse this instance if suitable; do not create a duplicate merely because application setup is unfinished. The intended setup is AuraDB Free near us-east-1 where offered. Staging needs no graph instance.
2. Retry the Python driver from a terminal/network that can resolve the confirmed hostname and connect to its Bolt endpoint on port 7687. Load credentials from `.env.hosted.beta`; call `verify_connectivity()` and execute `RETURN 1 AS connected` explicitly against database `neo4j`. Record success only after both pass. If DNS still fails, investigate DNS/network access and compare the URI with the console. Reset credentials only if a subsequent authentication error warrants it.
3. Complete Neon beta plan/recovery settings and both hosted environment files using the existing projects and exact branch IDs above. Preserve the current beta Aura credentials when filling the other fields. Generate separate session/intake secrets for each environment and configure OAuth as described in section 1.
4. Rehearse schema changes on an isolated branch of synthetic staging, then apply repository migrations to the selected staging and beta databases with `scripts/hosted.py migrate`. Verify tables and migration status. Do not copy real member data to staging.
5. Deploy and validate staging with the graph disabled. Prepare beta data using section 3, then initialize graph constraints and drain the SQL outbox through the application's sync workflow. Do not manually seed member projections or run a destructive rebuild against an unconfirmed target.
6. Finish hosted connection/sync checks, backups and a restore drill, and the launch acceptance checks before inviting beta members.

### Information needed from the owner

- For instance `869db2f9`, provide the console's current **name, status, plan/tier, cloud provider, region, and driver URI** as text or a screenshot with secrets hidden. This supplies metadata that the database MCP cannot report.
- No password needs to be pasted into chat: the matching downloaded credentials are already saved locally. To finish the driver check, a working DNS/network path is needed. If this agent environment still cannot resolve the hostname, run the credential-loading Python check in a normal local terminal and share only its success or sanitized error. A successful MCP query alone is not an app-driver test.

## 0. Confirm account access

Use the connected MCP servers for supported setup operations. OAuth connects the agent to your accounts; database creation, application credentials, and AWS deployment are separate steps in this guide.

| Service | Confirm before initial setup |
| --- | --- |
| Neon | Access to the existing beta and staging projects recorded above; confirm the selected branch before writes. |
| Neo4j | Console verification of existing instance `869db2f9`, plus a successful application driver connection. |
| AWS | The intended AWS account, deployment role, and region for creating the application stacks. |
| GitHub | The intended repository, current branches, and relevant PRs and checks. Follow `AGENTS.md` to avoid branch conflicts and mixing unrelated changes into commits. |

If a server's tools are unavailable in the current session, resolve access or use an authenticated CLI/console for that step. Tool availability is separate from resource setup.

Keep local `.env` pointed at Docker. Hosted connections belong in separate ignored `.env.hosted.staging` and `.env.hosted.beta` files. Connecting MCP does not transfer local data; section 3 covers beta data migration.

## Architecture

CloudFront serves a private S3 static Next.js export and forwards `/api/*` to an HTTP API → FastAPI Lambda. APIs are never cached; cookies, query strings, Origin, redirects and Set-Cookie pass through. The browser uses one HTTPS origin. There is no VPC or NAT gateway.

PostgreSQL is authoritative. Use Neon Launch in AWS us-east-1, PostgreSQL **17**, with its paid restore history configured. Use the pooled URL for Lambda, the direct URL for migrations and backups. [Neon connection pooling](https://neon.com/docs/connect/connection-pooling).

Neo4j Aura Free is a rebuildable projection. A disabled/paused/unavailable graph falls back to PostgreSQL. SQL eligibility and the same canonical matching vocabulary apply to both engines. A SQL outbox, SQS notification, bounded sync Lambda, hourly recovery and dead-letter queues handle missed or failed sync. Staging sets `GRAPH_ENABLED=false`; CI uses a separate Neo4j container. [Aura plans](https://neo4j.com/pricing/).

## 1. Create the databases

1. Reuse the existing Neon beta project above and upgrade it to **Launch**; it already uses us-east-1 and PostgreSQL 17. Set a seven-day restore window, autosuspend, and the smallest compute range suitable for the beta. Confirm current plan support and these settings in the provider console; the AWS stack cannot enforce them.
2. Reuse the **separate staging project** recorded above with synthetic data. Do not branch staging from the live member database. A free staging project is sufficient for fallback tests; production must have recovery enabled.
3. Copy each project's pooled and direct connection strings for the **same selected branch/database** (both require `sslmode=require`, or `verify-full`). Store the pooled URL as `DATABASE_URL` and the direct URL as `DIRECT_DATABASE_URL`, the exact names used by this repository. If a provider tool exports `DATABASE_URL_UNPOOLED`, map it to `DIRECT_DATABASE_URL` in the hosted file. Do not add these values to Git.
4. Verify and reuse Aura instance `869db2f9` if it meets the intended AuraDB Free setup near us-east-1 where offered. Save its `neo4j+s://` driver URI, username as `NEO4J_USER`, and password as `NEO4J_PASSWORD` locally. The backend targets database `neo4j`. This is for beta; staging needs no graph instance. Free instances may pause; do not add keepalive traffic. MCP tool authentication and the app's driver connection are separate setup steps; see the [Neo4j MCP quickstart](https://neo4j.com/docs/mcp/current/quickstart/).
5. Copy `.env.hosted.example` only for missing hosted files. `.env.hosted.beta` already contains Aura credentials; preserve those values. Fill the corresponding connections. Keep the local `.env` unchanged.
6. Generate **two different** random secrets for each environment:
   ```sh
   .venv/bin/python -c 'import secrets; print(secrets.token_hex(32))'
   ```
   Put one in `SESSION_SECRET`, another in `INTAKE_SECRET`. The intake secret must also match Apps Script if enabling webhook delivery. Manual JSON import does not require delivery.
7. Supply the existing Google OAuth client credentials and form ID. Use a separate Google OAuth client for staging if practical. `APP_URL=https://replace-after-deploy.cloudfront.net` is only a first-deploy placeholder.

The files are ignored. Use the helper to upload configuration without placing passwords on command lines:

```sh
.venv/bin/python scripts/hosted.py secret --env-file .env.hosted.staging --secret-name neighbor/staging
.venv/bin/python scripts/hosted.py migrate --env-file .env.hosted.staging
```

Save the returned secret ARN. Use an IAM deployment role/SSO profile, not root credentials. The stack grants runtime Lambdas only secret read, queue access, and backup bucket writes as appropriate.

For development or migration rehearsals on Neon, use an isolated branch of the synthetic staging project and a separate ignored environment file. Record both the Git branch and Neon project/branch IDs; they are separate selections. Ordinary Neon branches include their parent's data, so do not use a live-member branch for routine staging tests. Review the schema diff and apply repository migrations to the intended release database explicitly; a Git merge does not migrate it. See [Neon branching](https://neon.com/docs/introduction/branching).

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

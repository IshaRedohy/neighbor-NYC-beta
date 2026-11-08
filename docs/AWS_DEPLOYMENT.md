# Future AWS hosting: Lambda, not Lightsail

**Current decision: stay local until friends' testing data has been collected.** Nothing in this repository provisions AWS services. Google Forms is the only remote collection service required now; its responses can be imported into local PostgreSQL. This guide is a future deployment plan, not a claim that the current app has been cloud-tested.

Pricing checked September 27, 2026. Estimates use US East planning rates, USD, 730 hours/month, a small 100–500-member beta, and no promotional credits. Verify the chosen region and providers in their calculators before deployment.

## Is Lambda cheaper?

For intermittent API traffic, Lambda itself is inexpensive. At **100,000 requests/month, 512 MB, and 300 ms average execution time**, compute is 15,000 GB-seconds, about **$0.25**, plus **$0.02** in requests before free-tier allowances. HTTP API Gateway adds about **$0.10**. These are usage examples, not a measured performance forecast. [Lambda pricing](https://aws.amazon.com/lambda/pricing/), [HTTP API pricing](https://aws.amazon.com/api-gateway/pricing/)

PostgreSQL and Neo4j cannot run as persistent databases inside Lambda. Their hosting, backups, and networking can cost substantially more than the API. Replacing a small server with Lambda therefore does **not** guarantee a smaller total bill.

## Target architecture

```text
Browser → CloudFront → private S3 origin: exported Next.js frontend
                    → /api/*: API Gateway HTTP API → Python FastAPI on Lambda
                                                       ├─ PostgreSQL (Aurora)
                                                       └─ Neo4j AuraDB

Google Forms → signed HTTPS intake → same Python API → SQL outbox
SQL outbox → bounded, retryable graph-sync Lambda → Neo4j
```

- **Frontend:** This beta's UI is client-rendered, so the economical future deployment is Next.js static export to private S3 + CloudFront. Before exporting, replace the optional catch-all page with explicit `/`, `/discover`, `/messages`, `/profile`, and `/admin` pages; remove the Next.js API proxy and route `/api/*` directly to API Gateway through CloudFront. Add `output: 'export'` and verify deep-link handling. These are future edits: today's app intentionally uses the local proxy and is not currently an S3 upload artifact.
- **API:** Package `backend/` and Linux-compatible Python 3.12 dependencies for Lambda. `backend/lambda_handler.py` provides the Mangum handler. Start with 512 MB, a 20-second timeout, no provisioned concurrency, and a small reserved concurrency limit (for example, five) to protect SQL connection capacity. Benchmark and tune before increasing it. Do not package your Mac `.venv`.
- **PostgreSQL:** Use Aurora PostgreSQL Serverless v2 with an engine version that supports automatic pause at zero ACUs if infrequent-use savings are desired. Keep it private. Start with a small maximum capacity and alerts; startup latency after a pause may exceed this beta's five-second SQL pool timeout, so add bounded resume-aware retry and suitable timeouts before deploying. [Aurora pause/resume guidance](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2-auto-pause.html)
- **Graph:** Neo4j AuraDB Free can serve a constrained experiment after checking current quotas, availability, inactivity rules, and region. Use Professional for the first paid tier when appropriate. AuraDB is a Neo4j-managed service, optionally hosted in AWS; it is not an AWS-native Lambda database. [Neo4j plans](https://neo4j.com/pricing/)
- **Networking:** A VPC-connected API accessing private Aurora still needs a working outbound path to Google OAuth and a public Aura endpoint. Budget a NAT gateway in the straightforward deployment. Merely placing Lambda in a public subnet does not provide internet access. [AWS networking guidance](https://docs.aws.amazon.com/lambda/latest/dg/configuration-vpc-internet.html)
- **Background work:** Replace the local infinite worker loop with a bounded Lambda invocation. Trigger processing after committed profile mutations through a durable dispatch mechanism; retain the SQL outbox for recovery. Use SQS retries/dead-letter handling and a low-frequency reconciliation job. Never rely on an unawaited background task after an HTTP response.

The current five-second polling worker and open SQL connections would undermine Aurora auto-pause. Do not deploy that loop as-is. Reduce the pool size for Lambda, close idle SQL connections promptly, pause browser polling when tabs are hidden, and avoid health checks/reconciliation schedules that repeatedly wake the database. Document the expected tradeoff between stale graph projection and waking the database.

## Approximate monthly costs

Two Aurora compute scenarios: 0.5 ACU active for 150 hours/month (about $9), or 0.5 ACU active all 730 hours (about $43.80), using $0.12/ACU-hour. These assume the database actually stays at that capacity while active; automatic scaling can cost more. [Aurora pricing examples](https://aws.amazon.com/rds/aurora/pricing/)

| Item | Intermittent-use experiment | Continuously active small beta |
|---|---:|---:|
| Python Lambda, example usage above | $0.27 | $0.27 |
| HTTP API Gateway, 100k calls | $0.10 | $0.10 |
| Static frontend, CDN, build allowance | $1–5 | $1–5 |
| Aurora compute assumption | $9 | $43.80 |
| SQL storage, I/O, backup allowance | $2–5 | $2–5 |
| Neo4j graph | $0 Free, if suitable | $65.70 Professional 1 GB |
| One NAT gateway, hourly charge | $32.85 | $32.85 |
| One NAT public IPv4 address | $3.65 | $3.65 |
| Logs, secrets, queues, DNS, domain allowance | $3–8 | $3–8 |
| **Approximate total** | **$52–65/month** | **$152–164/month** |

NAT is estimated at $0.045/hour; public IPv4 at $0.005/hour. NAT data processing, internet transfer, extra AZs, endpoints, replicas, WAF, RDS Proxy, and unusual traffic are additional. The table's frontend/storage/operations ranges are planning allowances, not individual vendor quotes. Domain cost is amortized, though normally paid annually. [VPC pricing](https://aws.amazon.com/vpc/pricing/)

Neo4j Professional's listed entry price is $0.09/hour, or $65.70 over 730 hours. It has its own terms and availability characteristics; confirm the chosen AWS region. [Neo4j pricing](https://neo4j.com/pricing/)

Keeping the graph on the free tier in the second scenario brings that estimate to approximately **$87–99/month**. With private Aurora, the straightforward NAT arrangement alone is much larger than the Lambda bill. A managed Postgres provider reachable over TLS from a non-VPC Lambda can avoid that NAT setup, but changes the AWS-only database choice; compare provider limits and total costs before choosing. An AWS-only Data API architecture could also change networking costs, but requires replacing the current psycopg access layer and carefully validating transaction/latency behavior. Neither alternative is implemented here.

Free tiers may lower some actual charges, but the estimates deliberately do not depend on credits. Local development has **$0 AWS hosting cost**.

## Deployment sequence when you are ready

1. **Finish the local pilot.** Validate a real Google submission, approval, matching, Google sign-in, message request/acceptance/reply, blocking, and deletion. Get feedback on ZIP proximity and expertise labels. Decide the retention policy for Google responses, JSON exports, messages, and backups.
2. **Prepare a staging environment.** Create infrastructure as code only when hosting is requested. Use a dedicated AWS environment, least-privilege roles, Secrets Manager, HTTPS, budget alerts, and separate staging Google OAuth configuration. Restrict admin bootstrap access. Enforce `ENVIRONMENT=production` and `DEMO_MODE=false`; startup refuses production demo mode.
3. **Adapt for Lambda.** Make the frontend/static changes above. Forward all required HTTP methods, cookies, query strings, `Origin`, and intake signature headers through CloudFront. Disable caching on `/api/*`; preserve `Set-Cookie` and redirects. Block inappropriate methods/body sizes at the edge. Ensure error responses also stay uncached. Use one public hostname and set `APP_URL` to it.
4. **Prepare database access.** Configure TLS certificate validation, private security groups, low connection limits and concurrency, engine-compatible SQL migration testing, pause/resume retry, backup retention, and restore tests. Plan at least one staging migration through the same code path used in production.
5. **Migrate data.** Take an encrypted PostgreSQL backup; restore only intended pilot data into the staging/production database. Keep demo profiles excluded or remove them with a reviewed targeted migration. Rebuild Neo4j from SQL and verify relationship counts; do not migrate messages or emails into the graph. Preserve the original local dump for rollback.
6. **Wire the real integrations.** Add the production Google redirect URI `/api/auth/callback`, complete Google consent-screen requirements, update Apps Script's intake URL and secret, and check a signed test submission. Scheduled replay must remain idempotent. Rotate all example/development secrets.
7. **Test and observe.** Measure cold starts, paused-database recovery, request latency, graph downtime fallback, worker retries, dead-letter recovery, duplicate delivery, rate limits, and message authorization. Add monitoring for 5xx responses, failed OAuth callbacks (without token logging), SQL saturation, outbox age, queue dead letters, and spend. Alert on $10/$25/$50/$100 thresholds appropriate to the selected architecture.
8. **Release to a small invited group.** Check a rollback to the previous API/frontend versions and restore a backup into an isolated database before expanding. Maintain an accessible community-host contact route and deletion-request process.

## Improvements before larger scale

- Move candidate filtering and ranking into bounded SQL/graph queries with appropriate indexes; avoid reading the whole directory.
- Add cursor pagination for messages and conversations, and stop browser polling on hidden/inactive tabs. Consider an event-driven chat transport only when measured demand justifies it.
- Add audited moderation actions and stronger abuse controls; hash session tokens as now, expire sessions on security changes, and implement an incident-response process.
- Replace broad development CSP script allowances with a production nonce-based policy compatible with the chosen frontend hosting mode.
- Keep dependencies locked and scanned, test migrations on a restore, add CI, and run actual browser/accessibility checks. A local passing build is not a cloud-readiness certificate.

**Recommendation for today:** collect with Google Forms, import into the running local beta, and measure real usage before paying for any hosted databases.

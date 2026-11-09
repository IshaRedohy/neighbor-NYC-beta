# Verification record — November 8, 2026

This records the roadmap implementation, not a completed hosted launch. Real Neon/Aura services, CloudFront OAuth and SES delivery still require the setup in [AWS_DEPLOYMENT.md](AWS_DEPLOYMENT.md).

## Passed locally

- TypeScript checks, normal Next.js production build, and static export with explicit routes. The static build excludes the development API proxy and local environment files.
- **32 backend integration and unit tests** on Python 3.12, with **isolated** PostgreSQL 17 and Neo4j 5.26 containers. Tests refuse the normal application database and graph endpoint.
- Discovery eligibility/filtering, opt-in culture tie-breaking, reviewed occupation aliases, and actual Neo4j versus PostgreSQL recommendation parity.
- Ordinary member/admin separation; import idempotency and approval; hidden/deleted/suspended profiles; Google pending/wrong-account/suspended/temporary outcomes with mocked provider responses.
- Message request/acceptance/participant protection, blocking/reporting, bounded history pages, incremental cursors, unread boundary, sequential and simultaneous duplicate-safe retries, and identifier/content conflict rejection.
- Native applicant isolation and approval; provider identity mapping preserves member UUID and role; verified email alone cannot link accounts; repeated OAuth state is rejected. Google/Cognito token exchange is mocked in these tests; real OTP delivery/expiry is provider acceptance testing.
- Failed queue notification leaves committed work recoverable; bounded worker reports SQS failures; scheduled recovery failures are surfaced; production TLS configuration is enforced.
- CDK TypeScript checks, infrastructure assertions and full staging synthesis. Assertions include uncached API forwarding, private database-free Lambda networking, queue retries and budget thresholds. The optional Cognito template is also asserted.
- Linux x86-64 Lambda container build with pinned Python dependencies, pinned base-image digest, PostgreSQL 17 client. Its actual Mangum adapter passes production-mode `/api/config`, unauthenticated `/api/me` and admin denial, and disabled demo authentication smoke tests.
- Synthetic migration into a fresh database: real-designated profile IDs, fields and roles remain identical; relevant messages copy; demo accounts and sessions are excluded; graph outbox is recreated.
- PostgreSQL custom-format dump restored into a separate database. Member and message fingerprints match, including roles and approval statuses.
- A private backup of the local app database was saved. Additive local migrations were applied; existing member IDs/roles were not rewritten.

## Repeat locally

```sh
npm ci
npm ci --prefix infra
npm run typecheck
npm run build:static
npm --prefix infra run typecheck
npm --prefix infra test
docker compose -f compose.test.yaml up -d --wait
scripts/test-integration.sh
.venv/bin/python scripts/check-migration.py
scripts/restore-check.sh
docker build --platform linux/amd64 -f backend/Dockerfile.lambda -t neighbor-lambda:test .
docker compose -f compose.test.yaml down -v
```

The test stack uses ports 15432/17687 with temporary synthetic data. Integration startup resets only that guarded test database. The separate migration/restore databases are also inside the temporary stack. Never repoint these helpers at member data. GitHub Checks runs these operations and the Lambda smoke test.

## Still pending before hosted invitations

- Browser interaction and visual review: the Browser skill reported no available browser in this session. Builds and HTTP tests do not verify mobile layout, accessibility interactions or background-tab timing.
- Live Google callback on the CloudFront domain, including cookies, expected account choice, approval states and expired sessions.
- Hosted Neon sleep/wake and restore from the actual daily S3 dump; Aura pause/rebuild; SQS delivery/DLQ redrive; CloudWatch/SNS and provider spending alerts.
- An actual deployment and rollback on the selected AWS account. No stack has been deployed or paid service created during this implementation.
- SES sending approval, delivery failures, Cognito OTP expiry/reuse and real account linking before enabling `NATIVE_SIGNUP`.

## Browser acceptance checklist

Use isolated synthetic users for development/staging. On beta, use two invited accounts, not demo login.

1. Sign in as an ordinary member and try `/admin`; host data must not be accessible. Exercise pending, wrong account, suspended, expired and temporary service states.
2. Check discovery at mobile/desktop widths. Use every filter, all five recommendation sections, reset, zero results and shared-culture preference. Refresh to verify preference persistence. Hidden/blocked users must be absent.
3. Send a first-message request; accept/decline as the other account. Reply, load earlier messages and more conversations. Disconnect during sending, reconnect and retry: the recipient must see one copy.
4. Watch network requests: an open conversation polls every five seconds, other inbox checks are slower, hidden tabs do not start polling, and returning refreshes. Quickly change conversations during slow requests; no old conversation content/draft may appear under another recipient.
5. Open an old conversation through its direct link, even if it is outside the first inbox page. Check unread counts, blocking and reporting.
6. Import/re-import the same private form export, approve, copy the invitation and verify its hosted URL/email. No import or login may grant a host role.
7. After Cognito is enabled, new identities can submit a profile but cannot enter until approval. Existing members must authenticate both their current membership and the added login method; verify UUID/role preservation.

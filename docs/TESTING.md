# Verification record

Verified locally on September 27, 2026. The app remains local; no AWS resources, public tunnel, Google OAuth client, or Google Form were created in the user's accounts.

## Passed

- TypeScript checking and optimized Next.js production build.
- Python backend Docker image build using the pinned dependencies on Python 3.12.
- **16 automated tests**, including isolated PostgreSQL integration tests and live Neo4j integration. Passed on the Mac's Python environment and in the Python 3.12 backend container.
- An HTTP walkthrough through the actual running Next.js proxy: HTML routes, demo login, HttpOnly session cookie, member retrieval, Neo4j-backed discovery, email exclusion from public profiles, admin restrictions, and logout.
- PostgreSQL + Neo4j restart: the 12 original fictional member records persisted. The API connection pool now validates connections before reuse, fixing a stale-connection failure detected during this check. The HTTP walkthrough passed again after the fix and a further PostgreSQL restart.
- Backup script produced a private custom-format PostgreSQL dump; restoring it into a separate `neighborhub_restore_test` database recovered all 12 original member records.
- Docker Compose configuration validation and healthy database containers.

## Automated coverage

| Area | Scenarios |
|---|---|
| Intake | Required fields, tag normalization, invalid ZIP, age/consent rejection, duplicate response IDs, pending approval, existing-email resubmission isolation |
| Webhook | Correct HMAC, exact-body tampering, expired timestamps, idempotent replay |
| Access | Anonymous denial, wrong-origin mutation denial, member/admin separation, demo rejection in production mode |
| Google flow | Invalid state rejected; verified-but-unapproved Google account rejected using mocked Google responses |
| Discovery | Language/expertise filters, same-ZIP matching, geographic calculation, graph-down SQL fallback, private-email exclusion |
| Messaging | Initial request, no follow-up before acceptance, recipient-only acceptance, participant-only history, unread/read state, block enforcement in both directions |
| Moderation | Reports, suspension, session/access denial, restoration, report resolution |
| Profiles | Hidden profile denial, deletion/anonymization, session invalidation, queued graph changes |
| Graph | Real relationship creation, no login email in graph nodes, retry state after simulated outage, recovery, hidden-node removal and restoration |

The isolated `neighborhub_test` database retains fictional test rows between runs; each run rebuilds its projection and cleans up only graph nodes whose IDs belong to that test database. Tests refuse to use the main application database. `neighborhub_restore_test` is an intentionally separate restore-verification database. Neither contains friends' collected data.

## Not verified in this session

- **Visual/browser interaction walkthrough:** the installed Browser skill's runtime reported no available browser, including an empty browser list after its documented connection checks. HTTP tests do not verify React hydration, rendered layout, mobile behavior, or keyboard interactions. Perform the checklist below in a browser before inviting testers into the app.
- **Live Google account integration:** no user Google credentials were supplied. Apps Script syntax and the signed intake contract are implemented, but publishing the real form, authorizing Apps Script, completing Google OAuth, and observing a live submission remain account-setup steps.
- **Cloud deployment/load testing:** the Lambda handler and hosting guide are preparation only. No API Gateway, S3/CloudFront, Aurora, AuraDB, queues, or production configuration was deployed.

## Follow-up verification

After resuming work, the local API and both database containers were still healthy. A code review found an inbox race: a slow response from a previous conversation could populate the newly selected conversation, and drafts could carry between recipients. The frontend now cancels superseded loads, checks the selected conversation before committing results, resets drafts on switching, and waits for pending polls instead of repeatedly interrupting slow requests. Unavailable threads are cleared from the active view.

TypeScript checking, the production build, and the live HTTP smoke walkthrough passed after these changes. Browser availability was checked again and still returned no available browsers, so these interaction changes have not been visually exercised. Add rapid conversation switching under a slow network and switching away during a send to the browser checklist; verify that no previous thread's content or draft appears under a different recipient.

## Browser checklist

1. Open http://localhost:3000. Choose Maya's fictional host account. Check Discover at desktop and mobile widths, filters, reset, and empty results.
2. Open Arif's profile. Check keyboard focus remains within the dialog, Escape closes it, and focus returns to the trigger. Send a short message request.
3. Sign out and enter Arif's demo account. Open Messages, accept Maya's request, and reply. Switch back to Maya and confirm the reply. Try a declined request using another fictional account if desired.
4. Edit Maya's profile, verify matching reflects the change, then hide and restore it. Block a member, verify discovery/conversation exclusion, then unblock under My profile.
5. As Maya, import `data/sample-submissions.json` in Manage community, review every field, approve the fictional Jordan profile, and find it in discovery. Import again and confirm duplicate detection. The sample uses an `example.com` identity and is for import testing only, not real Google login.
6. Use the [Google setup guide](GOOGLE_FORMS.md) for a real test response and real approved Google account. Disable demo mode first. Verify that an unapproved Google account cannot enter.

## Repeatable checks

```sh
npm run typecheck
npm run build
.venv/bin/python -m unittest discover -s backend/tests -p 'test_unit.py' -v
RUN_INTEGRATION=1 DATABASE_URL=postgresql://neighbor:local-neighbor-password@127.0.0.1:5432/neighborhub_test .venv/bin/python -m unittest discover -s backend/tests -v
.venv/bin/python scripts/smoke.py
```

Run the smoke check only with the local demo server and graph worker up. It verifies fictional demo sessions and will deliberately stop when demo mode is disabled. Run builds separately from editing the development app where practical; both use the `.next` build directory.

To reproduce the Linux/Python 3.12 tests without publishing any ports:

```sh
docker compose build backend
docker compose run --rm --no-deps -e RUN_INTEGRATION=1 -e DATABASE_URL=postgresql://neighbor:local-neighbor-password@postgres:5432/neighborhub_test backend python -m unittest discover -s backend/tests -v
```

## Non-destructive backup verification

Create the backup with `sh scripts/backup.sh`, then restore into a new database name. Replace `YOUR_BACKUP.dump` with the specific file produced; do not restore over the main database.

```sh
docker compose exec -T postgres createdb -U neighbor neighborhub_restore_test
docker compose exec -T postgres pg_restore -U neighbor --no-owner --no-acl -d neighborhub_restore_test < backups/YOUR_BACKUP.dump
docker compose exec -T postgres psql -U neighbor -d neighborhub_restore_test -c 'SELECT count(*) FROM members;'
```

If that verification database already exists, choose another unused verification name rather than overwriting it. Compare table counts and application behavior against the expected source snapshot before relying on a recovery procedure.


## Community stories update (2026-09-30)

- `npm run typecheck` and `npm run build` passed.
- All 19 Python tests passed with integration enabled against the isolated `neighborhub_test` database.
- Added coverage for topic/profession matching, normalized tags, required future event times and public venues, post persistence, author-only deletion, private feed fields, unread event alerts/read receipts, and blocked-author exclusion.
- Applied the idempotent `002_community` migration locally. Restart a running backend to load the community API routes.
- This update was not visually browser-tested. Existing browser verification elsewhere in this file refers to earlier work.

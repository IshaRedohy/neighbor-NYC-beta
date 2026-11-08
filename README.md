# Neighbor · NYC

A local, invitation-only networking beta for New Yorkers. **Next.js frontend, Python/FastAPI backend, PostgreSQL source of truth, Neo4j relationship graph.** No AWS resources are created.

Discover neighbors by hobbies, profession, expertise, language, optional cultural identity and country of origin, and approximate ZIP distance. Approve Google Form submissions, sign in with Google, exchange message requests, manage conversations, block/report members, and hide or delete profiles.

## What members can do

- **Find nearby people:** search gardening, programming, realtor, or other interests and professions; combine distance, language, culture, country-of-origin, and interest filters. Profiles explain shared interests and languages. Send a private message request without exchanging contact details.
- **Find common ground:** describe languages, origin, hobbies, and causes in your profile. Use your bio for birthplace and outlook; these are searchable text, not inferred attributes or a separate compatibility score.
- **Find help or advertise:** publish a need/ad or offer on **Community**, with topics such as `real estate`, `realtor`, and `home buying`. The “For me” feed matches these topics against interests, expertise, needs, and occupation. Matching posts rank first; all members in the selected area can browse all posts by switching off “For me”. Matching uses normalized text, so include related terms explicitly.
- **Hear about local events:** publish street fairs, block parties, clothing drives, and other events with a future date, area ZIP, and public meeting place. Upcoming events within approximately five miles create persistent unread in-app alerts, refreshed every ten seconds while signed in. Mark them read on Community. These are not device push, SMS, or email notifications. Organizers can also use Discover to contact neighbors.
- **Control privacy:** use a display name; initials provide an avatar without requiring a photo. ZIP code is required. Street address is optional and hidden from other members; the host can review it in signup submissions. It is not used for matching or copied into the relationship graph. No phone number is collected. ZIP-based distances are approximate. Google email is still required privately for approval/sign-in and is visible to the member and host, never in member discovery or posts. Keep personal contact details out of free-text profiles, posts, and messages.

Posts are visible only to approved members and respect blocking, profile visibility, suspension, and demo-mode restrictions. Authors can delete their posts; hosts can remove any post. Deleting a profile deletes its posts. Event alerts disappear when events start or become unavailable. Photo uploads, semantic matching, and push notifications are outside this beta.

After updating an existing installation, run `.venv/bin/python -m backend.cli migrate` and restart the backend. Migration `002_community` adds posts and per-member event read receipts; `003_optional_address` adds a private optional street address. Neither replaces existing data.

## Start locally

Prerequisites: Docker Desktop, Node.js 22+, Python 3.9+ (3.12 recommended). The installed local development environment and containers use Python 3.12. On Apple Silicon, use a native arm64 Python installation when creating the virtual environment.

1. Copy `.env.example` to `.env` if `.env` does not already exist. The local implementation includes a gitignored `.env` with **development-only** credentials. Never commit it.
2. Start the databases:

   ```sh
   docker compose up -d postgres neo4j
   ```

3. Install dependencies and initialize:

   ```sh
   npm ci
   python3 -m venv .venv
   .venv/bin/pip install -r backend/requirements.lock.txt
   .venv/bin/python -m backend.cli migrate
   .venv/bin/python -m backend.cli seed
   .venv/bin/python -m backend.cli sync
   ```

4. Run these in three terminals from the project folder:

   ```sh
   .venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000
   ```

   ```sh
   .venv/bin/python -m backend.cli worker
   ```

   ```sh
   npm run dev
   ```

5. Open **http://localhost:3000** (use `localhost`, matching `APP_URL`, rather than `127.0.0.1`). Choose **Maya** for the community-host demo or **Arif** for the member demo. All twelve sample people and workplaces are fictional.

You can also run `docker compose --profile full up --build -d` for a containerized frontend/API/worker. It uses the same database volumes. The frontend's production build is separate from the Python backend's `ENVIRONMENT`; local demo access is controlled by the latter. Run migration and seed commands using `docker compose --profile full exec backend python -m backend.cli ...` when using this path. Stop host processes first to avoid port conflicts.

Docker packages the two databases reproducibly and keeps their data in named volumes. `docker compose stop` preserves data. **Do not run `docker compose down -v` unless you intend to erase the databases.**

## Collect friends' data

Start with the [step-by-step Google Forms → local app guide](docs/GOOGLE_FORMS_LOCAL_WALKTHROUGH.md). A provided Apps Script creates the questionnaire and handles JSON export/import without Google Sheets. The [integration reference](docs/GOOGLE_FORMS.md) also covers optional signed live delivery.

For now, friends can submit the Google Form while the app stays on your laptop. You can import responses whenever you like; your computer does not need to remain online. Google still stores the form responses in your Google account. No cloud app/database is required.

Before exposing an intake endpoint through a tunnel or importing real friend data, disable demo access (`DEMO_MODE=false`), rotate the intake secret, configure Google OAuth, and create your own administrator account. The guide gives the exact steps. A local-only app is not remotely accessible to friends; remote app testing later requires a tunnel or hosting. Google Forms collection itself works remotely already.

## Architecture

```text
Google Form ── Apps Script HMAC webhook / JSON import ──┐
                                                      ▼
Browser ── Next.js UI + same-origin API proxy ── Python/FastAPI
                                                      │
                                        PostgreSQL + transactional outbox
                                                      │
                                             Python sync worker
                                                      │
                                                    Neo4j
```

- SQL owns profiles, approvals, sessions, conversations, messages, blocks, reports, community posts, event read receipts, and synchronization jobs. Input validation runs before storing submitted profile data.
- Neo4j stores members' relationships to ZIPs, languages, expertise, interests, cultures, and countries. Emails and messages are not copied into it.
- Discovery filters current SQL records, uses Neo4j relationship counts to rank candidates, and uses SQL ranking when the graph is unavailable or pending updates. Hidden/suspended/blocked members are filtered using current SQL state.
- Skills matching the viewer's requested help rank first, then geographic proximity, shared interests, and languages. Cultural identity only filters results when selected explicitly.
- Google OAuth uses state, nonce, PKCE, verified ID tokens, approved-email matching, and an immutable Google subject binding. Sessions are opaque cookies backed by hashed database tokens. API mutations require a matching `Origin` (except the independently signed webhook).
- First contact is a single pending message. Only the recipient can accept/decline; subsequent messages require acceptance. Polling refreshes the inbox every five seconds. No attachments, group chat, or email notifications in this beta.

See interactive Python API docs at http://localhost:8000/api/docs. Authenticated writes are intended through the frontend; direct tools must supply `Origin: http://localhost:3000` and a session cookie.

## Useful commands

```sh
# Schema + bundled NYC ZIP data; idempotent
.venv/bin/python -m backend.cli migrate
# Rebuild only this application's Person projection (dedicated Neo4j recommended)
.venv/bin/python -m backend.cli rebuild
# TypeScript + optimized frontend build
npm run typecheck
npm run build
# Pure validation/security tests
.venv/bin/python -m unittest discover -s backend/tests -p 'test_*.py' -v
```

Integration tests use an isolated SQL database and temporary graph nodes, cleaned by their test member IDs. Do not point them at collected friend data:

```sh
docker compose exec -T postgres createdb -U neighbor neighborhub_test
RUN_INTEGRATION=1 DATABASE_URL=postgresql://neighbor:local-neighbor-password@127.0.0.1:5432/neighborhub_test .venv/bin/python -m unittest discover -s backend/tests -v
```

If the test database already exists, skip `createdb`. Substitute your local database password if changed.

## Backups and recovery

Use `scripts/backup.sh` to make a PostgreSQL custom-format dump in gitignored `backups/`. Treat dumps as private: they contain profile and message data. Keep an encrypted copy away from the laptop before collecting important responses.

```sh
sh scripts/backup.sh
```

To verify a dump without overwriting anything, create a **new** restore-test database and use `pg_restore --no-owner --no-acl -d neighborhub_restore_test` through the PostgreSQL container. The verification steps are in [the testing notes](docs/TESTING.md).

PostgreSQL contains the authoritative data; rebuild Neo4j from SQL after a graph failure. Normal sync retries failures with bounded backoff. Pending/failed jobs are visible on the admin screen. Deletions and visibility changes also enqueue synchronization jobs.

## Beta boundaries

- Adults-only community; optional self-described cultural identity. Membership approval does not verify professional qualifications, background, or trustworthiness.
- Only approved members browse profiles. Login emails stay private except to the member and community host. Users decide what workplace/cultural information to include.
- Profile deletion anonymizes the account and retains existing message text as disclosed. Google Form responses and downloaded exports must be removed separately by the host; deleting the local profile does not delete Google's copy.
- Residential ZIP geography is approximate and excludes building-only ZIP codes. See [location sources](data/SOURCES.md).
- This is a small beta (roughly 100–500 members), not a production launch. The app fetches the small candidate directory before ranking, messages currently load the full thread, and rate limits are basic. The [Lambda hosting guide](docs/AWS_DEPLOYMENT.md) covers scale, operations, security, and estimated total costs.

Real Google OAuth/form delivery requires your Google account configuration. No form has been created in your account automatically. Browser verification and actual checks performed are recorded in [TESTING.md](docs/TESTING.md).

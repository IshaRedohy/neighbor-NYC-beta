# Google Forms, local validation, and Google sign-in

For a first-time, step-by-step manual workflow, start with [Google Forms → your local Neighbor app](GOOGLE_FORMS_LOCAL_WALKTHROUGH.md). This page covers the integration configuration, including optional live delivery.

## 1. Create the questionnaire

1. Open [Google Apps Script](https://script.google.com/) and create a standalone project in your own Google account.
2. Paste `google-forms/Code.gs` into the editor. Run `setupForm` once and authorize the Forms, Drive (private JSON exports), external-request, and trigger permissions.
3. The execution log gives the form ID, edit URL, and respondent/share URL. Open the form and **publish it** if Google shows a Publish button. Confirm that respondents outside your organization can access it, if applicable.
4. In the Google Forms settings, use **verified email collection** and tell friends to use the Google account they will use to sign in. Review the consent description and questions before distributing the link.
5. Set `GOOGLE_FORM_ID` in the project's local `.env` to the generated ID; restart FastAPI. Nothing creates or requires a Google Sheet.

The questions cover display name, required residential ZIP, optional private street address (up to 240 characters), occupation, optional workplace, languages, skills offered, interests, support sought, optional ethnicity/cultural identity, optional country of origin, and bio. Required age and sharing consent checks accompany each response. Lists are comma-separated, with up to 12 entries and 60 characters per entry. The server additionally validates the NYC ZIP allowlist and field limits before storing the pending submission.

Question IDs, not editable question titles, map responses to fields. Do not delete/recreate questions without updating `QUESTION_IDS` in Apps Script properties. Forms validation helps respondents; Python validation remains authoritative.

## Updating an existing form

The local `Code.gs` now includes an optional street-address question, required ZIP, display-name wording, and privacy wording excluding email/address from the public profile. Copying the updated script does **not** change questions on an already-created Google Form. Do not rerun `setupForm` or clear `FORM_ID` / `QUESTION_IDS`.

1. Replace the code in your existing Apps Script project with the current [`Code.gs`](../google-forms/Code.gs) and save it.
2. In your existing form, keep the ZIP question **required** with its five-digit validation. Rename the name question to **Display name** without recreating it.
3. Add the optional address question using the temporary helper below in the same Apps Script project. Run `addOptionalAddress` once. It saves the new question ID in the existing mapping; repeated runs leave the mapped question alone.

   ```javascript
   function addOptionalAddress() {
     var props = props_();
     var ids = JSON.parse(props.getProperty('QUESTION_IDS'));
     if (ids.address) return;
     var form = FormApp.openById(props.getProperty('FORM_ID'));
     var item = form.addTextItem()
       .setTitle('Street address (optional)')
       .setRequired(false)
       .setHelpText('Private: visible to you and the reviewing host, not other members. Nearby matching uses your required ZIP code.')
       .setValidation(FormApp.createTextValidation()
         .requireTextLengthLessThanOrEqualTo(240).build());
     ids.address = String(item.getId());
     props.setProperty('QUESTION_IDS', JSON.stringify(ids));
   }
   ```

4. Update the existing form description and consent wording to match `setupForm` in the current script. State that ZIP is required, address is optional, and email/address are hidden from other members. The host can review the address in submissions. Do not recreate the consent question.
5. Run `.venv/bin/python -m backend.cli migrate` locally and restart FastAPI before importing updated responses.
6. Submit a fresh test response leaving address blank, then another with an address. Verify both import; missing ZIP must be rejected. After approval, the address should appear only in the member's own profile, not another member's discovery/profile view.

Older responses and exports without `address` remain valid and use an empty address. Previously imported response IDs remain duplicates; members can add an address in **My profile**, or submit a fresh response for host review. An approved replacement submission with a blank address clears an existing address, so review updates carefully.

## 2. Collect now, import later (no tunnel needed)

Friends can submit the form while your laptop is offline. Run `exportResponses` in Apps Script when ready. It writes private JSON files to your Google Drive, with at most 100 responses per file; download them.

In the app, sign in as your community host, open **Manage community**, select **Import responses**, and upload each JSON file. Each row reports success, duplication, or validation errors. Fix invalid responses with the respondent before importing a corrected export. Never enable a public Drive sharing link for these files.

Approve individual profiles after review. Repeated response IDs are ignored. A second response using an existing email is flagged as a profile update and requires explicit review; it never overwrites the account automatically. Rejecting a submission clears its stored profile payload. Approval transfers the validated fields into the member record and clears the staging payload.

## 3. Set up your real host account

Do this before importing friends' real information or exposing any endpoint externally:

1. Set `DEMO_MODE=false` in `.env`. This disables demo logins and existing demo sessions, and removes demo profiles from member discovery.
2. Replace `INTAKE_SECRET` with a new random value of at least 32 characters. Generate one locally with `openssl rand -hex 32`. Keep the value private.
3. Create an OAuth client at [Google Cloud Console](https://console.cloud.google.com/apis/credentials). Set up the consent screen, choose **Web application**, and add this authorized redirect URI exactly:

   ```text
   http://localhost:3000/api/auth/callback
   ```

4. Put its client ID and secret in `.env` as `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`. Keep `APP_URL=http://localhost:3000` for local browsing. If Google's OAuth app is in Testing mode, add your and your friends' Google accounts as test users before they sign in.
5. Create your host identity locally:

   ```sh
   .venv/bin/python -m backend.cli bootstrap-admin --email your-google-email@example.com
   ```

6. Restart the API, open http://localhost:3000, and choose **Continue with Google**. Update the starter host profile under **My profile**.

`ADMIN_EMAILS` optionally lists additional trusted Google addresses (comma-separated) that should become admins when first approved. It does not automatically approve submissions or grant browsing access to unknown accounts.

The application's shared-origin protection deliberately requires the hostname in `APP_URL`. Using `127.0.0.1:3000` in the browser while `APP_URL` says `localhost:3000` causes writes to be rejected.

## 4. Optional live delivery while the database remains local

No tunnel is started automatically. Manual import is sufficient for the first collection round.

Once demo access is disabled and your host account works, use an HTTPS tunnel provider to forward to **localhost:8000**. Configure it to expose only `POST /api/intake/google-forms` if it supports path restrictions. Do not expose PostgreSQL port 5432 or Neo4j ports 7474/7687. Database bindings in Compose are loopback-only.

Set these **Script Properties** in Apps Script → Project Settings:

| Property | Value |
|---|---|
| `INTAKE_URL` | `https://YOUR-TUNNEL/api/intake/google-forms` |
| `INTAKE_SECRET` | Exactly the private value in your local `.env` |
| `FORM_ID` | Created by `setupForm`; keep unchanged |
| `QUESTION_IDS` | Created by `setupForm`; keep unchanged |

Keep `APP_URL` as localhost when only the webhook is tunneled. Form submissions now POST signed JSON to FastAPI. The signature is HMAC-SHA256 over `timestamp + '.' + exact JSON bytes`; timestamps expire after five minutes. The server rejects unknown form IDs, oversized bodies, missing consent, invalid profiles, and signatures that do not match.

If the tunnel/laptop is unavailable, the form still retains responses. A ten-minute scheduled trigger cycles through 25 responses per batch to redeliver them; duplicates are harmless. Rotating replay avoids losing older responses after an outage. For the small beta this intentionally rechecks delivered responses too; replace it with a durable delivery ledger at larger scale. Validation failures are logged by response ID/status only, not by full personal contents. Export/import gives row-level diagnostic messages.

## 5. End-to-end real-account check

Submit a test response through the published form. Confirm it arrives as pending, does not appear in discovery, and only becomes accessible after approval. Sign in using its verified Google email. Submit a duplicate export and verify it is ignored. Close the tunnel, submit another response, then import it or reopen the tunnel and allow a recovery cycle.

This real-account flow requires your credentials and authorization and has **not** been executed by the coding agent.

## Deleting data

Deleting an app profile clears its profile fields and login identifiers in PostgreSQL and enqueues graph deletion. Existing messages are retained under an anonymized label. The host must also delete that person's response in Google Forms and remove any exported JSON/backups according to the retention policy agreed with testers. Response-ID tombstones remain locally to prevent scheduled redelivery from recreating a deleted profile from the same response.

## References

- [Installable Google Forms submission triggers](https://developers.google.com/apps-script/guides/triggers/installable)
- [Form responses and item IDs](https://developers.google.com/apps-script/reference/forms/form-response)
- [Google OpenID Connect validation](https://developers.google.com/identity/openid-connect/openid-connect)

# Google Forms → your local Neighbor app

This guide is for your first round of testing with friends. Collect answers in Google Forms, download them using the script included with your app, and import them into your local database when you are ready.

**You do not need AWS, Google Sheets, or a public connection to your laptop for this workflow.** Your friends need a Google account to submit their verified email. You need your own Google account to own the form.

```text
Friend completes your Google Form
                ↓
Google Forms keeps the response in your Google account
                ↓  You run exportResponses
A private JSON file appears in your Google Drive
                ↓  You download it and select Import responses
Python validates each response
                ↓
Valid responses wait in local PostgreSQL for your approval
                ↓  You approve the profile
The member becomes discoverable; the local worker updates Neo4j
```

Your laptop can be switched off during collection. It only needs to be running when you import or use the local app. “Local database” does not mean every copy is local: the original responses remain in Google Forms and the exports remain in Google Drive until you remove them.

## 1. Create your form once

1. Open the project's [`google-forms/Code.gs`](../google-forms/Code.gs) file in your editor and copy its entire contents.
2. Go to [script.google.com](https://script.google.com/) while signed into the Google account that should own your community's data.
3. Select **New project**. Name it something recognizable, such as **Neighbor NYC — Form intake**.
4. Open the default `Code.gs` file in the script editor. Replace its starter contents with the code you copied. Save the project.
5. In the function selector near **Run**, choose **setupForm**. Click **Run** once.
6. Review Google's authorization request for this script. It needs to create/read the form, create private Drive exports, and install its delivery triggers. External-request permission supports the optional live-delivery feature. Only authorize the project you created and whose code you reviewed; an organizational permission block may need your Google Workspace administrator. [Google authorization guide](https://developers.google.com/apps-script/guides/services/authorization)
7. Open the execution log. Save these three values somewhere private:

   | Output | What it is for |
   |---|---|
   | `FORM_ID` | Identifies the form in your app's configuration. |
   | `Edit` URL | Your administrative link for changing questions and viewing responses. |
   | `Share` URL | The respondent link you will send to friends. |

The script creates the questions for you. It also saves the question IDs internally, so exported answers match the correct database fields. **Do not run `setupForm` for every batch.** If it says a form is already configured, use the existing form.

If you already created a form with an earlier script, follow [Updating an existing form](GOOGLE_FORMS.md#updating-an-existing-form) to add the optional address and update privacy wording. Replacing the script alone does not modify existing questions.

You do not need to click Apps Script's **Deploy** button. This workflow runs functions from the editor and uses installed triggers; it is not an Apps Script web app.

For manual import, leave the script properties `INTAKE_URL` and `INTAKE_SECRET` unset. The installed delivery functions will skip sending anything to your laptop. Do not remove the automatically created `FORM_ID` or `QUESTION_IDS` properties.

## 2. Review and publish before sharing

Open the **Edit** URL and review the form's description and questions.

- Under **Settings → Responses**, choose **Verified** email collection. Tell friends to use the Google account they will later use to sign in to Neighbor. [Google's email-collection instructions](https://support.google.com/docs/answer/139706?hl=en)
- Keep the sharing-consent and age-confirmation questions. The beta is for adults aged 18 or older.
- Keep cultural identity, country of origin, workplace, and street address optional. Residential ZIP code is required. Address is private to the member and reviewing host; it is not shown to other members or used for distance matching.
- Keep **View results summary** off. Google warns that response summaries can expose full-text answers to people who can respond. [Google sharing settings](https://support.google.com/docs/answer/2839588?hl=en)
- Keep response editing off for this first version. The import uses response IDs to prevent duplicates; re-exporting an edited response is not an update mechanism.
- You can clarify question wording, but avoid deleting/recreating questions or changing their types: the script relies on the original question IDs.

Publish the form and choose who may respond. If you use a work/school account, confirm that the access settings allow the friends you intend to invite. Copy the **respondent/share link**, not the edit link. Google requires forms to be published for responders to access them. [Publishing instructions](https://support.google.com/docs/answer/2839588?hl=en)

Submit one response yourself before distributing the link. Use real consent and your own verified email; keep the profile information limited to what you are comfortable testing with. Check that it appears in the form's **Responses** tab.

Example wording you can send with the link:

> I'm testing a small NYC networking community to help friends find neighbors with shared languages, backgrounds, and useful skills. If you'd like to participate, please fill out this form using the Google account you'd use to sign in later: [FORM LINK]. Your profile will be reviewed before approved community members can see it. ZIP code is required. Street address, cultural background, and workplace are optional. Email and street address are hidden from other members. The app is currently being tested on my laptop, so this first step is just collecting profiles.

No invitations or messages are sent automatically by this guide.

## 3. Prepare your local host account before importing real data

You can collect responses now and finish this step later. However, **do this before importing your friends' real information**. Maya and Arif are public demo identities, not your real administrator account.

Follow [the real-host setup section](GOOGLE_FORMS.md#3-set-up-your-real-host-account) to:

1. Create a Google OAuth **Web application** client for the local app. This is separate from authorizing the Apps Script you created above.
2. Configure this exact authorized redirect URI:

   ```text
   http://localhost:3000/api/auth/callback
   ```

3. Edit these entries in your existing project `.env` file. Keep its database configuration; do not replace the whole file:

   ```dotenv
   APP_URL=http://localhost:3000
   DEMO_MODE=false
   GOOGLE_CLIENT_ID=your-client-id
   GOOGLE_CLIENT_SECRET=your-client-secret
   GOOGLE_FORM_ID=the-form-id-from-setupForm
   INTAKE_SECRET=your-new-random-secret
   ```

   Generate the random secret with `openssl rand -hex 32`. Even with manual import, the current backend uses this secret to protect the Google sign-in flow. Do not paste credentials into the form or share them with friends. `GOOGLE_FORM_ID` lets the app link to your form and is required for optional live delivery; manual import does not require a matching form ID.

4. From the project directory, create your host account, replacing the example email with **your actual Google account email**:

   ```sh
   cd /Users/shahisharedohy/Desktop/banglahub
   .venv/bin/python -m backend.cli bootstrap-admin --email your-address@gmail.com
   ```

5. Restart FastAPI after changing `.env`. In its terminal, press Control-C, then run:

   ```sh
   .venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000
   ```

6. Open **http://localhost:3000**, select **Continue with Google**, and sign in as yourself. Update the temporary host profile under **My profile**.

If your Google OAuth project restricts access to test users, add your account there. Add friends when you are ready for them to test sign-in. The form can collect their answers independently of the app's OAuth configuration.

The app, PostgreSQL, and API need to be running for import. Keep the graph worker running too so approvals appear in Neo4j. Use the [local startup instructions](../README.md#start-locally) if you have closed the terminals.

## 4. Download responses from Google

Whenever you want to import a batch:

1. Return to your **existing Apps Script project**.
2. Choose **exportResponses** in the function selector and click **Run**.
3. The execution log lists one or more private Google Drive file links. There is one file per batch of up to 100 responses.
4. Open each link and download the file. Its name looks like:

   ```text
   neighbor-responses-2026-09-27-1.json
   ```

5. Keep the downloaded file somewhere private on your Mac. Do not put response exports into the project source folder or a shared Git repository.

**Use the JSON export from this script.** The current importer does not accept Google Forms' built-in CSV download, Excel files, or a Google Sheet URL. You do not need to open or edit the JSON file for a normal import.

If the log says **No responses yet**, confirm that a response was actually submitted, not just previewed.

## 5. Import and approve in Neighbor

1. Open **http://localhost:3000** and sign in as your host account.
2. Open **Manage community**.
3. Click **Import responses** and select a downloaded `.json` file.
4. Read the row-by-row results:

   | Result | Meaning and next action |
   |---|---|
   | **Ready for review** | The response passed validation and is stored as pending in local PostgreSQL. Review it below. |
   | **Already imported** | This form/response ID was received previously. No extra profile was created. |
   | An error | That row was not imported successfully. Other valid rows in the same file can still succeed. Resolve the problem before retrying it. |

5. In **Profile submissions**, expand **Review all submitted fields**. Check the person's name, email, ZIP, expertise, and the other answers.
6. Select **Approve** or **Reject**. Approval publishes public profile fields to approved members and permits that email to sign in. Email and street address remain excluded from public profiles. Rejection clears the staged profile payload and does not create a member.
7. Open **Discover**. Use **All of NYC** if the new profile is outside your current distance filter. You cannot find your own profile in your own discovery results; use **My profile** for that.

The worker updates Neo4j automatically, normally on its next processing cycle. PostgreSQL remains the authoritative database; graph delays do not bypass member approval.

## 6. Repeat collection and handle corrections

You can export all responses again tomorrow and import the resulting files. The importer skips previously received response IDs and accepts new ones. Re-importing the same file does not create duplicate profiles.

For corrections:

- **Invalid row:** ask the friend to submit a corrected response, then export/import again. The generated form does not let them edit their original submission. If you enabled a one-response-per-person restriction, you will need to adjust it before requesting a new response.
- **Already imported or rejected row:** changing that row's JSON and uploading it again does not replace it. Its ID is already recorded. Use a fresh, genuinely submitted response, not an invented ID.
- **Existing member submits again:** the app flags the new submission as an update to an existing profile. Review it carefully; it only changes the profile after approval.
- **Approved member wants a small change:** they can update their own profile in the app once app access is available.

Common problems:

| Problem | What to check |
|---|---|
| No **Manage community** tab | You are signed into a member account rather than the email you bootstrapped as host. |
| Google says redirect URI mismatch | Use the exact callback URL above in Google Cloud and `APP_URL=http://localhost:3000` locally. |
| **Origin not allowed** | Open `localhost:3000`, not `127.0.0.1:3000`. |
| ZIP rejected | Confirm a supported NYC residential ZIP. Some building-only ZIPs are absent from the geographic reference; do not substitute an invented location. |
| Too many list entries | Use at most 12 comma-separated entries per list, each at most 60 characters. |
| Missing age or consent confirmation | Ask the respondent to complete the required confirmations; do not consent on their behalf. |
| Python backend/database unavailable | Start Docker's databases and FastAPI using the README. |
| Profile does not appear | Check approval, visibility, distance/language/culture filters, and whether you are looking for your own profile. |

## 7. What to keep, share, and delete

The respondent link is what you share with friends. Keep the form edit link, response exports, database backups, and OAuth credentials private.

After confirming an import and creating a database backup with `sh scripts/backup.sh`, remove unnecessary downloaded/exported copies according to the retention period you told testers. Do not delete the only remaining copy of data you still need.

If someone wants to leave, remove their app profile and separately delete their original Google Form response and unnecessary exports. App deletion does not delete Google's copy. Existing conversation text remains in the app under **Deleted member**, as explained in the form description.

Your friends can complete the Google Form from anywhere, but **your local app is currently only available on your Mac**. Sending them `localhost:3000` will not connect them to your laptop. Remote app testing is a separate future step.

When manual imports become inconvenient, the app already supports signed delivery through an HTTPS tunnel. See [optional live delivery](GOOGLE_FORMS.md#4-optional-live-delivery-while-the-database-remains-local). It is not required for this first collection round.

## Your first successful run

- Create and publish the generated form.
- Submit one test response and check it in Google Forms.
- Set up your real local host sign-in and disable demo mode.
- Run `exportResponses` and download the JSON.
- Import, review, and approve the test profile.
- Confirm the result in the local app before sharing the form more widely.

This guide reflects the app's current code. The real Google authorization and form submission steps still need to be completed in your account.

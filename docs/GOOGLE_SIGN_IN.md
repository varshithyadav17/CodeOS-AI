# Google sign-in setup and verification

CodeOS uses Google's visible, officially rendered sign-in button. The browser obtains a short-lived nonce and public client ID from FastAPI, then sends Google's ID token to FastAPI. The backend verifies Google's signature, audience, issuer, timestamps, verified email, permanent account subject and browser nonce before issuing its own HttpOnly session cookie.

Accounts are identified by Google's permanent `sub`, not by mutable email addresses. Connecting Google to an existing password account requires that account's CodeOS password. An incorrect password leaves the accounts unlinked and allows another attempt.

## Configure your Google Cloud project

1. Configure Google Auth Platform branding, audience and a **Web application** OAuth client. If the application is in testing, add the intended test users where Google requires them.
2. Add your actual frontend origins to **Authorized JavaScript origins**. Origins include scheme and port, without a path. For local Compose use `http://localhost` and `http://localhost:8080`; for native Vite development include `http://localhost:5173`. Add the precise HTTPS origin used in production. `localhost` and `127.0.0.1` are distinct origins.
3. Set `GOOGLE_CLIENT_ID` in the root Compose `.env`, or `backend/.env` for native development. This is a public client ID; no client secret is needed for this ID-token flow. Do not create a separate frontend client-ID setting. The frontend reads the configured value from the backend at runtime.
4. Run `alembic upgrade head` before restarting the backend. Revision `b17006a91f42` adds the nullable, uniquely indexed `google_subject` field without removing existing users. Compose runs migrations through its migration service.
5. Restart the backend after changing its configuration. A frontend rebuild is not necessary just to change the client ID. Use HTTPS, `AUTH_COOKIE_SECURE=true`, and the same-origin `/api` proxy in production.

The app uses the JavaScript popup callback flow. It does not consume tokens from URL fragments or require an `/auth/callback` redirect URL. The included nginx/Vite configurations set `Cross-Origin-Opener-Policy: same-origin-allow-popups`. Local HTTP uses Google's documented `no-referrer-when-downgrade` referrer policy. If you add a Content Security Policy, allow the GIS resources required by Google's setup guide; do not allow arbitrary domains merely to silence errors.

## Verify on the actual website

- Start from a signed-out browser. Click the Google button, complete Google's account/consent UI, and check the correct CodeOS account appears.
- Reload to confirm the session persists. Sign out, then sign in with Google again without reloading the page.
- For an existing email/password account, check that the linking prompt rejects a wrong CodeOS password and succeeds with the correct password.
- Verify the actual HTTPS origin, browser privacy settings and popup/FedCM behavior. Repeat in browsers your users rely on.
- A missing client ID keeps a disabled Google option visible with an explanation and leaves email sign-in available. A blocked or failed Google script displays a refresh action. A ten-minute nonce expiry also requires refreshing Google sign-in. Opening another login tab can replace the challenge cookie; refresh the older tab before retrying.

Legacy Google-only records that lack a subject can migrate automatically only when Google is authoritative for the email (Gmail or a verified hosted domain claim). Legacy third-party email accounts require administrator-assisted identity recovery; do not attach a new identity solely because email text matches.

## What was tested here

Thirteen backend tests run Google's actual token-verification SDK against locally signed RSA credentials and local public certificates. They exercise invalid signatures/claims, expiry, nonce mismatch, missing challenge, account linking, changed email, conflicting identities and provider failures. Browser checks use an explicit GIS/verification substitute to exercise application behavior without a real Google account. Neither test mode verifies your Google Cloud settings or actual consent screen. Complete the live checks above with your client ID and domain.

References: [Google setup guide](https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid), [server-side ID-token verification](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token), [JavaScript API](https://developers.google.com/identity/gsi/web/reference/js-reference).

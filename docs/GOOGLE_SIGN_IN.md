# Google sign-in setup and verification

CodeOS uses Google's visible, officially rendered sign-in button. The browser loads Google's library while fetching a short-lived nonce and public client ID. In production Vercel serves the setup request so the button can render while the Render API starts. Local development keeps the FastAPI setup route. FastAPI verifies Google's signature, audience, issuer, timestamps, verified email, permanent account subject and browser nonce before issuing its own HttpOnly session cookie.

Accounts are identified by Google's permanent `sub`, not by mutable email addresses. Connecting Google to an existing password account requires that account's CodeOS password. An incorrect password leaves the accounts unlinked and allows another attempt.

## Current portfolio deployment

The official button is enabled at https://codeos-ai-two.vercel.app/login. On 23 October 2026 (India), a real Chrome check loaded Google's actual button iframe with HTTP 200 and no origin errors; no Google response was substituted. The backend challenge and client ID shape also passed. [CI evidence](https://github.com/varshithyadav17/CodeOS-AI/actions/runs/39873930978). Personal Google account selection/consent remains a separate user check.

## Configure your Google Cloud project

1. Configure Google Auth Platform branding, audience and a **Web application** OAuth client. If the application is in testing, add the intended test users where Google requires them.
2. Add your actual frontend origins to **Authorized JavaScript origins**. Origins include scheme and port, without a path. For local Compose use `http://localhost` and `http://localhost:8080`; for native Vite development include `http://localhost:5173`. Add the precise HTTPS origin used in production. `localhost` and `127.0.0.1` are distinct origins.
3. Set `GOOGLE_CLIENT_ID` in the root Compose `.env`, or `backend/.env` for native development. This is a public client ID; the ID-token flow needs no Google client secret.
4. Run `alembic upgrade head` before restarting the backend. Revision `b17006a91f42` adds the nullable, uniquely indexed `google_subject` field without removing existing users. Compose runs migrations through its migration service.
5. Restart the backend after changing its configuration. Use HTTPS, `AUTH_COOKIE_SECURE=true`, and the same-origin `/api` proxy in production.

## Vercel and Render deployment

- Set the same `GOOGLE_CLIENT_ID` on Render and in Vercel's production environment. Use the existing client authorized for the production domain.
- Generate a new random `GOOGLE_CHALLENGE_SECRET` of at least 32 characters and set it on both services. Store it as a sensitive, server-only variable on Vercel. Keep `JWT_SECRET` on Render and use a different value for the challenge key.
- Deploy the backend with the key first, then deploy the Vercel frontend. Existing nonce cookies work until they expire. The setup response at `/api/auth/google/challenge` should be HTTP 200 with `X-CodeOS-Auth-Source: vercel`, no-store caching and a secure, host-only nonce cookie. All credential exchanges still go to Render.
- Preview deployments without those production variables show the email form and an unavailable Google option. If you deliberately enable Google in a preview, use an authorized origin and environment-specific credentials. Update both deployed services when changing the public client ID.

The app uses the JavaScript popup callback flow. It does not consume tokens from URL fragments or require an `/auth/callback` redirect URL. The included nginx/Vite configurations set `Cross-Origin-Opener-Policy: same-origin-allow-popups`. Local HTTP uses Google's documented `no-referrer-when-downgrade` referrer policy. If you add a Content Security Policy, allow the GIS resources required by Google's setup guide; do not allow arbitrary domains merely to silence errors.

## Verify on the actual website

- Start from a signed-out browser. Click the Google button, complete Google's account/consent UI, and check the correct CodeOS account appears.
- Reload to confirm the session persists. Sign out, then sign in with Google again without reloading the page.
- For an existing email/password account, check that the linking prompt rejects a wrong CodeOS password and succeeds with the correct password.
- Verify the actual HTTPS origin, browser privacy settings and popup/FedCM behavior. Repeat in browsers your users rely on.
- A missing client ID leaves email sign-in available. Setup automatically recovers from transient errors within a bounded time and respects `Retry-After`; credential exchanges are never automatically repeated. A blocked Google script, expired nonce, or challenge replaced by another tab offers a fresh setup action.

Legacy Google-only records that lack a subject can migrate automatically only when Google is authoritative for the email (Gmail or a verified hosted domain claim). Legacy third-party email accounts require administrator-assisted identity recovery; do not attach a new identity solely because email text matches.

## What was tested here

Thirteen backend tests run Google's actual token-verification SDK against locally signed RSA credentials and local public certificates. They exercise invalid signatures/claims, expiry, nonce mismatch, missing challenge, account linking, changed email, conflicting identities and provider failures. Browser checks use an explicit GIS/verification substitute to exercise application behavior without a real Google account. Those isolated test modes do not verify the consent screen. The additional anonymous production check described above verifies real button loading and detects reported origin errors, but does not sign into an account. Complete the live checks above with your client ID and domain.

References: [Google setup guide](https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid), [server-side ID-token verification](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token), [JavaScript API](https://developers.google.com/identity/gsi/web/reference/js-reference).

# CodeOS Render setup

Status checked on 22 October 2026: the owner confirmed **My Workspace** (`tea-d8rd7qojs32c73bu413g`) and explicitly selected **free hosting for a portfolio demo**, accepting PostgreSQL expiry after 30 days. The existing GitHub repository and Vercel project are already connected.

The free `codeos-db` PostgreSQL 16 instance is in Singapore: `dpg-dbck2rui0phs73f353jg-a`. Render reports expiry at `2026-11-20T22:49:19Z` (21 November in India). The free web service `codeos-api` (`srv-dbd85cd9fdbs73apdqdg`) is live at `https://codeos-api.onrender.com`. QuickChat is separate. The root [render.yaml](../render.yaml) manages only the CodeOS web service and references the existing database; no paid resources have been created. Earlier cloud checks passed, but the latest restart returns a Neo4j authentication failure; see [current results](LIVE_VERIFICATION.md).

The file passes validation against Render's published JSON schema. CI builds the Docker image, checks non-root execution and API imports, and starts two 512 MB containers against the isolated CI PostgreSQL database to verify concurrent migrations and actual HTTP startup. Inspect the latest workflow result before applying. This does not replace authenticated Render validation or live provider checks.

The authenticated Render setup rejected `maxShutdownDelaySeconds` on the Free plan even though the public schema accepted it. That override has been removed; free services use Render's default shutdown window. Refresh an already-open setup form to load the corrected Blueprint.

## Free demo resources

| Resource | Configuration | Compute price |
| --- | --- | --- |
| `codeos-api` | One free web service, 512 MB, with the existing in-process job worker; sleeps when idle | USD 0 |
| `codeos-db` | Free PostgreSQL 16, 256 MB, 1 GB storage; expires after 30 days | USD 0 |

Use free provider tiers and remain within their allowances. Do not upgrade plans or enable paid Gemini billing. Render's bandwidth/build overages depend on workspace billing settings; keep the existing spend limits. No paid compute, disk, worker, or automatically created preview environments are included.

The user accepts the database expiry for this project. Render's free web service can sleep after 15 minutes without traffic; open the app before presenting it and allow time to wake. CodeOS and QuickChat share the workspace's free instance-hour allowance. Use small demo repositories. Background jobs resume when the service runs again. See [free service limits](https://render.com/docs/free).

Free web services have no pre-deploy commands, one-off jobs, or interactive shell. The command `python start.py --migrate` runs Alembic before accepting HTTP traffic. PostgreSQL transaction advisory locks serialize concurrent starts, and migration failure prevents startup. The Blueprint generates the JWT secret and gets the existing database's private connection string through `fromDatabase`; there is no database password to copy or send. The database already blocks external connections, and this Blueprint does not change its settings. It uses the real Dockerfile and `/api/health/live`; provider readiness must be checked separately through authenticated `/api/health/ready` and the live demo flow.

The existing database is deliberately absent from the Blueprint's `databases` list. A newly created Blueprint can duplicate declared resources and append name suffixes. Render supports referencing a database outside the Blueprint when it exists in the same workspace, so this deployment requires the existing `codeos-db` and creates no additional database. See [resource references](https://render.com/docs/blueprint-spec#referencing-service-properties) and [Blueprint replication](https://render.com/docs/infrastructure-as-code#replicating-a-blueprint).

## Connected accounts and settings

The required accounts and provider settings are connected. The table below is a reference for replacing or rotating settings, not a request to create resources again. GitHub, Vercel, and Render need no new accounts. Google Cloud and AI Studio can use the existing Google account.

| Provider | Setup | Values to enter in the Render form |
| --- | --- | --- |
| Google Auth Platform | [Create/select a Web application client](https://console.cloud.google.com/auth/clients); configure branding/audience and authorize `https://codeos-ai-two.vercel.app` as a JavaScript origin | `GOOGLE_CLIENT_ID` |
| Gemini Free tier | [Create/select a Gemini API key](https://aistudio.google.com/api-keys) on an unbilled project; verify generation and embedding quota | `GEMINI_API_KEY` |
| S3-compatible archive storage | Use an existing free-allowance bucket, or a private Backblaze B2 bucket within its free 10 GB allowance; see below | `S3_BUCKET`, `S3_ENDPOINT_URL`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` |
| Neo4j Aura | [Create/select an instance](https://console.neo4j.io/); save its credentials and use its encrypted `neo4j+s://` connection URI | `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`; all four use manual `sync: false` settings so future Blueprint syncs preserve them |
| Qdrant Cloud | [Create/select a cluster](https://cloud.qdrant.io/); create a database API key with collection read/write access | `QDRANT_URL`, `QDRANT_API_KEY` |

Neo4j Aura and Qdrant offer free instances for initial testing, with capacity/inactivity limits. They are not a production availability guarantee. Review [Aura creation](https://neo4j.com/docs/aura/getting-started/create-instance/) and [Qdrant free-cluster limitations](https://qdrant.tech/documentation/cloud/create-cluster/) before choosing a tier. Keep storage providers geographically close to the API where possible.

The deployment uses a private [Backblaze B2](https://www.backblaze.com/cloud-storage/pricing) bucket. Actual archive upload, read, re-ingestion and coordinated deletion passed. Its S3 endpoint and region come from the bucket settings; the application key ID and application key map to the two `AWS_...KEY` settings because the app uses boto3. Access is restricted to the demo bucket, including object versions and deletion. For a future AWS bucket, leave `S3_ENDPOINT_URL` blank and use the permissions in [SETUP.md](SETUP.md). Temporary files on Render are not a replacement for archive storage.

The free demo uses `gemini-3.5-flash-lite` for generation and keeps the existing embedding model and collection. Google lists a free tier for this model. The previous 3.8 Flash configuration exhausted its observed 20-request daily allowance during verification. Generation and retries are paced at five requests per minute in the single API process; daily quota exhaustion still requires a later request. Keep the project unbilled and never switch to a paid key. See [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing).

Enter private values directly in Render's setup/environment form. Do not paste API keys or passwords into chat, commit them to GitHub, or use unrelated QuickChat credentials. The Google client ID is public; this sign-in flow does not require a Google client secret. Additional Google setup and live tests are in [GOOGLE_SIGN_IN.md](GOOGLE_SIGN_IN.md).

## Apply and finish deployment

Current recovery: re-save the four Neo4j values from the **current** Aura instance in the existing service's Environment page, then choose **Save, rebuild, and deploy**. A diagnostic graph request currently returns `Neo.ClientError.Security.Unauthorized`. The Blueprint previously fixed the username/database to `neo4j`; both now use manual settings. Do not recreate the instance or send credentials in chat.

The existing Blueprint and service are installed. Use the existing [CodeOS dashboard](https://dashboard.render.com/web/srv-dbd85cd9fdbs73apdqdg) for updates; do not submit another Blueprint or create another database. The numbered procedure below documents initial setup and the release checks for a replacement deployment.

1. Open [the prepared Render setup](https://render.com/deploy?repo=https%3A%2F%2Fgithub.com%2Fvarshithyadav17%2FCodeOS-AI%2Ftree%2Fcodex%2Fdeployment-readiness) in your own browser, sign in, select **My Workspace**, and use Render's connected GitHub integration for this repository. Cloud Browser is not required. Alternatively, choose **New > Blueprint**, connect `varshithyadav17/CodeOS-AI`, select branch `codex/deployment-readiness`, and leave Blueprint Path as `render.yaml`.
2. Confirm the change list creates only the free `codeos-api` web service in Singapore, with no new database. Enter the provider settings listed above directly into Render. The Blueprint supplies `DATABASE_URL` from the existing `codeos-db` and generates `JWT_SECRET` automatically; neither needs manual entry. The Blueprint inherits the selected branch. Deploy once all required provider settings are available. If Render proposes a new database or a paid resource, do not submit that configuration. Do not import or rename QuickChat.
3. Observe build, startup migration, and live status. Migration does not transfer old MongoDB data. Confirm any prior CodeOS user data separately before replacing the public frontend.
4. Verify authenticated `/api/health/ready`, then upload a tiny repository and ask a question to exercise real embedding and generation calls within free quota. The free web service has no shell; the local `check_services.py --ai` helper remains available where the configured services are reachable. CI substitutes do not validate actual keys.
5. Read the service's **actual** public URL from Render. From the repository root run `python scripts/configure_vercel.py https://ACTUAL-SERVICE.onrender.com`, then commit its `frontend/vercel.json` change. Never use a guessed URL or QuickChat's URL.
6. Add the exact Vercel candidate origin to `CORS_ORIGINS` and Google Authorized JavaScript origins for candidate testing. Verify API forwarding, secure cookies, Google login/reload/logout, upload and GitHub import, graph, chat, reviews, docs, Memory, Timeline, and deletion with a disposable repository. Run the [live checks](DEPLOYMENT.md#ci-release-and-verification).
7. After live checks pass, merge the candidate into `main`; Vercel's existing Git connection deploys the frontend. Change the CodeOS Blueprint branch and service branch to `main`, keeping `autoDeployTrigger: checksPass`. Confirm the deployed commit on both platforms and the public production URL. Verify the Render GitHub connection, because a service created using only a public Git URL cannot auto-deploy.

Blueprint `sync: false` values are prompted only during initial creation. Later provider changes must be saved in the service's Environment settings. Save all related changes together before deploying. Keep `AUTH_COOKIE_DOMAIN` unset and use Vercel's same-origin `/api` proxy.

References: [Blueprint fields](https://render.com/docs/blueprint-spec), [automatic deployments](https://render.com/docs/deploys), [secret environment settings](https://render.com/docs/configure-environment-variables), [Google client setup](https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid).

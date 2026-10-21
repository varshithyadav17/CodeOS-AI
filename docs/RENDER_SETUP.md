# CodeOS Render setup

Status checked on 22 October 2026: the owner confirmed **My Workspace** (`tea-d8rd7qojs32c73bu413g`) and explicitly selected **free hosting for a portfolio demo**, accepting PostgreSQL expiry after 30 days. The existing GitHub repository and Vercel project are already connected.

The free `codeos-db` PostgreSQL 16 instance has been created in Singapore: `dpg-dbck2rui0phs73f353jg-a`. Render reports expiry at `2026-11-20T22:49:19Z` (21 November in India). QuickChat is separate. The CodeOS web service is still pending the database connection and provider settings. The root [render.yaml](../render.yaml) now selects only free plans; no paid resources have been created.

The file passes validation against Render's published JSON schema. CI builds the Docker image, checks non-root execution and API imports, and starts two 512 MB containers against the isolated CI PostgreSQL database to verify concurrent migrations and actual HTTP startup. Inspect the latest workflow result before applying. This does not replace authenticated Render validation or live provider checks.

## Free demo resources

| Resource | Configuration | Compute price |
| --- | --- | --- |
| `codeos-api` | One free web service, 512 MB, with the existing in-process job worker; sleeps when idle | USD 0 |
| `codeos-db` | Free PostgreSQL 16, 256 MB, 1 GB storage; expires after 30 days | USD 0 |

Use free provider tiers and remain within their allowances. Do not upgrade plans or enable paid Gemini billing. Render's bandwidth/build overages depend on workspace billing settings; keep the existing spend limits. No paid compute, disk, worker, or automatically created preview environments are included.

The user accepts the database expiry for this project. Render's free web service can sleep after 15 minutes without traffic; open the app before presenting it and allow time to wake. CodeOS and QuickChat share the workspace's free instance-hour allowance. Use small demo repositories. Background jobs resume when the service runs again. See [free service limits](https://render.com/docs/free).

Free web services have no pre-deploy commands, one-off jobs, or interactive shell. The command `python start.py --migrate` runs Alembic before accepting HTTP traffic. PostgreSQL transaction advisory locks serialize concurrent starts, and migration failure prevents startup. The Blueprint generates the JWT secret, references the existing database by name, and restricts its public network access. It uses the real Dockerfile and `/api/health/live`; provider readiness must be checked separately through authenticated `/api/health/ready` and the live demo flow.

## Accounts and settings still required

Reuse any accounts and resources you already own. GitHub, Vercel, and Render need no new accounts. Google Cloud and AI Studio can use your existing Google account. The source archive and Vercel project did not contain CodeOS provider credentials. The plugin search did not find tools capable of configuring the required Google OAuth, Neo4j, Qdrant, or ordinary S3 resources; unrelated Google and analytics plugins do not supply these application credentials.

| Provider | Setup | Values to enter in the Render form |
| --- | --- | --- |
| Google Auth Platform | [Create/select a Web application client](https://console.cloud.google.com/auth/clients); configure branding/audience and authorize `https://codeos-ai-two.vercel.app` as a JavaScript origin | `GOOGLE_CLIENT_ID` |
| Gemini Free tier | [Create/select a Gemini API key](https://aistudio.google.com/api-keys) on an unbilled project; verify generation and embedding quota | `GEMINI_API_KEY` |
| S3-compatible archive storage | Use an existing free-allowance bucket, or a private Backblaze B2 bucket within its free 10 GB allowance; see below | `S3_BUCKET`, `S3_ENDPOINT_URL`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` |
| Neo4j Aura | [Create/select an instance](https://console.neo4j.io/); save its credentials and use its encrypted `neo4j+s://` connection URI | `NEO4J_URI`, `NEO4J_PASSWORD`; the Blueprint defaults user/database to `neo4j`, so change those if your instance differs |
| Qdrant Cloud | [Create/select a cluster](https://cloud.qdrant.io/); create a database API key with collection read/write access | `QDRANT_URL`, `QDRANT_API_KEY` |

Neo4j Aura and Qdrant offer free instances for initial testing, with capacity/inactivity limits. They are not a production availability guarantee. Review [Aura creation](https://neo4j.com/docs/aura/getting-started/create-instance/) and [Qdrant free-cluster limitations](https://qdrant.tech/documentation/cloud/create-cluster/) before choosing a tier. Keep storage providers geographically close to the API where possible.

For a free S3-compatible option, [Backblaze B2](https://www.backblaze.com/cloud-storage/pricing) includes the first 10 GB, with separate egress allowances. Use the S3 endpoint and region shown for your bucket; its application key ID and application key map to the two `AWS_...KEY` settings because the app uses boto3. Grant access only to the private demo bucket, including object versions and deletion. This alternative still needs a live upload/read/delete check; it has not been provisioned or verified here. For an existing AWS bucket, leave `S3_ENDPOINT_URL` blank and use the permissions in [SETUP.md](SETUP.md). Temporary files on Render are not a replacement for archive storage.

Google lists a free tier for the configured Gemini 3.8 Flash model. Use a free project and its supported embedding quota; quota exhaustion must show an error rather than switch to a paid key. See [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing).

Enter private values directly in Render's setup/environment form. Do not paste API keys or passwords into chat, commit them to GitHub, or use unrelated QuickChat credentials. The Google client ID is public; this sign-in flow does not require a Google client secret. Additional Google setup and live tests are in [GOOGLE_SIGN_IN.md](GOOGLE_SIGN_IN.md).

## Apply and finish deployment

1. Open [the prepared Render setup](https://render.com/deploy?repo=https%3A%2F%2Fgithub.com%2Fvarshithyadav17%2FCodeOS-AI%2Ftree%2Fcodex%2Fdeployment-readiness), select **My Workspace**, and use Render's connected GitHub integration for this repository. Render dashboard sign-in is separate from the connected app authorization.
2. Confirm the selected branch is `codex/deployment-readiness`, `codeos-api` is free, and the Blueprint reuses the existing free `codeos-db` in Singapore. Keep both plans free and enter provider settings. The Blueprint inherits the selected branch. Do not import or rename QuickChat or create another database.
3. Observe build, startup migration, and live status. Migration does not transfer old MongoDB data. Confirm any prior CodeOS user data separately before replacing the public frontend.
4. Verify authenticated `/api/health/ready`, then upload a tiny repository and ask a question to exercise real embedding and generation calls within free quota. The free web service has no shell; the local `check_services.py --ai` helper remains available where the configured services are reachable. CI substitutes do not validate actual keys.
5. Read the service's **actual** public URL from Render. From the repository root run `python scripts/configure_vercel.py https://ACTUAL-SERVICE.onrender.com`, then commit its `frontend/vercel.json` change. Never use a guessed URL or QuickChat's URL.
6. Add the exact Vercel candidate origin to `CORS_ORIGINS` and Google Authorized JavaScript origins for candidate testing. Verify API forwarding, secure cookies, Google login/reload/logout, upload and GitHub import, graph, chat, reviews, docs, Memory, Timeline, and deletion with a disposable repository. Run the [live checks](DEPLOYMENT.md#ci-release-and-verification).
7. After live checks pass, merge the candidate into `main`; Vercel's existing Git connection deploys the frontend. Change the CodeOS Blueprint branch and service branch to `main`, keeping `autoDeployTrigger: checksPass`. Confirm the deployed commit on both platforms and the public production URL. Verify the Render GitHub connection, because a service created using only a public Git URL cannot auto-deploy.

Blueprint `sync: false` values are prompted only during initial creation. Later provider changes must be saved in the service's Environment settings. Save all related changes together before deploying. Keep `AUTH_COOKIE_DOMAIN` unset and use Vercel's same-origin `/api` proxy.

References: [Blueprint fields](https://render.com/docs/blueprint-spec), [automatic deployments](https://render.com/docs/deploys), [secret environment settings](https://render.com/docs/configure-environment-variables), [Google client setup](https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid).

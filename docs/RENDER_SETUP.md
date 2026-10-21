# CodeOS Render setup

Status checked on 22 October 2026: the owner confirmed **My Workspace** (`tea-d8rd7qojs32c73bu413g`). It contains QuickChat and no PostgreSQL database. CodeOS needs its own API service and database. The existing GitHub repository and Vercel project are already connected.

The root [render.yaml](../render.yaml) is ready for configuration review. **It has not been applied and no paid resources have been created.** Installing it is a billable action and also requires the provider settings below.

The file passes validation against Render's current published JSON schema, with Docker paths and database references checked locally. This does not replace authenticated platform validation during setup. CI now also builds the actual Docker image and checks non-root execution, Git availability, and API imports; inspect the latest workflow result before applying.

## Proposed resources and cost

| Resource | Configuration | Published monthly base price |
| --- | --- | --- |
| `codeos-api` | One always-on web service, 0.5 CPU / 512 MB, with the existing in-process job worker | USD 7 |
| `codeos-db` | PostgreSQL 16, 0.1 CPU / 256 MB, 1 GB storage included | USD 6 |
| Total Render compute | Both in Singapore; existing workspace plan unchanged | **USD 13/month** |

Prices were checked against [Render pricing](https://render.com/pricing). This is the Render base cost, not an all-inclusive product bill: it excludes taxes, additional bandwidth/build usage, AI requests, S3 usage, and any paid Neo4j/Qdrant plans. Database storage autoscaling and preview environments are disabled. The smallest compute size is a starting point for small repositories; production ingestion memory and load still need measurement before choosing larger capacity.

Render's free web services sleep when idle and share a workspace allowance. Its free PostgreSQL database expires after 30 days. Those limits make the free database unsuitable as the durable production database. See [free service limitations](https://render.com/docs/free).

The Blueprint generates the JWT secret, wires the database's private connection automatically, blocks public database connections, migrates the schema, and checks S3/Neo4j/Qdrant access before starting the API. It uses the real Dockerfile and `/api/health/live`. Provider failures stop deployment instead of marking an unconfigured backend successful. Gemini generation and embedding calls are checked separately after configuration.

## Accounts and settings still required

Reuse any accounts and resources you already own. GitHub, Vercel, and Render need no new accounts. Google Cloud and AI Studio can use your existing Google account. The source archive and Vercel project did not contain CodeOS provider credentials. The plugin search did not find tools capable of configuring the required Google OAuth, Neo4j, Qdrant, or ordinary S3 resources; unrelated Google and analytics plugins do not supply these application credentials.

| Provider | Setup | Values to enter in the Render form |
| --- | --- | --- |
| Google Auth Platform | [Create/select a Web application client](https://console.cloud.google.com/auth/clients); configure branding/audience and authorize `https://codeos-ai-two.vercel.app` as a JavaScript origin | `GOOGLE_CLIENT_ID` |
| Gemini | [Create/select a Gemini API key](https://aistudio.google.com/api-keys) with access to the selected generation and embedding models | `GEMINI_API_KEY` |
| AWS S3 | Create/select a private archive bucket and a credential restricted to that bucket; use the permissions in [SETUP.md](SETUP.md) | `S3_BUCKET`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` |
| Neo4j Aura | [Create/select an instance](https://console.neo4j.io/); save its credentials and use its encrypted `neo4j+s://` connection URI | `NEO4J_URI`, `NEO4J_PASSWORD`; the Blueprint defaults user/database to `neo4j`, so change those if your instance differs |
| Qdrant Cloud | [Create/select a cluster](https://cloud.qdrant.io/); create a database API key with collection read/write access | `QDRANT_URL`, `QDRANT_API_KEY` |

Neo4j Aura and Qdrant offer free instances for initial testing, with capacity/inactivity limits. They are not a production availability guarantee. Review [Aura creation](https://neo4j.com/docs/aura/getting-started/create-instance/) and [Qdrant free-cluster limitations](https://qdrant.tech/documentation/cloud/create-cluster/) before choosing a tier. Keep storage providers geographically close to the API where possible.

Enter private values directly in Render's setup/environment form. Do not paste API keys or passwords into chat, commit them to GitHub, or use unrelated QuickChat credentials. The Google client ID is public; this sign-in flow does not require a Google client secret. Additional Google setup and live tests are in [GOOGLE_SIGN_IN.md](GOOGLE_SIGN_IN.md).

## Apply and finish deployment

1. Review the resources and approve the base cost. Then open [the prepared Render setup](https://render.com/deploy?repo=https%3A%2F%2Fgithub.com%2Fvarshithyadav17%2FCodeOS-AI%2Ftree%2Fcodex%2Fdeployment-readiness), select **My Workspace**, and use Render's connected GitHub integration for this repository. The link opens the creation flow; it does not deploy automatically.
2. Confirm the selected branch is `codex/deployment-readiness`, the two new resource names are `codeos-api` and `codeos-db`, and the region is Singapore. Enter every prompted provider setting, review the cost, and apply. The Blueprint inherits the selected branch. Do not import or rename QuickChat.
3. Observe the deployment through build, migrations, provider checks, and live status. The migration is for the new PostgreSQL database; it does not transfer old MongoDB data. Confirm any prior CodeOS user data separately before replacing production.
4. In the backend's shell, run `python scripts/check_services.py --ai` to verify actual generation and embeddings. This makes two small AI requests and can consume provider quota. The existing automated tests used substitutes for these requests.
5. Read the service's **actual** public URL from Render. From the repository root run `python scripts/configure_vercel.py https://ACTUAL-SERVICE.onrender.com`, then commit its `frontend/vercel.json` change. Never use a guessed URL or QuickChat's URL.
6. Add the exact Vercel candidate origin to `CORS_ORIGINS` and Google Authorized JavaScript origins for candidate testing. Verify API forwarding, secure cookies, Google login/reload/logout, upload and GitHub import, graph, chat, reviews, docs, Memory, Timeline, and deletion with a disposable repository. Run the [live checks](DEPLOYMENT.md#ci-release-and-verification).
7. After live checks pass, merge the candidate into `main`; Vercel's existing Git connection deploys the frontend. Change the CodeOS Blueprint branch and service branch to `main`, keeping `autoDeployTrigger: checksPass`. Confirm the deployed commit on both platforms and the public production URL. Verify the Render GitHub connection, because a service created using only a public Git URL cannot auto-deploy.

Blueprint `sync: false` values are prompted only during initial creation. Later provider changes must be saved in the service's Environment settings. Save all related changes together before deploying. Keep `AUTH_COOKIE_DOMAIN` unset and use Vercel's same-origin `/api` proxy.

References: [Blueprint fields](https://render.com/docs/blueprint-spec), [automatic deployments](https://render.com/docs/deploys), [secret environment settings](https://render.com/docs/configure-environment-variables), [Google client setup](https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid).

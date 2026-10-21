# Existing Vercel and Render deployment

## Confirmed targets and current status

- GitHub: `varshithyadav17/CodeOS-AI`. Production branch: `main`.
- Vercel project: `code_os-ai` (`prj_QgtWYgzbJniBczcuWSSHx8bkSLzm`). Public production origin: `https://codeos-ai-two.vercel.app`.
- Production serves `20c0f5f98d8aaecb57bc1cee0c4a4d2c24e0402b`. Its Google button displays a placeholder message.
- Render workspace `My Workspace` (`tea-d8rd7qojs32c73bu413g`) is confirmed by the owner. Inspection found only the unrelated QuickChat service and no PostgreSQL instances. There is no CodeOS backend in this workspace to update.
- Vercel successfully built the deployment candidate preview at commit `f3ffe47`. The preview renders the frontend, but the API proxy still needs an actual CodeOS backend origin.
- [The Render setup](RENDER_SETUP.md) and root `render.yaml` prepare a separate CodeOS API and PostgreSQL database. The paid resources have not been provisioned; external provider credentials and a hosting-cost decision remain necessary.

This branch is a deployment candidate. It has not replaced production.

## Preserve existing data

The old GitHub backend uses MongoDB. This candidate implements the agreed PostgreSQL, S3, Neo4j, Qdrant, and Gemini architecture. Alembic upgrades PostgreSQL schemas; it does **not** import MongoDB users, repositories, conversations, or findings. Inspect the existing backend and take a recoverable export before changing its database. If user data exists, transfer and verify it before cutover. Preserve the original database and existing S3 objects.

Reuse the existing GitHub repository, Vercel project, and confirmed Render workspace. Keep QuickChat separate. PostgreSQL can use the existing Render account; S3, Neo4j, Qdrant, Gemini, and a Google Web OAuth client must be supplied or configured for CodeOS. No CodeOS provider credentials were present in the supplied source or Vercel configuration. Do not create paid resources or change plans without agreement. Keep private values in provider secret settings, never in source control or chat.

## Backend settings

The prepared Blueprint uses the existing Dockerfile, a private PostgreSQL connection, pre-deploy migrations, and automatic deployments after CI passes. If creating the service manually with the native Python runtime instead:

| Setting | Value |
| --- | --- |
| Root directory | `backend` |
| Python | 3.12 |
| Build | `pip install -r requirements.txt` |
| Pre-deploy migration | `alembic upgrade head` |
| Start | `python start.py` |
| Health check | `/api/health/live` |

For Docker, use `backend/Dockerfile` with build context `backend`. It also reads Render's `PORT`. If pre-deploy commands are unavailable on the existing plan, run migrations in an authorized one-off session before rollout. Startup deliberately does not run database migrations.

Configure:

- `ENV=production`, random `JWT_SECRET` with at least 32 characters, `AUTH_COOKIE_SECURE=true`, `AUTH_COOKIE_SAMESITE=lax`. Leave `AUTH_COOKIE_DOMAIN` unset.
- `CORS_ORIGINS=https://codeos-ai-two.vercel.app`; add only exact additional testing origins.
- `DATABASE_URL`: standard `postgres://`, `postgresql://`, or `postgresql+asyncpg://` URL.
- `S3_BUCKET`, `AWS_REGION`, existing S3 credentials or workload identity, and appropriate encryption. Set `S3_ENDPOINT_URL` only for a compatible non-AWS endpoint.
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`.
- `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_COLLECTION`; collection size must match `EMBEDDING_DIMENSIONS`.
- `GEMINI_API_KEY`; verify the configured `LLM_MODEL` and `EMBEDDING_MODEL` are available to this key. Changing embeddings requires a compatible collection and re-indexing.
- `GOOGLE_CLIENT_ID` for the intended Web OAuth client.
- `WORKER_ENABLED=true` for background processing in a single web service. With a separate worker, disable it on web services and run `python worker.py` on the worker. Sleeping free services cannot provide continuous background processing.
- `INTERACTIVE_TIMEOUT_SECONDS=105` keeps chat and documentation generation within Vercel's external rewrite time limit. Ingestion and reviews remain durable background jobs.

## Frontend settings

Use the existing Vercel project and Git connection. Root directory: `frontend`; framework: Vite; Node: 24; build: `npm run build`; output: `dist`.

After creating the CodeOS backend and confirming its Render URL, run `python scripts/configure_vercel.py https://ACTUAL-RENDER-SERVICE.onrender.com` and commit the generated `frontend/vercel.json` before deployment. Use the actual service origin without `/api`; the example is not a deployable address. The script validates the origin and prepends the API proxy route. Remove `VITE_BACKEND_URL` on Vercel.

The checked-in configuration supplies the real SPA routes and popup/cache headers, but deliberately has no invented API destination. Until configured, previews can render the frontend but cannot use the backend. Vercel rejected the earlier dynamic configuration, so routing now uses the supported static JSON format. Browser requests use the same-origin `/api` proxy once the actual destination is written, preserving session and Google challenge cookies.

## Google sign-in

Add `https://codeos-ai-two.vercel.app` to the Google Web application's Authorized JavaScript origins. Configure the consent audience and any required test users. Put its public client ID in Render's `GOOGLE_CLIENT_ID`. This ID-token flow does not need a Google client secret or redirect URL.

The real button is rendered by Google once configured. Missing configuration leaves a visible disabled option and email login. Existing password accounts require their CodeOS password to link Google. See [Google setup and live verification](GOOGLE_SIGN_IN.md). Automated substitutes cannot validate the actual consent screen.

## CI, release, and verification

The `Verify CodeOS` workflow runs backend tests, PostgreSQL concurrency checks against an isolated CI schema, frontend lint, and the browser suite against a production build. No production secrets are needed. Populated Timeline browser views and AI/Google behavior use explicit test substitutes.

After data/configuration checks and a successful preview, merge into `main`. Vercel's existing Git integration can automatically deploy that branch. Move the CodeOS Blueprint and its service to `main` as described in the setup guide. The Blueprint sets `autoDeployTrigger: checksPass`; verify Render is connected through its GitHub integration because deployments from a public repository URL alone do not provide automatic updates. Adding a workflow alone does not enable automatic deployments.

Before assigning production traffic, verify API forwarding, cookies, SPA navigation, and Google on the candidate domain. Add that exact domain to CORS and Google origins if testing sign-in there. Confirm the deployed commit on both platforms.

Then test live signup/email login, actual Google login/logout/reload, a small ZIP and GitHub import through ingestion, files, graph paging, chat citations, reviews, docs export, Memory edits, Timeline, re-ingestion, and deletion of a disposable test repository. Check authenticated `/api/health/ready`, build logs, and worker logs. A ready frontend build alone is not proof that all features work.

References: [Render web services](https://render.com/docs/web-services), [Render deployments](https://render.com/docs/deploys), [Vercel programmatic configuration](https://vercel.com/docs/project-configuration/vercel-ts), [Vercel rewrites](https://vercel.com/docs/routing/rewrites).

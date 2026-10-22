# Existing Vercel and Render deployment

## Confirmed targets and current status

- GitHub: `varshithyadav17/CodeOS-AI`. Production branch: `main`.
- Vercel project: `code_os-ai` (`prj_QgtWYgzbJniBczcuWSSHx8bkSLzm`). Public production origin: `https://codeos-ai-two.vercel.app`.
- Render workspace: `My Workspace` (`tea-d8rd7qojs32c73bu413g`). The free API is `codeos-api` (`srv-dbd85cd9fdbs73apdqdg`), Singapore, at `https://codeos-api.onrender.com`. QuickChat is separate.
- Free PostgreSQL: `codeos-db` (`dpg-dbck2rui0phs73f353jg-a`), Singapore, private connections only. The owner accepts its expiry at `2026-11-20T22:49:19Z` (21 November in India).
- The checked-in Vercel configuration forwards `/api` to the actual CodeOS API. PostgreSQL, Backblaze storage, Neo4j and Qdrant pass authenticated readiness. Actual `gemini-3.5-flash-lite` chat returned citations and relationships; README generation and all six review specialists plus the manager passed. Embeddings and the vector collection are unchanged.
- [Live verification](LIVE_VERIFICATION.md) records the tested flows, CI evidence, quota handling, and checks that require a personal Google account. No paid compute, storage disk or separate worker was created.

The tested release merged through PR #1. Both application deployments are configured to follow `main`; final production verification is recorded in the live report.

## Preserve existing data

The old GitHub backend uses MongoDB. This deployment implements PostgreSQL, S3-compatible archives, Neo4j, Qdrant, and Gemini. Alembic upgrades PostgreSQL schemas; it does **not** import MongoDB users, repositories, conversations, or findings. The new demo database is separate; no historical MongoDB migration or deletion was performed. Preserve any older database and objects if they contain data to retain.

Reuse the existing GitHub repository, Vercel project, and confirmed Render workspace. Provider settings are already stored on the CodeOS Render service. Keep QuickChat separate and private values in provider secret settings, never in source control or chat.

## Backend settings

The free Blueprint uses the Dockerfile, a private PostgreSQL connection, and `python start.py --migrate`. PostgreSQL transaction locks serialize migrations before HTTP starts. The Blueprint requests automatic deployments after CI passes. If creating a native Python service manually instead:

| Setting | Value |
| --- | --- |
| Root directory | `backend` |
| Python | 3.12 |
| Build | `pip install -r requirements.txt` |
| Start (free service) | `python start.py --migrate` |
| Health check | `/api/health/live` |

For Docker, use `backend/Dockerfile` with build context `backend` and command `python start.py --migrate`. It reads Render's `PORT`. Free services have no pre-deploy jobs, one-off sessions, or interactive shell. The plain `python start.py` command still leaves migrations to the operator for other deployment environments.

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
- `LLM_REQUESTS_PER_MINUTE=5` paces generation and retries across chat, documentation and reviews in this single-process free deployment. Keep it within the actual provider allowance. Reviews can take several minutes; multiple processes would need a shared limiter.

## Frontend settings

Use the existing Vercel project and Git connection. Root directory: `frontend`; framework: Vite; Node: 24; build: `npm run build`; output: `dist`.

`frontend/vercel.json` already forwards `/api/:path*` to `https://codeos-api.onrender.com/api/:path*`. If the backend origin changes, run `python scripts/configure_vercel.py https://NEW-CONFIRMED-ORIGIN` and commit the generated configuration. The script validates the origin and prepends the API proxy route. Leave `VITE_BACKEND_URL` unset on Vercel.

The checked-in configuration supplies SPA routes and popup/cache headers using static JSON. Browser requests use the same-origin `/api` proxy, preserving session and Google challenge cookies. Deployment Protection remains enabled on previews; the connected fetch operation could not access the protected candidate with its current project scope.

## Google sign-in

Add `https://codeos-ai-two.vercel.app` to the Google Web application's Authorized JavaScript origins. Configure the consent audience and any required test users. Put its public client ID in Render's `GOOGLE_CLIENT_ID`. This ID-token flow does not need a Google client secret or redirect URL.

The real button is rendered by Google once configured. Missing configuration leaves a visible disabled option and email login. Existing password accounts require their CodeOS password to link Google. See [Google setup and live verification](GOOGLE_SIGN_IN.md). Automated substitutes cannot validate the actual consent screen.

## CI, release, and verification

The `Verify CodeOS` workflow runs backend tests, PostgreSQL concurrency checks against an isolated CI schema, frontend lint, and the browser suite against a production build. No production secrets are needed. Populated Timeline browser views and AI/Google behavior use explicit test substitutes.

Publish application changes through `main`. Vercel follows that branch and `render.yaml` explicitly sets the existing CodeOS service to `branch: main` with `autoDeployTrigger: checksPass`. Main pushes run the complete verification workflow. The existing Blueprint may still monitor the original candidate branch for infrastructure; an infrastructure edit must reach that branch (fast-forward it from tested main) until the Blueprint source is moved in the Dashboard. Ordinary application updates use main. Configuration syncs can deploy before CI finishes, so inspect checks before applying infrastructure changes. Never create a second Blueprint or service.

Before assigning production traffic, verify API forwarding, cookies, SPA navigation, and Google on the candidate domain. Add that exact domain to CORS and Google origins if testing sign-in there. Confirm the deployed commit on both platforms.

Then test live signup/email login, actual Google login/logout/reload, a small ZIP and GitHub import through ingestion, files, graph paging, chat citations, reviews, docs export, Memory edits, Timeline, re-ingestion, and deletion of a disposable test repository. Check authenticated `/api/health/ready`, build logs, and worker logs. A ready frontend build alone is not proof that all features work.

References: [Render web services](https://render.com/docs/web-services), [Render deployments](https://render.com/docs/deploys), [Vercel programmatic configuration](https://vercel.com/docs/project-configuration/vercel-ts), [Vercel rewrites](https://vercel.com/docs/routing/rewrites).

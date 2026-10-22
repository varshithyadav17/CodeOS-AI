# CodeOS AI

[Open the live app](https://codeos-ai-two.vercel.app)

Codebase intelligence with semantic code retrieval, a structural knowledge graph, and answers linked to source files and line ranges.

Upload a ZIP or import a GitHub repository, browse its files and relationships, ask questions with source citations, run six-specialist reviews, generate documentation, and retain findings as engineering memory.

Built with **React, Vite, Tailwind, FastAPI, PostgreSQL, S3-compatible storage, Neo4j, Qdrant, and Gemini**. Google sign-in uses Google Identity Services. Original repository archives remain in private object storage; clones and extracted workspaces are temporary.

See [live verification](docs/LIVE_VERIFICATION.md) for actual cloud checks and release status, and [automated verification](docs/VERIFICATION.md) for test coverage. The local suite passes 83 backend tests; CI additionally checks PostgreSQL concurrency, deployment containers and browser flows. Browser AI and Google checks use explicit substitutes. Personal Google consent, private GitHub token access and production load are separate verification boundaries.

## Start with Docker Desktop

Prerequisites: Docker with Compose v2, Python 3.10+ for the small configuration helper, and a Gemini API key with access to the configured generation and embedding models. Allow roughly 4 GB of memory for the local stack.

1. Clone this repository and open a terminal in the `CodeOS-AI` folder.
2. Generate separate random local credentials:

   ```bash
   python scripts/configure.py
   ```

3. Edit the generated `.env` and fill in `GEMINI_API_KEY`. The defaults use `gemini-3.5-flash-lite` for generation and `gemini-embedding-001` with 768-dimensional cosine vectors for retrieval. Both model names are configurable. Choose models available to your account.
4. Start the stack:

   ```bash
   docker compose up --build -d
   docker compose ps
   ```

5. Open **http://localhost:8080**, create an account, and upload a small ZIP. Local development builds the official MinIO source release as an S3-compatible object store; its first build compiles Go dependencies. The portfolio deployment uses private Backblaze S3-compatible storage.
6. Verify the actual service configuration, including two small Gemini requests:

   ```bash
   docker compose exec backend python scripts/check_services.py --ai
   ```

7. Run the complete live API lifecycle check after creating your account:

   ```bash
   docker compose exec backend python scripts/smoke_api.py --base-url http://localhost:8000 --email you@example.com
   ```

   Enter your CodeOS password when prompted. The script uploads a small test repository, checks indexing, file preview, graph relationships, chat evidence and re-ingestion, then deletes the test repository.

View logs with `docker compose logs -f backend`. Use `docker compose down` to stop services while keeping data volumes. `docker compose down -v` removes all local database and archive data.

## Native development

Use **Python 3.12** and **Node 22.12+**. Start PostgreSQL, Neo4j, Qdrant and an S3 bucket first. The Compose services can supply these dependencies locally.

Backend:

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
# Copy .env.example to .env; fill database, JWT, storage, Neo4j and Gemini values.
alembic upgrade head
uvicorn server:app --reload --host 127.0.0.1 --port 8000
```

Frontend, in a separate terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to the backend. A deployed frontend should use the included nginx configuration, which serves the SPA and proxies the API on the same origin. Google sign-in is optional: set `GOOGLE_CLIENT_ID` on the backend and authorize the actual frontend origin in Google Cloud. The frontend reads it at runtime. Follow [docs/GOOGLE_SIGN_IN.md](docs/GOOGLE_SIGN_IN.md).

## What is included

- Existing dark UI, authentication, repository workspace, engineering memory, reviews and architecture tools.
- Google sign-in with browser nonces, permanent subject identity, password-confirmed linking and recovery.
- Documentation workspace with ten generators, saved Markdown, regeneration and ZIP export.
- Streamed, bounded ZIP upload; safe extraction; GitHub import with an optional **user-provided** private-repository token.
- Stable repository-scoped graph and chunk IDs; idempotent indexing and archive-based re-ingestion.
- PostgreSQL job records with retries, leases, cancellation, per-repository PostgreSQL advisory locks, and retryable cross-store cleanup.
- Python AST and tree-sitter analysis, full-source chunk windows, imports, classes, functions and best-effort static calls.
- Gemini document/query embeddings stored exclusively in Qdrant; model/dimension/distance compatibility checks.
- Hybrid retrieval that combines code evidence with Neo4j relationships. Source excerpts, file paths and line references persist with conversations.
- Ownership checks, HttpOnly cookies, CSRF origin checks, safe GitHub URLs, archive limits, secret-file exclusions, and bounded external calls.
- Version-aware S3 deletion, related-record cascades, service health checks, migrations, Docker files, and automated tests.
- Paged graph browsing, combined memory search and filters, updated memory counts, and compact mobile navigation.

See [docs/PRODUCT_AUDIT.md](docs/PRODUCT_AUDIT.md) for the feature-by-feature audit, [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/SETUP.md](docs/SETUP.md), [docs/CHECKPOINTS.md](docs/CHECKPOINTS.md), and [docs/EMERGENT_HANDOFF.md](docs/EMERGENT_HANDOFF.md).

## Run tests

From the project root, with the backend virtual environment activated:

```bash
pip install -r backend/requirements-dev.txt
python -m pytest -q
ruff check backend --select F
```

From `frontend`:

```bash
npm ci
npm run lint
npm run build
npm audit
```

The default suite uses isolated SQLite application records, a graph test double, the actual Qdrant local implementation, S3 API simulation, and deterministic AI/embedding substitutes. **No production fallback to these substitutes exists.** Opt-in tests against real PostgreSQL, Neo4j and Qdrant are documented in the verification report.

## Existing Vercel and Render deployment

See [deployment and cutover instructions](docs/DEPLOYMENT.md) for the confirmed project, API routing, Google configuration, data preservation, and automatic updates.

The portfolio deployment uses the existing Vercel project and free Render service at `https://codeos-api.onrender.com`. PostgreSQL, private archives, Neo4j and Qdrant pass authenticated readiness. Real free-model chat, documentation and all six review specialists plus manager passed. The production app follows `main`; same-origin API forwarding, secure cookie sessions, provider readiness and SPA routes pass live checks. The real Google button also loads successfully on the public origin. [Live verification](docs/LIVE_VERIFICATION.md) records the tested flows and remaining limits. [The Render setup guide](docs/RENDER_SETUP.md) documents the existing resources and free-tier settings. The owner accepts PostgreSQL expiry on 21 November 2026 in India. Startup migrations run before HTTP because free web services do not have pre-deploy jobs.

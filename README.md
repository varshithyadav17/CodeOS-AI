# CodeOS AI

Codebase intelligence with semantic code retrieval, a structural knowledge graph, and answers linked to source files and line ranges.

This source checkpoint upgrades the supplied React application to **React + Vite + Tailwind, FastAPI, PostgreSQL, S3, Neo4j, Qdrant, and Gemini**. The frontend sends application operations to FastAPI; Google sign-in uses Google Identity Services. Repository source exists permanently as an original ZIP in object storage; clones and extracted workspaces are temporary.

**Read [docs/VERIFICATION.md](docs/VERIFICATION.md) before deployment.** GitHub CI passed 76 backend tests (including PostgreSQL concurrency) and 31 production-build browser checks. Earlier real Neo4j/Qdrant adapter checks also passed. Browser AI and Google flows use explicit test substitutes. AWS permissions, real Gemini calls, Google consent, private GitHub imports, the complete Docker startup, and production load still need live verification. No API keys or existing application database were supplied with the source archive.

## Start with Docker Desktop

Prerequisites: Docker with Compose v2, Python 3.10+ for the small configuration helper, and a Gemini API key with access to the configured generation and embedding models. Allow roughly 4 GB of memory for the local stack.

1. Extract the ZIP and open a terminal in the `CodeOS-AI` folder.
2. Optionally verify the untouched extracted source, then generate separate random local credentials:

   ```bash
   python scripts/verify_source.py
   python scripts/configure.py
   ```

3. Edit the generated `.env` and fill in `GEMINI_API_KEY`. The defaults use `gemini-3.8-flash` for generation and `gemini-embedding-001` with 768-dimensional cosine vectors for retrieval. Both model names are configurable. Choose models available to your account.
4. Start the stack:

   ```bash
   docker compose up --build -d
   docker compose ps
   ```

5. Open **http://localhost:8080**, create an account, and upload a small ZIP. Local development builds the official MinIO source release as an S3-compatible object store; its first build compiles Go dependencies. Production uses your AWS S3 bucket.
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

The portfolio deployment uses free Render plans, as requested. The free PostgreSQL database is created; the API and external provider settings still need connecting. [The Render setup guide](docs/RENDER_SETUP.md) records the resources, free-tier limits, and account settings. `render.yaml` uses startup migrations because free web services do not have pre-deploy jobs.

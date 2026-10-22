# Setup and operating guide

## Configuration

Use the root `.env` with Docker Compose. Use `backend/.env` for native backend development. Never put backend credentials in a `VITE_` variable: Vite variables become public browser assets.

| Setting | Purpose |
| --- | --- |
| `DATABASE_URL` | `postgresql+asyncpg://user:password@host:5432/database`; URL-encode reserved characters in manually supplied passwords |
| `JWT_SECRET` | Stable random secret, minimum 32 characters; the helper generates 48 random bytes encoded safely |
| `GEMINI_API_KEY` | Server-side Gemini API key; required for embeddings and AI features |
| `LLM_MODEL` | Available Gemini generation model; default `gemini-3.5-flash-lite` for the free demo |
| `LLM_REQUESTS_PER_MINUTE` | Shared per-process generation pacing; default 5, including retries; keep within the provider allowance |
| `EMBEDDING_MODEL` | Default `gemini-embedding-001` |
| `EMBEDDING_DIMENSIONS` | Default 768; must match the Qdrant named vector |
| `QDRANT_COLLECTION` | Versioned collection name; use a new collection after a model/dimension change |
| `S3_BUCKET` | Existing private archive bucket |
| `S3_ENDPOINT_URL` | Empty/unset for AWS; local MinIO URL only for development |
| `AWS_REGION` | Bucket region |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Optional when using the AWS SDK's normal IAM-role credentials |
| `S3_ENCRYPTION` | `AES256` for AWS SSE-S3; blank for the supplied development MinIO configuration |
| `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` | Graph connection; use a secure Neo4j URI for a hosted graph |
| `QDRANT_URL`, `QDRANT_API_KEY` | Vector service connection |
| `GOOGLE_CLIENT_ID` | Optional public Google sign-in client ID; delivered to the frontend at runtime; see `GOOGLE_SIGN_IN.md` |
| `CORS_ORIGINS` | Exact trusted browser origins, including scheme and port |
| `AUTH_COOKIE_SECURE` | `true` for HTTPS production |
| `AUTH_COOKIE_SAMESITE` | Usually `lax`; `none` requires secure cookies and explicit cross-origin setup |
| `WORKER_ENABLED` | Start an in-process worker; disable when operating separate workers |

Private GitHub imports accept a fine-grained access token in the import form. The token belongs to that requesting user and should have Contents read access only for the chosen repository. It is encrypted in job metadata, excluded from job API responses and cleared after the archive is saved. No shared server GitHub token grants private access to all application users. Rotating `JWT_SECRET` also changes the credential-encryption derivation and invalidates unfinished private-import credentials; re-import those repositories after rotation.

## AWS deployment

The supplied Compose stack is a local-development stack. Its MinIO image is compiled from official security release `RELEASE.2025-10-15T17-29-55Z`, so the first build needs internet access for the Go source and modules. The image retains the upstream license and notice. The upstream community repository is archived; use AWS S3 for production as specified by the architecture. For your hosted deployment, run the backend with your actual PostgreSQL, Neo4j, Qdrant and AWS environment values. Configure an existing private S3 bucket and leave `S3_ENDPOINT_URL` empty. Use IAM roles where supported.

Grant the backend role bucket-level `s3:ListBucket` and `s3:ListBucketVersions`, and object-level `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject`, and `s3:DeleteObjectVersion` on the `repositories/` prefix. Repository deletion removes historical versions as well as the current key; Object Lock/retention rules can prevent deletion and will leave tracked cleanup failures.

Enable HTTPS in your hosting reverse proxy. Set `ENV=production`, `AUTH_COOKIE_SECURE=true`, a persistent `JWT_SECRET`, and actual frontend origins. Keep datastore ports private. Use the supplied frontend nginx config or an equivalent same-origin `/api` proxy. Direct native deployments should provide equivalent authentication request throttling; the included nginx config limits authentication requests.

Run `alembic upgrade head` exactly once as a release/migration step before starting API instances. Docker Compose includes a separate migration service. Do not start multiple simultaneous schema migrations.

Verify with `python scripts/check_services.py --ai` inside `backend`, then `scripts/smoke_api.py`. Health endpoints distinguish process liveness from authenticated service readiness. The readiness response's Gemini `configured` value checks key presence; the `--ai` script validates real API access and model calls.

## Google sign-in

Follow [GOOGLE_SIGN_IN.md](GOOGLE_SIGN_IN.md). Run `alembic upgrade head` to include revision `b17006a91f42` before starting the updated backend. Only backend `GOOGLE_CLIENT_ID` is configured; no frontend build-time duplicate is needed. Live consent, authorized origins and popup/FedCM behavior must be checked on the actual domain.

## Model/index changes

Changing `LLM_MODEL` does not require re-indexing. Changing the embedding model or dimensionality requires a new `QDRANT_COLLECTION` and re-ingestion of repositories from their S3 archives. The backend rejects incompatible vector layouts rather than mixing them. After migrating every repository, delete the old collection administratively; repository deletion can only clean the currently configured collection. Keep a record of older collections until their migration is complete.

## Retries and recovery

- `GET /api/repos/{id}/jobs` reports the owner's bounded job history, attempts and cleanup stages.
- A normal ingestion job retries transient errors up to three times by default, with backoff. Invalid archives or unsupported inputs fail without repeated processing.
- Retry re-ingestion after correcting service configuration. Ready repositories always reuse their stored archive.
- `DELETE /api/repos/{id}` returns 202 and a job ID. Wait for removal from the list; a queued deletion is not yet a completed deletion.
- If deletion fails after retry limits, the list shows `delete_failed`. Press Delete again to start a new safe cleanup job.
- Missing Gemini configuration causes indexing or AI requests to fail visibly; no placeholder AI engine or fake vectors are substituted.
- Abrupt host/process termination can leave operating-system temporary directories. Run APIs/workers in ephemeral containers with an appropriately sized temporary volume; normal Python exceptions, timeouts and cancellations clean their workspaces. A killed process cannot run a `finally` block.

## Existing MongoDB data

The supplied source ZIP did not contain a MongoDB export, previous user database, repository ZIP storage, or cloud credentials. The new schema therefore does not claim to have migrated your existing deployed records.

Before moving an existing deployment, back up MongoDB and its local repository data. Export and map application records into the PostgreSQL schema, preserve user/repository IDs, and move each original archive to its stable S3 key with SHA-256 metadata. Existing bcrypt password hashes remain verifiable. Users need to sign in again because JWT issuer/audience validation is now explicit. Rebuild graph/vector indexes from the saved archives. Old ZIP repositories whose original source is unavailable must be uploaded again. Validate ownership, record counts and backups before switching traffic.

## Resource limits

Defaults: 200 MiB uploaded archive, 500 MiB expanded/clone budget, 20,000 archive entries, 500 KB per indexed/previewed source file, maximum compression ratio 200 for large members, 30 repositories per user, 30-minute job timeout and 300-second clone timeout. Generated dependency directories, common credentials, huge files and minified lines are skipped by the parser. Raise limits only after testing capacity and upstream proxy body limits.

## Browser and service tests

Default tests run from the project root using `python -m pytest -q`. Real-store checks are opt-in:

```bash
# Run from backend. Point to disposable/test-capable service accounts.
CODEOS_LIVE_GITHUB_TESTS=1 python -m pytest -q tests/test_live_github.py
CODEOS_LIVE_STORE_TESTS=1 python -m pytest -q tests/test_live_stores.py
CODEOS_TEST_POSTGRES_URL=postgresql+asyncpg://... python -m pytest -q tests/test_postgres.py
```

The PostgreSQL test creates and removes a uniquely named schema; it needs CREATE SCHEMA permission. Real Neo4j checks create/delete test repository IDs; real Qdrant checks create/delete a unique test collection. No existing repository or collection is selected for deletion.

The reproducible browser harness is `python scripts/verify_browser.py` after installing frontend dependencies, backend development dependencies and `playwright install chromium`. It serves the actual production frontend with an explicitly isolated test backend; it does not call your cloud AI account.

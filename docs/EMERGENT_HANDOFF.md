# Emergent handoff: CodeOS AI

Use the source in this ZIP as the audited checkpoint. Keep the architecture fixed:

**React/Vite/Tailwind → FastAPI → PostgreSQL, AWS S3, Neo4j, Qdrant, Gemini.**

The backend owns authorization and access to every store. Do not reintroduce MongoDB, a SQL vector mirror, permanently extracted local repositories, fake production embeddings, or a second inconsistent ingestion pipeline.

## First tasks in the deployment account

1. Read `README.md`, `docs/ARCHITECTURE.md`, and `docs/VERIFICATION.md`. Install the pinned backend requirements and frontend lockfile. Do not claim the live stack is verified because the local tests passed.
2. Supply real PostgreSQL, AWS S3, Neo4j, Qdrant and Gemini configuration. The local MinIO Compose image is built from official source; it is not the production AWS storage service. Run `alembic upgrade head`, including `b17006a91f42` for permanent Google identity subjects. Verify S3 ListBucketVersions/DeleteObjectVersion permissions and actual private archive access. Configure HTTPS, exact CORS origins and secure cookies.
3. Run `backend/scripts/check_services.py --ai`. Then run `backend/scripts/smoke_api.py` through the actual public frontend/API origin. Confirm object storage bytes, graph counts, vector counts and cleanup after deletion.
4. Run the isolated PostgreSQL concurrency test and actual Neo4j/Qdrant adapter tests. Test worker interruption/recovery in the actual deployment before increasing worker count.
5. Verify public GitHub cloning, a private GitHub import using the requesting user's token, Google sign-in using `docs/GOOGLE_SIGN_IN.md` if enabled, and that no source workspaces remain after normal processing. Test file/source access as a second user.
6. Repeat the actual browser workflow, dependency audit, build and automated suite. Record passed, failed and unverified results separately. Do not replace real failures with placeholder answers or success flags.

## Preserve these working source behaviors

- Source-code UI, engineering memories, reviews and architecture tools.
- Documentation workspace with ten types, saved drafts, Markdown download and ZIP export.
- Google subject identity, browser nonce and password-confirmed account linking; runtime backend client-ID configuration.
- Durable database-backed jobs with leases, per-repository exclusion, cancellation and retries.
- Archive checksum verification, safe ZIP extraction and temporary cleanup.
- Stable node/chunk IDs and repository-isolated graph/vector access.
- Qdrant model compatibility checks and code evidence/relationships returned to chat.
- Deletion progress, retryable cleanup and related-record cascades.

## Existing deployed data

This source ZIP did not include a deployed MongoDB export or previous repository archives. Do not wipe an existing account's records. Back up and explicitly migrate its application metadata and original source archives, preserve ownership IDs, rebuild indexes, and compare counts before switching traffic. Existing bcrypt password hashes are supported; old sessions need a fresh login.

Deliver the resulting deployment URL, exact environment/model configuration names without secret values, final tests and any remaining limitations. Do not describe a frontend-only preview or an AI-stubbed test server as the completed live product.

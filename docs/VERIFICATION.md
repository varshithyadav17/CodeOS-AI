# Deployment candidate checks — 2026-10-21

The deployment branch restores Dashboard and Timeline, retains a visible Google option when configuration is absent, adds Render port/PostgreSQL URL support, bounds interactive AI requests, and supplies Vercel API/SPA routing plus CI.

- GitHub CI on commit `34a6bdd`: **76 passed, 3 skipped**, including the real PostgreSQL concurrency check. Local backend run: 75 passed, 4 skipped. Live Neo4j/Qdrant and GitHub integration checks were not rerun.
- Frontend lint and production build: passed. Runtime npm audit: **0 vulnerabilities**.
- Python import/name lint and dependency consistency: passed.
- Vercel rejected dynamic configuration during its preview attempt. Static SPA configuration and an origin-validating API proxy setup script replace it; the actual Render destination still requires workspace confirmation.
- GitHub CI browser suite: **31 checks passed, zero uncaught browser errors**, against the production build. Covers restored Dashboard/Timeline and visible unavailable Google state. AI, Google, and populated Timeline data use explicit substitutes. See [CI browser results](DEPLOYMENT-BROWSER-RESULTS.json). Local Chromium downloads were unavailable; CI completed these checks successfully.
- Live Google consent, provider credentials, existing MongoDB data transfer, Render service configuration, and production rollout remain unverified. See [deployment instructions](DEPLOYMENT.md).

The report below records earlier source verification and remains historical evidence only.

---

# Verification report

Checkpoint date: 19 October 2026 (India). The checks below describe what actually ran in the build environment. They do not certify an unconfigured cloud deployment.

## Results

| Check | Result | Actual scope |
| --- | --- | --- |
| Backend automated suite | **70 passed, 4 skipped** | Isolated SQL records, authentication, ownership, archive security, parsing, full chunk coverage, jobs, retry/failure/cancellation, hybrid context, reviews, memory, docs and cleanup |
| Google credential verification | **13 tests passed** | Real Google verification SDK with local RSA signatures/certificates; claims, nonce, linking and identity conflicts covered; no real Google account consent |
| Real Neo4j 5.26.0 adapter | **Passed** | Constraints, repeated upserts, repository scoping, static relationships, traversal, parameter binding and repeated deletion |
| Real Qdrant 1.19.2 server adapter | **Passed** | Named vector schema, upserts, query filtering, idempotency and repository deletion with deterministic test embeddings |
| S3 boto3 integration tests | **Passed in S3 API simulation** | Archive bytes/metadata/encryption parameters, retrieval, idempotent deletion, historical-version erasure, unrelated-object preservation |
| Alembic migration | **Passed on isolated SQLite** | Existing-user upgrade to Google-subject schema, schema comparison with no pending changes, downgrade/upgrade validation |
| PostgreSQL migration SQL | **Generated successfully** | PostgreSQL-dialect DDL compilation; not a live PostgreSQL migration run |
| Production frontend build | **Passed** | Vite 8, Tailwind 4, React 18, React Router 7; lazy chunks generated |
| Frontend lint | **Passed** | Zero ESLint errors or warnings |
| npm dependency audit | **0 known advisories reported** | Audit at checkpoint time; no perpetual vulnerability guarantee |
| Python dependency consistency | **Passed** | `pip check`; runtime requirements include SQLAlchemy's required asyncio dependency |
| Python compilation/static checks | **Passed** | `compileall` and Ruff undefined/unused-name checks |
| Browser flow against production build | **27 checks passed; 0 uncaught browser errors** | Signup/login, upload/status, file preview, graph positions/paging, chat evidence/relationships, re-ingestion, architecture, six-specialist reviews, memory search/filters/status/counts, source navigation, session reload, mobile layout, deletion cascades and logout |
| Compose YAML | **Parsed and checked** | Service definitions, migration dependencies, local-only datastore port bindings |
| Final ZIP | **CRC and manifest checked** | Source package integrity, no dependency caches or actual `.env` files |

The four default-suite skips are two opt-in real-store tests, one PostgreSQL concurrency test and one public GitHub network test. The two real-store tests were separately enabled and passed against locally launched Neo4j and Qdrant servers. They are skipped in the default run so normal tests do not require those servers.

## Browser execution details

The browser test used the actual compiled frontend and actual FastAPI routes, with a deliberately isolated test database, a graph test double, the actual local Qdrant client implementation, deterministic embeddings, an AI response stub and a temporary archive-storage double. GIS JavaScript and the Google verifier were explicitly substituted in browser tests; separate backend tests use the real verifier with local signatures. It did not make live Gemini calls or use the user's cloud accounts.

The expanded browser test also checked graph paging beyond node 120, combined memory filters, review-to-memory import without duplicates, refreshed counts, deletion cascades, login after logout, and a 390-pixel mobile repository page.

Documentation generation/regeneration/ZIP export/reload, failed-logout recovery, repeat Google sign-in after logout, password-confirmed linking, nonce rejection, blocked GIS script recovery and a 390-pixel login layout were also checked.

The main workspace was also visually inspected after the Tailwind/Vite migration. The existing dark interface remained usable; graph nodes occupy distinct positions and source evidence is visible beneath assistant answers.

## Covered failure and security paths

- Google signature/audience/issuer/expiry/subject/verified-email checks, browser-bound nonce, unchanged identity after email changes, password-gated linking and conflicting-identity rejection.
- Missing/invalid authentication; duplicate emails; bounded passwords; invalid JWT claims; cookie flags and logout.
- Cross-origin mutation rejection and cross-user repository, conversation, memory, statistics, graph and job isolation.
- Unsafe URL schemes/hosts/ports/credentials, malformed branches and GitHub DNS resolving to private addresses.
- Chunked multipart bodies are stopped at the configured byte limit before unbounded temporary spooling.
- ZIP traversal/absolute/Windows paths, symlinks, duplicate/case-conflicting entries, compression expansion and size/file-count limits.
- Indexed-file allowlists, credential-file exclusions and archive-backed preview path validation.
- Stable graph/chunk IDs, complete line coverage of long functions and preservation of syntax-error source evidence.
- Duplicate-job rejection, expired-job recovery, cancellation during indexing and graceful worker shutdown.
- Idempotent re-ingestion, archive checksum failure, retryable multi-store deletion, failed-ingestion index cleanup and persisted cleanup retries.
- Model/dimension/distance mismatch rejection and repository-scoped vector queries/deletion.
- Provider error responses that do not create false assistant messages; encrypted per-import GitHub credentials omitted from APIs.
- Review zero-score preservation, malformed findings/invalid scores/unknown evidence files, all ten document types, timeline API ownership and degraded health without secret leakage.
- Review parsing failures, all-specialist review failures, idempotent review-to-memory import, documentation regeneration/export and directed impact analysis.

## Still requires verification in the target environment

1. **Live PostgreSQL and worker concurrency.** No usable container engine was available. Official PostgreSQL binaries were downloaded, but the environment did not permit switching to the non-root account required to run the server. The PostgreSQL-specific `FOR UPDATE SKIP LOCKED` and advisory-lock test is included but was not executed. Run it against a test-capable PostgreSQL connection before scaling workers.
2. **AWS S3 permissions, bucket policy, encryption, retention and real network behavior.** The S3 SDK was tested against a simulated API, not a user's AWS bucket. Version deletion requires the documented permissions and can be prevented by retention/Object Lock rules.
3. **Actual Gemini generation, embeddings, quota, costs and answer quality.** No Gemini API key was supplied. The SDK integration, context construction and vector plumbing were exercised with substitutes. Use `check_services.py --ai` and the live lifecycle script with your real model access.
4. **Live public/private GitHub cloning.** The common archive path was exercised with a controlled clone substitute. The opt-in real public pipeline test was attempted but failed the application DNS validation because of this environment's DNS/network restriction. A separate Git proxy connectivity probe succeeded; it is not a passing pipeline test. Temporary DNS failures now retry; private-address guards remain. Verify egress and a user-owned private token in the deployment environment.
5. **Google OAuth.** Application flow and real token-verifier tests pass as described above. No real Google client/domain/account flow was supplied for actual consent, authorized-origin, popup or FedCM verification. Follow `GOOGLE_SIGN_IN.md`.
6. **Complete Docker Compose startup, HTTPS hosting and production load.** Dockerfiles and Compose configuration are included and syntax/dependencies were checked. The local MinIO service builds official source tag `RELEASE.2025-10-15T17-29-55Z`; the previous registry image returned HTTP 401 during an anonymous manifest check. The new image build has not been executed here; a full container build/start and load benchmark were not available here. No throughput/SLA claim is made.

## Reproduce

From the project root with Python 3.12's development environment installed:

```bash
python -m pytest -q
ruff check backend --select F
python -m compileall -q backend
python scripts/verify_browser.py
```

From `frontend`, run `npm ci`, `npm run lint`, `npm run build`, and `npm audit`.

From `backend`, with real services configured:

```bash
alembic upgrade head
python scripts/check_services.py --ai
python scripts/smoke_api.py --base-url http://localhost:8080 --email your-account@example.com
```

Enable the isolated PostgreSQL locking test via `CODEOS_TEST_POSTGRES_URL`. Enable the actual Neo4j/Qdrant tests via `CODEOS_LIVE_STORE_TESTS=1`. Enable the public GitHub network test via `CODEOS_LIVE_GITHUB_TESTS=1`. See `SETUP.md` for permissions and test isolation.

## Provider documentation checked

The configured generation ID and supported thinking level were checked against [Google’s Gemini 3.8 Flash model documentation](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash). The existing text embedding model remains documented by [Google’s embeddings guide](https://ai.google.dev/gemini-api/docs/embeddings). These document checks do not prove access or quota for a user’s API key.

The local object-store build follows the [official MinIO security release](https://github.com/minio/minio/releases/tag/RELEASE.2025-10-15T17-29-55Z). The [upstream repository](https://github.com/minio/minio) is archived and describes source-only distribution; this local development container is separate from the AWS S3 production configuration.

Google integration references: [ID token verification](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token), [JavaScript API](https://developers.google.com/identity/gsi/web/reference/js-reference), and [client/origin/browser setup](https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid).

# Product flow and feature audit

Current cloud results are in [LIVE_VERIFICATION.md](LIVE_VERIFICATION.md). This file records the original source checkpoint; later work restored Dashboard and a dedicated Timeline UI, added cloud deployment, and verified real provider calls.

19 October 2026. This follow-up starts from the previously delivered `CodeOS-AI-Verified-Source.zip`, SHA-256 `1c584fc70dda180b69abd29fbfe645b2e166a9f0006597717300ffc7dcfd69ee`. It preserves the agreed architecture and existing product design.

## Flow checked against the agreed design

React/Vite/Tailwind sends application operations to FastAPI. PostgreSQL stores application records and durable jobs; S3 stores original archives; Neo4j stores structure; Qdrant stores Gemini code embeddings. Google Identity Services separately handles Google's browser sign-in UI. Datastore credentials stay on the backend.

ZIP/GitHub input → validation → original archive in S3 → temporary extraction and parsing → Neo4j and Qdrant writes → count verification → ready status → temporary-file cleanup. Re-ingestion uses the stored snapshot. Deletion tracks each store's cleanup and removes SQL records last. MongoDB, permanent extracted source and SQL vector mirrors have not been reintroduced.

## Repairs and additions

- Replaced the hidden/forwarded Google-button approach with the visible official button. The public client ID now comes from backend runtime configuration. Fresh callbacks and nonces survive sign-out/sign-in cycles; loading failures offer recovery.
- Added a browser-bound nonce, permanent Google subject, migration and password-confirmed account linking. Bad signatures, mismatched claims and conflicting identities fail explicitly. Logout failures retain the visible session instead of pretending the cookie was cleared.
- Added a Documentation workspace for all ten existing generators, saved Markdown previews, regeneration, individual downloads and ZIP export. Saves coordinate with repository deletion and concurrent generation. Remote Markdown images do not automatically load.
- Enforced the actual streamed multipart upload limit before unbounded temporary spooling, including chunked requests without a trustworthy content length.
- Made temporary GitHub DNS failures retryable. Unsafe/private-address checks remain enforced.
- Tightened specialist review schema, file-reference and score validation. A score of zero is preserved; invalid findings fail the specialist. Concurrent report updates are serialized.
- Corrected Vite configuration loading, Google popup headers, proxy timeout and narrow-screen login spacing.

## Feature evidence

| Feature | Evidence and limits |
| --- | --- |
| Email signup/login, cookie session, logout | Backend and browser pass, including reload and failed-logout recovery |
| Google sign-in and account linking | 13 real verifier tests with local RSA signatures; browser lifecycle passes with explicit GIS/verifier substitutes; actual Google client/domain flow still required |
| ZIP upload, parsing and readiness | API/browser pass; traversal, expansion, quota, credential-file and chunked-body limits covered |
| GitHub public/private import | Controlled clone, token encryption, URL/DNS guards and snapshot reuse covered; real public pipeline attempt blocked by environment DNS; private token not supplied |
| Original storage and re-ingestion | S3 SDK simulation and lifecycle tests pass; original checksum/snapshot preserved; live AWS not supplied |
| Files and graph browsing | Archive-backed preview, scoped graph, pagination and distinct node positions pass |
| Dense retrieval and cited chat | Real Qdrant adapter and context/relationship/citation tests pass; Gemini embeddings/answers substituted in local workflow tests |
| Reviews and architecture | Six specialists, validation/failure paths, memory import and graph/impact/flow analytics pass; actual AI review quality unmeasured |
| Engineering memory | Creation, search/filter combinations, resolution counts, source navigation, owner isolation and deletion pass |
| Documentation | All ten types tested through API; generate/regenerate/export/reload tested in browser |
| Timeline | Snapshot-backed commits, hotspots, contributors, complexity and file-history APIs covered; shallow history disclosed; no dedicated timeline UI is claimed |
| Jobs, retries and cleanup | Retry, lease recovery, cancellation, idempotency, per-store deletion progress and cascades covered locally; PostgreSQL concurrency test remains unrun |
| Health and migrations | Service readiness/degraded response and existing-user migration tested; PostgreSQL DDL compiled; live PostgreSQL migration unrun |
| Frontend and packaging | Lint/build, mobile browser checks, dependency audit, source manifest and ZIP CRC checked |

## Verification boundary

The restored final source passes **70 backend tests**, **27 production-build browser checks**, and **2 separate real Neo4j/Qdrant adapter checks**. Four default skips are the two opt-in real-store tests, the PostgreSQL concurrency test and the public GitHub network test. See `VERIFICATION.md` and `BROWSER-RESULTS.json` for details.

The public GitHub test was attempted but could not pass the application's DNS validation in this environment. A separate Git proxy connectivity probe succeeded; that is not an end-to-end import pass, and the DNS safety guard was not bypassed.

This is a tested source checkpoint, not a completed live deployment. Real Google consent/origin configuration, Gemini access and response quality, AWS permissions, live PostgreSQL locking, private GitHub access, complete Docker startup and production load still need the target environment. Follow `GOOGLE_SIGN_IN.md`, `SETUP.md` and `EMERGENT_HANDOFF.md` for those checks.

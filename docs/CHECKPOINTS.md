# Implementation checkpoints

These checkpoints describe the delivered source and the evidence for each phase. They are not separate cloud deployments or a claim that credentials were supplied.

| Phase | Source checkpoint | Verification |
| --- | --- | --- |
| 1. Audit | Supplied ZIP inspected; React UI preserved; MongoDB/local-disk/TF-IDF-only baseline identified; no tests in the original archive | Original file inventory and SHA-256 in `AUDIT.json` |
| 2. Foundation | Configuration, startup lifecycle, authorization, input bounds, cookie/origin handling, API errors, dependency installation | Backend auth/security tests, Python checks, frontend lint/build |
| 3. PostgreSQL | Relational tables, foreign keys, indexes, connection pool, immutable initial Alembic revision; MongoDB runtime removed | Migration/schema check on SQLite; PostgreSQL DDL generated; **live PostgreSQL test remains opt-in/unrun here** |
| 4. S3 and Neo4j | Stable original archives, isolated temporary processing, file manifests/previews, stable graph, retryable version-aware cleanup | Real Neo4j test passed; boto3/S3 simulation and lifecycle tests passed; **AWS bucket not supplied** |
| 5. Qdrant | Actual dense-vector adapter, repository filters, named-vector model fingerprint, Gemini embedding client | Real Qdrant server test passed using deterministic test embeddings; **live Gemini embeddings not supplied** |
| 6. Hybrid retrieval | Semantic candidates plus graph neighborhoods, relationships, evidence, persisted citations and UI source links | Backend and browser checks passed with AI substitutes; **live answer quality not measured** |
| 7. End-to-end checks | Auth → import → status → files/graph → chat → repeat indexing → cleanup, plus failure paths | 70 backend tests; 2 separate real-store tests; 27 production-browser checks; **target deployment checks remain explicit** |
| 8. Source handoff | Setup scripts, environment templates, Docker files, architecture, test report, dependency locks and verified source archive | ZIP CRC/manifest and artifact-content checks |

The source archive is one consolidated checkpoint. The unchanged original input is identified by its SHA-256 and remains the starting reference; no additional unseen archives were assumed to be a better baseline.

Follow-up product audit: repaired Google sign-in and identity linking, added the documentation workspace, bounded chunked uploads, tightened review validation, preserved transient DNS retries, and expanded migration/authentication/browser coverage. See `PRODUCT_AUDIT.md` and `GOOGLE_SIGN_IN.md`.

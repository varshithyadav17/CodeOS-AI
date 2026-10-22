# Live verification — 23 October 2026 (India)

## Current status

The free API is live at https://codeos-api.onrender.com. Authenticated readiness passes PostgreSQL, Backblaze archives, Neo4j and Qdrant. Generation uses `gemini-3.5-flash-lite`; embeddings remain `gemini-embedding-001`, 768 dimensions.

The owner restored the current Aura connection after an authentication regression. Actual graph-backed chat now passes. All four Neo4j settings use manual `sync: false` values so later Blueprint syncs preserve the saved connection.

The tested release merged through PR #1. Vercel already follows `main`; the Blueprint now explicitly points the existing Render service at `main`. Final production proxy/cookie/SPA checks and cleanup are in progress. Personal Google consent requires a real account on the production origin.

## Actual checks

| Flow | Result | Scope |
| --- | --- | --- |
| Provider readiness | Passed | PostgreSQL, private archives, Neo4j and Qdrant; current generation model configured |
| Authentication | Passed | Signup, Secure cookie session, session reload, logout rejection and sign-in again |
| Google configuration | Configured | Browser-bound challenge enabled and full client ID syntax checked; personal consent unverified |
| ZIP ingestion/re-ingestion | Passed | Real archive storage, parsing, graph writes, Gemini embeddings and reuse of the stored archive |
| File preview/graph | Passed | Original archive extraction, four nodes and four relationships for a two-file QA repository |
| Free-model chat | Passed | Actual Flash-Lite answer, two sources and four graph relationships |
| Architecture | Passed | Four graph views, cycle/dead-code checks, impact and execution flow |
| Dashboard/Memory | Passed | Indexed statistics; memory creation, edit, search, deletion and idempotent review import |
| Documentation | Passed | Actual Flash-Lite README generation; persistence and ZIP export also verified earlier |
| Review | Passed | All six specialists completed with actual Flash-Lite output; manager produced a non-fallback summary and action plan |
| Public GitHub/Timeline | Passed | Real Spoon-Knife clone/embeddings; commit, README history and contributor retained; shallow diff counts explicitly unavailable |
| Coordinated deletion | Passed once; final cleanup pending | First QA GitHub import removed across SQL, graph, vectors and archive versions. Two saved QA repositories retained for final proxy verification |
| UI verification | Passed in CI | All 31 browser checks, zero uncaught errors; AI, Google and populated Timeline scenarios use explicit substitutes |

## Free AI configuration

The previous `gemini-3.8-flash` model reported five generation requests per minute and 20 per day for this project. Overloaded requests also consumed its allowance. Generation and retries now share a paced queue, provider cooldowns reach waiting calls, and daily quota errors are not retried as minute limits. Background reviews may take several minutes; interactive routes keep a 105-second deadline.

The demo selects Google's supported free `gemini-3.5-flash-lite`, with medium thinking and deprecated sampling parameters omitted. Actual chat, documentation, six review specialists and manager calls passed. No billing, paid key or extra project was enabled. Provider quotas and availability can still change.

The limiter operates within the single API process, by API key/model, at a conservative five requests per minute. Multiple independent processes would require a shared limiter.

## Regression evidence

- Local: 83 backend tests passed, four opt-in skips; Ruff and frontend lint/build passed.
- Full CI on `bd1e190`: 84 backend tests passed, three opt-in skips; Docker/non-root execution and two concurrent 512 MB startup containers passed. All 31 browser checks passed with zero uncaught errors using Chrome 155.0.8059.39.
- Evidence: https://github.com/varshithyadav17/CodeOS-AI/actions/runs/39871516005
- Regressions cover actual Google SDK error shapes, supported Flash-Lite parameters, concurrent generation with overloaded requests, shared cooldowns, cancellation, and actual shallow Git history including an empty commit message.
- Main-branch CI additionally runs an optional anonymous diagnostic of the public login and real Google button. No Google response is substituted and no account sign-in or consent is attempted. External availability does not block backend releases; inspect the diagnostic result separately.

## Remaining release checks

1. Confirm main-branch deployments and verify production API forwarding, cookies and SPA routes.
2. Delete the two saved disposable QA repositories through coordinated cleanup after those checks.
3. Inspect the real public Google button diagnostic, then complete personal Google consent on the canonical origin. Private GitHub token access was not tested.

Free PostgreSQL expires on 21 November 2026 in India; the owner accepts this for the portfolio demo. Any older MongoDB data remains separate: no historical migration or deletion was performed. ZIP uploads have no Git history, and depth-one GitHub snapshots cannot provide full historical churn. No production load or availability guarantee is made.

References: [Flash-Lite model](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite), [free pricing](https://ai.google.dev/gemini-api/docs/pricing), [model parameter changes](https://ai.google.dev/gemini-api/docs/whats-new-gemini-3.6).

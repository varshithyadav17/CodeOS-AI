# Live verification — 23 October 2026 (India)

## Current status

The free API is live at https://codeos-api.onrender.com. It now selects `gemini-3.5-flash-lite`; embeddings remain `gemini-embedding-001`, 768 dimensions. PostgreSQL, Backblaze archives and Qdrant pass authenticated readiness.

**Neo4j currently rejects authentication.** It passed actual graph/indexing operations earlier, but after the latest Blueprint deployment readiness became degraded and a graph request returned `Neo.ClientError.Security.Unauthorized`. The exact cause has not been established. The Blueprint fixed username/database to `neo4j`; the safeguard makes both manual `sync: false` settings alongside URI/password. Re-save the four connection settings from the current Aura instance directly in Render and deploy. Do not recreate the instance or send its password in chat.

Production still serves the earlier `main`; final frontend cutover is pending. The candidate Vercel configuration forwards `/api` to the actual backend. Protected preview access was denied to the connected fetch operation. Personal Google consent needs a real account on the final production origin.

## Actual checks

| Flow | Result | Scope |
| --- | --- | --- |
| Provider readiness | Earlier pass; Neo4j now blocked | PostgreSQL, archives and Qdrant remain healthy; current graph authentication must be restored |
| Authentication | Passed | Signup, Secure cookie session, session reload, logout rejection and sign-in again |
| Google configuration | Configured | Browser-bound challenge enabled and client ID syntax checked; real consent unverified |
| ZIP ingestion/re-ingestion | Passed before current graph failure | Real archive storage, parsing, graph writes, Gemini embeddings and reuse of the stored archive |
| File preview/graph | Passed before current failure | Original archive extraction, four nodes and four relationships for a two-file QA repository |
| Chat | Passed with prior generation model | Actual Gemini answer, source citations and graph relationships; provider errors returned honestly |
| Architecture | Passed | Four graph views, cycle/dead-code checks, impact and execution flow |
| Dashboard/Memory | Passed | Indexed statistics; memory creation, edit, search, deletion and idempotent review import |
| Documentation | Passed with prior generation model | Real README generation, persisted content and ZIP export |
| Review | Live completion pending | Earlier runs exposed minute quotas and overloaded responses; the later run reached the old model's daily allowance. Recheck six specialists and manager after graph recovery |
| Public GitHub/Timeline | Passed | Real Spoon-Knife clone/embeddings; corrected import retained commit, README history and contributor, explicitly marking unavailable shallow diff counts |
| Coordinated deletion | Passed once; remaining cleanup pending | First QA GitHub import removed across SQL, graph, vectors and archive versions. Keep the two remaining QA repositories until graph access is restored |
| UI verification | Passed in CI | All 31 browser checks; zero uncaught errors. AI, Google and populated Timeline scenarios use explicit substitutes |

## Free AI configuration

The previous `gemini-3.8-flash` model reported five generation requests per minute and 20 per day for this project. Overloaded requests also consumed its allowance. Generation and retries now share a paced queue, provider cooldowns reach waiting calls, and daily quota errors are not retried as minute limits. Background reviews may take several minutes; interactive routes keep a 105-second deadline.

The demo selects Google's supported free `gemini-3.5-flash-lite`, with medium thinking and deprecated sampling parameters omitted. No billing, paid key or extra project was enabled. Actual Flash-Lite generation/review verification is blocked by Neo4j authentication; its active project quota has not been measured or guaranteed.

The limiter operates within the single API process, by API key/model, at a conservative five requests per minute. Multiple independent processes would require a shared limiter.

## Regression evidence

- Local on `3674eea`: 83 backend tests passed, four opt-in skips, and Ruff passed. Frontend lint/build passed on the pacing change; the model change did not alter frontend source.
- Full CI on `3674eea`: 84 backend tests passed, three opt-in skips; Docker/non-root execution and two concurrent 512 MB startup containers passed. All 31 browser checks passed with zero uncaught errors using Chrome 155.0.8059.39.
- Evidence: https://github.com/varshithyadav17/CodeOS-AI/actions/runs/39870007877
- New regressions cover actual Google SDK error shapes, supported Flash-Lite parameters, concurrent generation with overloaded requests, shared cooldowns, cancellation, and actual shallow Git history including an empty commit message.

## Remaining release checks

1. Restore current Aura credentials in Render; confirm authenticated readiness and a graph request.
2. Verify actual Flash-Lite chat, documentation, six review specialists and manager output.
3. Delete the two saved disposable QA repositories through coordinated cleanup.
4. Merge the tested release, point Render at `main`, and verify production API forwarding, cookies, SPA routes and deployed commits. Vercel already follows `main`; Render currently follows the candidate branch.
5. Complete personal Google consent on the canonical production origin. Private GitHub token access was not tested.

Free PostgreSQL expires on 21 November 2026 in India; the owner accepts this for the portfolio demo. Any older MongoDB data remains separate: no historical migration or deletion was performed. ZIP uploads have no Git history, and depth-one GitHub snapshots cannot provide full historical churn. No production load or availability guarantee is made.

References: [Flash-Lite model](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite), [free pricing](https://ai.google.dev/gemini-api/docs/pricing), [model parameter changes](https://ai.google.dev/gemini-api/docs/whats-new-gemini-3.6).

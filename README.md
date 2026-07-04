# Code Intelligence Platform

A standalone, open-source full-stack application for **repository analysis,
knowledge-graph generation, AI-powered chat, multi-agent code review,
architecture intelligence, engineering memory, timeline intelligence and
AI documentation generation** — all running on your own machine.

This repository can be cloned from GitHub and started locally with **only
the commands shown below**. No private packages, no proprietary SDKs, no
platform-specific glue.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Tech Stack](#tech-stack)
4. [Project Layout](#project-layout)
5. [Prerequisites](#prerequisites)
6. [Installation](#installation)
7. [Environment Variables](#environment-variables)
8. [Running Locally](#running-locally)
9. [Production Deployment](#production-deployment)
10. [Troubleshooting](#troubleshooting)
11. [Future Roadmap](#future-roadmap)
12. [Migration Notes](#migration-notes)
13. [License](#license)

---

## Overview

The Code Intelligence Platform helps engineering teams understand large,
unfamiliar codebases. Point it at a GitHub repository or upload a ZIP and it
will parse the source with **tree-sitter**, build an **AST + knowledge
graph**, persist everything in **MongoDB**, and expose **AI chat** /
**multi-agent code review** powered by **Google Gemini**.

Capabilities preserved from earlier versions:

- JWT email/password authentication
- Google OAuth (placeholder until credentials are supplied — see below)
- GitHub and ZIP repository ingestion
- Tree-sitter parsing + AST generation
- Knowledge graph storage in MongoDB
- Hybrid retrieval (BM25 + vector-style scoring)
- AI chat over a repository
- Multi-agent code review
- Architecture intelligence
- Engineering memory
- Timeline intelligence
- AI documentation generator

---

## Architecture

```
┌────────────────────────┐        HTTPS / REST         ┌────────────────────────┐
│        Frontend        │  ─────────────────────────▶ │        Backend         │
│  React 18 + Vite       │                             │  FastAPI + Uvicorn     │
│  Tailwind + shadcn/ui  │  ◀───────────────────────── │  python-jose · passlib │
└──────────┬─────────────┘          JSON               │  GitPython · tree-sitter│
           │                                           │  google-genai (Gemini) │
           │ build artefacts (Vite)                    └──────────┬─────────────┘
           ▼                                                      │
       static files                                               ▼
                                                       ┌────────────────────────┐
                                                       │       MongoDB          │
                                                       │  (motor / pymongo)     │
                                                       └────────────────────────┘
```

* **Frontend** is a pure Vite + React 18 SPA using Tailwind CSS and the
  shadcn/ui component library. All API calls are made against
  `import.meta.env.VITE_BACKEND_URL`.
* **Backend** is FastAPI mounted under the `/api` prefix. Authentication uses
  JWT bearer tokens; passwords are hashed with bcrypt via `passlib`. The LLM
  layer talks to Gemini through the official `google-genai` SDK.
* **MongoDB** stores users, repositories, AST nodes, the knowledge graph
  edges, chat history, code-review findings and timeline events.

---

## Tech Stack

### Backend
| Concern              | Library / Tool                |
|----------------------|-------------------------------|
| Web framework        | FastAPI                       |
| ASGI server          | Uvicorn                       |
| Database driver      | Motor / PyMongo               |
| Validation           | Pydantic v2                   |
| Auth (JWT)           | python-jose, PyJWT            |
| Password hashing     | passlib + bcrypt              |
| HTTP client          | httpx, requests               |
| LLM                  | google-genai (Gemini SDK)     |
| Repo ingestion       | GitPython                     |
| Code parsing         | tree-sitter, tree-sitter-languages |
| Tests                | pytest, pytest-asyncio        |

### Frontend
| Concern              | Library / Tool                |
|----------------------|-------------------------------|
| Build tool           | **Vite 5**                    |
| Framework            | React 18 (JavaScript, no TS)  |
| Styling              | Tailwind CSS 3                |
| Components           | shadcn/ui (Radix primitives)  |
| Forms                | react-hook-form + zod         |
| Data fetching        | @tanstack/react-query, swr, axios |
| Routing              | react-router-dom 6            |
| Animation            | framer-motion                 |
| Icons                | lucide-react                  |
| Package manager      | **npm**                       |

---

## Project Layout

```
.
├── backend/
│   ├── server.py              # FastAPI application entry point
│   ├── requirements.txt       # Standalone Python dependencies
│   ├── .env.example           # Backend environment template
│   └── pytest.ini
├── frontend/
│   ├── index.html             # Vite HTML entry
│   ├── vite.config.js         # Vite + alias configuration
│   ├── package.json           # npm dependencies & scripts
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── eslint.config.js
│   ├── components.json        # shadcn/ui registry
│   ├── .env.example           # Frontend env template (VITE_*)
│   └── src/
│       ├── main.jsx           # React entry point
│       ├── App.jsx            # Top-level routes
│       ├── App.css
│       ├── index.css          # Tailwind layers + design tokens
│       ├── components/ui/     # shadcn/ui primitives
│       ├── constants/testIds/ # data-testid registry
│       ├── hooks/
│       └── lib/
├── tests/                     # Cross-cutting tests
├── .gitignore
└── README.md
```

---

## Prerequisites

| Tool     | Minimum version | Notes                                          |
|----------|-----------------|------------------------------------------------|
| Python   | 3.10            | 3.11 / 3.12 also supported                     |
| Node.js  | 18              | 20 LTS recommended                             |
| npm      | 9               | Bundled with Node.js                           |
| MongoDB  | 6.0             | Local instance or MongoDB Atlas connection URI |
| git      | 2.30            | Required for repository ingestion              |

---

## Installation

```bash
# 1. Clone
git clone <your-fork-url> code-intel-platform
cd code-intel-platform

# 2. Backend
cd backend
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env                # then edit .env

# 3. Frontend
cd ../frontend
npm install
cp .env.example .env                # then edit .env

# 4. MongoDB (skip if using Atlas)
#    macOS:   brew services start mongodb-community
#    Linux:   sudo systemctl start mongod
#    Docker:  docker run -d -p 27017:27017 --name mongo mongo:6
```

That is the **only** installation sequence — no extra scripts, no manual
patching, no private registries.

---

## Environment Variables

### `backend/.env`

| Variable                    | Required | Description                                                |
|-----------------------------|----------|------------------------------------------------------------|
| `MONGO_URL`                 | yes      | MongoDB connection URI                                     |
| `DB_NAME`                   | yes      | Database name                                              |
| `CORS_ORIGINS`              | yes      | Comma-separated list of origins; `*` allowed in dev        |
| `JWT_SECRET`                | yes      | Long random string used to sign JWTs                       |
| `JWT_ALGORITHM`             | no       | Defaults to `HS256`                                        |
| `JWT_EXPIRES_MIN`           | no       | Token lifetime in minutes (default `1440`)                 |
| `GEMINI_API_KEY`            | LLM      | Get one at <https://aistudio.google.com/apikey>            |
| `GEMINI_MODEL`              | no       | Defaults to `gemini-2.0-flash-exp`                         |
| `GOOGLE_CLIENT_ID`          | OAuth    | Required to enable Google sign-in                          |
| `GOOGLE_CLIENT_SECRET`      | OAuth    | Required to enable Google sign-in                          |
| `GOOGLE_OAUTH_REDIRECT_URI` | OAuth    | Defaults to `http://localhost:8001/api/auth/google/callback` |

> **Google OAuth is shipped as a placeholder ("coming soon") until you
> populate `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`.** The standard
> JWT email/password flow works out of the box.

### `frontend/.env`

| Variable             | Required | Description                            |
|----------------------|----------|----------------------------------------|
| `VITE_BACKEND_URL`   | yes      | Base URL of the backend (no trailing slash) |

Only variables prefixed with `VITE_` are exposed to the browser.

---

## Running Locally

Two terminals — one for the backend, one for the frontend.

### Backend

```bash
cd backend
source .venv/bin/activate
uvicorn server:app --reload --host 0.0.0.0 --port 8001
```

The API will be available at <http://localhost:8001/api>. Swagger UI lives
at <http://localhost:8001/docs>.

### Frontend

```bash
cd frontend
npm run dev
```

Open <http://localhost:5173>. Vite has hot module replacement enabled.

### Production build (frontend)

```bash
npm run build       # outputs to frontend/dist
npm run preview     # serves the built bundle on port 4173
```

---

## Production Deployment

A minimal production setup looks like this:

1. **Build** the frontend: `npm --prefix frontend run build`. Serve the
   contents of `frontend/dist` with any static-file host (Nginx, Caddy,
   Cloudflare Pages, Vercel, Netlify, S3 + CloudFront).
2. **Run** the backend with a production ASGI server, e.g.
   ```bash
   uvicorn server:app --host 0.0.0.0 --port 8001 --workers 4
   ```
   Behind a reverse proxy that terminates TLS (Nginx, Caddy, Traefik) and
   forwards everything matching `^/api/` to the backend.
3. **MongoDB** can be self-hosted or pointed at MongoDB Atlas via the
   `MONGO_URL` variable.
4. **Secrets** (`JWT_SECRET`, `GEMINI_API_KEY`, Google OAuth credentials)
   must be injected through the deployment platform's environment / secret
   manager — never commit them to git.
5. Set `CORS_ORIGINS` to the exact origin(s) of your frontend deployment
   (no `*` in production).

### Docker (optional, sketch)

```dockerfile
# backend.Dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"]
```

```dockerfile
# frontend.Dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
```

---

## Troubleshooting

**Backend won't start — `ModuleNotFoundError`**
Make sure the virtualenv is activated and reinstall:
`pip install -r requirements.txt`.

**`pymongo.errors.ServerSelectionTimeoutError`**
MongoDB isn't reachable. Verify `MONGO_URL` and that the service is
running (`mongosh` should connect).

**`401 Unauthorized` from `/api/auth/...`**
Confirm `JWT_SECRET` is identical between restarts and that the frontend
sends `Authorization: Bearer <token>`.

**Frontend shows a blank page**
Check the browser console. Most often `VITE_BACKEND_URL` is unset, so
Axios is requesting `/api/...` against the Vite dev server.

**`npm install` produces peer-dependency warnings**
The lockfile pins compatible versions; warnings (not errors) are safe to
ignore. If you see hard `ERESOLVE` errors, delete `node_modules` and
`package-lock.json`, then `npm install` again.

**Gemini calls return 403 / 400**
Generate a fresh key at <https://aistudio.google.com/apikey> and set
`GEMINI_API_KEY`. The free tier of `gemini-2.0-flash-exp` is sufficient
for development.

**Tree-sitter wheel fails to build**
Install build tooling: `apt-get install build-essential` (Debian/Ubuntu)
or `xcode-select --install` (macOS).

---

## Future Roadmap

- Switchable LLM backends (OpenAI, Anthropic, local Ollama)
- Incremental knowledge-graph updates on `git pull`
- VS Code extension that surfaces architecture findings inline
- Team workspaces with role-based access control
- Webhook ingestion for GitHub / GitLab / Bitbucket
- Export findings to PDF / Markdown reports
- Native Docker Compose stack with one-command bootstrap

---

## Migration Notes

This codebase was migrated from an internal platform-specific stack to a
fully open-source standalone application. The migration removed every
proprietary dependency and replaced platform-managed services with
standard equivalents:

| Removed                                  | Replaced with                             |
|------------------------------------------|-------------------------------------------|
| Internal LLM wrapper                     | `google-genai` SDK (Gemini)               |
| Internal Google OAuth helper             | Standard Google OAuth 2.0 endpoints       |
| Create React App + CRACO + Yarn          | Vite 5 + npm                              |
| Visual-edit / preview build plugins      | Removed entirely                          |
| Internal universal API key               | Standard `GEMINI_API_KEY` env variable    |

If you encounter any reference to the legacy stack outside this section,
please open an issue — it is a bug.

---

## License

MIT. See `LICENSE` (add your own before publishing).

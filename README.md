<<<<<<< HEAD
# LLM Comparison Arena

A BYOK (bring-your-own-key) web app for comparing responses from Claude, GPT, and Gemini side by side — scored on both LLM-judged metrics (groundedness, correctness, completeness, safety) and deterministic metrics (cost, latency, coding pass-rate, consistency). Started as a single-response LLM judge dashboard; now a full head-to-head arena.
=======
# LLM Evaluation Pipeline

> An LLM-as-Judge evaluation pipeline for scoring AI agent responses with a full analytics dashboard.
>>>>>>> ef33cd5a83bae91c06388e0696ae70432066b3ed

---

## Overview

<<<<<<< HEAD
Pick two models from any combination of Anthropic/OpenAI/Google, paste in your own API keys, and either:
- **Custom prompt mode** — ask both models a single question and compare the two responses directly, or
- **Suite mode** — run both models against a curated 5-item test suite (`reasoning`, `rag_faithfulness`, `safety`, or `coding`) and get an aggregated score.

Every run is scored on:
- **Groundedness** — is the answer supported by the given context (suite mode only, where applicable)?
- **Correctness** — does it match the expected/reference answer?
- **Completeness** — does it cover the full scope of the question?
- **Safety** — is the output free of harmful/inappropriate content?
- **Cost** — computed from real token counts × provider pricing tables.
- **Latency (p50)** — wall-clock response time.
- **Coding pass-rate** — for the `coding` suite, generated code is extracted and executed against real unit tests in an isolated subprocess with a timeout.
- **Consistency** — run the same prompt 1–3 times per model and score how stable the outputs are (`1 − stdev` of per-run judge scores).

A winner is declared per run based on the aggregate score, and everything is persisted to SQLite so past runs show up in history.

**BYOK security**: API keys are held only in browser memory (React state) for the duration of the session and sent as per-request headers. They are never logged, never written to disk, and never touch `localStorage`/`sessionStorage`/cookies.

---

## Architecture

```
┌─────────────────────┐        ┌──────────────────────────┐
│  React (Vite/TS)     │  BYOK  │  FastAPI backend         │
│  frontend-src/  ───► │  keys  │  api/compare_routes.py   │
│  (built into         │  as    │                          │
│   frontend/)          │ headers│  ┌────────────────────┐ │
└─────────┬────────────┘        │  │ providers/          │ │
          │ SSE /stream/{id}    │  │  anthropic/openai/   │ │
          │ POST /compare       │  │  gemini adapters     │ │
          └────────────────────►│  └────────────────────┘ │
                                 │  ┌────────────────────┐ │
                                 │  │ evaluation_pipeline/│ │
                                 │  │  groq_judge.py       │ │
                                 │  │  (Groq-hosted judge, │ │
                                 │  │   JSON-mode, async)  │ │
                                 │  └────────────────────┘ │
                                 │  ┌────────────────────┐ │
                                 │  │ metrics/             │ │
                                 │  │  cost.py latency.py  │ │
                                 │  │  code_runner.py       │ │
                                 │  └────────────────────┘ │
                                 │  ┌────────────────────┐ │
                                 │  │ database/            │ │
                                 │  │  arena_store.py       │ │
                                 │  │  (SQLite via aiosqlite)│ │
                                 │  └────────────────────┘ │
                                 └──────────────────────────┘
```

One `/compare` call fans out to both model providers concurrently, runs judge scoring via Groq (JSON-mode, `asyncio.gather` across metrics), computes cost/latency/consistency/code-pass-rate, persists the run, and streams live progress over SSE to the frontend.
=======
The LLM Evaluation Pipeline is an analytics platform that scores AI agent responses across multiple quality dimensions — **groundedness**, **relevance**, **safety**, and **completeness** — and surfaces the results through a FastAPI-powered dashboard. Built for monitoring agent quality across production workflows.
>>>>>>> ef33cd5a83bae91c06388e0696ae70432066b3ed

---

## Features

<<<<<<< HEAD
```
providers/            — ModelProvider Protocol + Anthropic/OpenAI/Gemini adapters (never call paid APIs in tests — all mocked)
metrics/               — cost.py (pricing tables), latency.py (p50), code_runner.py (sandboxed subprocess execution)
evaluation_pipeline/   — groq_judge.py (LLM-as-judge, JSON-mode + async), metric_definitions.py, score_calculator.py (legacy single-response path)
suites/                — reasoning.json, rag_faithfulness.json, safety.json, coding.json (5 items each)
database/              — arena_store.py (runs/model_results/metric_scores tables) + evaluation_store.py (legacy)
api/                   — dashboard_server.py (FastAPI app + static mount), compare_routes.py (/compare, /suites, /runs, /stream), evaluation_routes.py (legacy /evaluate)
frontend-src/          — React + TypeScript + Vite + Tailwind v4 + Recharts source (Compare / Results / History pages)
frontend/              — built static output served by FastAPI at /dashboard and /static (generated by `npm run build`, do not hand-edit)
tests/                 — full backend test suite (providers, metrics, judge, suites, code runner, compare routes)
docs/                  — PLAN.md, CONTEXT.md, PROGRESS.md, SESSION_LOG.md, ERROR_LOG.md (living project trackers)
```
=======
- **LLM-as-Judge evaluation pipeline** that scores AI agent responses on groundedness, relevance, safety, and completeness
- **Analytics dashboard** powered by FastAPI for tracking model and agent quality over time
- **Multi-dimensional scoring** for monitoring response quality across production workflows
>>>>>>> ef33cd5a83bae91c06388e0696ae70432066b3ed

---

## Tech Stack

<<<<<<< HEAD
- **Backend** — Python, FastAPI, Pydantic v2, aiosqlite, sse-starlette, httpx
- **LLM Judge** — Groq API (Llama), JSON-mode structured output, async/parallel metric scoring
- **Model providers** — Anthropic, OpenAI, Google Gemini SDKs (BYOK — keys never touch server env/disk/logs)
- **Frontend** — React 19 + TypeScript + Vite + Tailwind CSS v4 (CSS-first `@theme`) + Recharts + react-router-dom (`HashRouter`)
- **Testing** — pytest + pytest-asyncio, ruff, mypy
- **Deploy** — Docker (multi-stage: Node build stage + Python runtime), Render (backend), Vercel (optional standalone frontend)

---

## Getting Started (local dev)

**1. Clone and set up the backend**
```bash
git clone https://github.com/gnanadeepgudapati/AI-Evaluation-Dashboard.git
cd AI-Evaluation-Dashboard
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
cp .env.example .env        # add your GROQ_API_KEY (used by the judge) — get a free key at groq.com
```

**2. Run the backend**
```bash
uvicorn api.dashboard_server:app --reload
```
This serves both the API and the pre-built `frontend/` at `http://127.0.0.1:8000/dashboard`.

**3. (Optional) Frontend dev mode with hot reload**
```bash
cd frontend-src
npm install
npm run dev
```
The Vite dev server proxies `/compare`, `/runs`, `/suites`, `/stream`, `/evaluate`, `/evaluations` to `http://localhost:8000`, so run the backend (step 2) alongside it.

**4. Build the frontend for production**
```bash
cd frontend-src
npm run build
=======
| Layer | Technology |
|---|---|
| **Language** | Python |
| **API Framework** | FastAPI |
| **Database** | PostgreSQL |
| **LLM Provider** | OpenAI |

---

## Architecture

```
┌────────────────┐    ┌─────────────────────┐    ┌──────────────────┐
│  Agent         │──▶│ LLM-as-Judge        │──▶│  PostgreSQL      │
│  Responses     │    │ Scoring             │    │  (scores store)  │
└────────────────┘    └─────────────────────┘    └──────────────────┘
                              │                          │
                              ▼                          ▼
                      ┌───────────────┐         ┌──────────────────┐
                      │  Multi-dim    │         │  FastAPI         │
                      │  Quality      │         │  Analytics       │
                      │  Metrics      │         │  Dashboard       │
                      └───────────────┘         └──────────────────┘
>>>>>>> ef33cd5a83bae91c06388e0696ae70432066b3ed
```
Output is written to `../frontend`, which FastAPI serves directly — no separate frontend deploy needed for the all-in-one Docker/Render path.

**5. Try it out**
- Go to `http://127.0.0.1:8000/dashboard`, paste in your own Anthropic/OpenAI/Gemini API key(s) for the providers you want to compare, pick two models, and run a comparison — or view the Results page in **demo mode** (no keys required) to see a pre-recorded example.

---

## Contact

<<<<<<< HEAD
**Arena (current):**
- `POST /compare` — run a head-to-head comparison (custom prompt or suite mode), BYOK keys via `X-Anthropic-Key` / `X-OpenAI-Key` / `X-Gemini-Key` headers
- `GET /suites` — list available test suites
- `GET /runs` — paginated list of past comparison runs
- `GET /runs/{run_id}` — full detail for one run
- `GET /stream/{run_id}` — SSE live progress (`started` → `model_a_done`/`model_b_done` → `judge_done` → `complete`)

**Legacy (single-response judge, still supported):**
- `POST /evaluate`, `GET /evaluations`, `GET /evaluations/{id}`

Auto-generated interactive API docs: `http://127.0.0.1:8000/docs`

---

## Running Tests

```bash
pytest tests/ -v
ruff check .
mypy .
```
All provider/judge calls in tests are mocked — the suite never makes real, paid API calls.

---

## Deployment

**Docker (recommended, all-in-one)**
```bash
docker build -t llm-arena .
docker run -p 8000:8000 --env-file .env llm-arena
```
The `Dockerfile` is multi-stage: a Node stage builds `frontend-src/` into `frontend/`, then a slim Python stage installs backend deps and serves everything from one container.

**Render**
`render.yaml` deploys the Docker image as a web service. Set `GROQ_API_KEY` as a secret environment variable in the Render dashboard (used only for the judge — end-user BYOK keys are never stored server-side).

**Vercel (optional, frontend-only)**
`vercel.json` builds `frontend-src/` as a standalone static SPA (useful if you want the frontend on a CDN separate from the API). Set `VITE_API_BASE_URL` to your backend's URL (e.g. the Render deployment) at build time so API calls resolve correctly across origins.

---

## Build Phases

- **Phase 0 — Planning** ✅ Tracking docs (`PLAN.md`, `CONTEXT.md`, `PROGRESS.md`, `SESSION_LOG.md`, `ERROR_LOG.md`).
- **Phase 1 — Core compare loop** ✅ Provider adapters, cost/latency metrics, SQLite arena store, `/compare` for custom prompts.
- **Phase 2 — Suites + judge upgrade** ✅ 4 curated test suites, async JSON-mode judge, sandboxed code runner, consistency scoring.
- **Phase 3 — React frontend** ✅ Vite/React/TS/Tailwind/Recharts app: Compare, Results, History pages, SSE progress, demo mode.
- **Phase 4 — Deploy** ✅ Dockerfile, `render.yaml`, `vercel.json`, this README.

---

## Why This Matters

Picking between LLM providers shouldn't mean trusting vibes or a single vendor's benchmark. This app runs the same prompt (or the same curated test suite) against multiple real models side by side, scores them the same way every time, and tracks cost and latency alongside quality — so the comparison is systematic and repeatable rather than anecdotal.
=======
**Gnanadeep Gudapati** — [gnanadeepgudapati@gmail.com](mailto:gnanadeepgudapati@gmail.com) · [LinkedIn](https://linkedin.com/in/gnanadeepgudapati)
>>>>>>> ef33cd5a83bae91c06388e0696ae70432066b3ed

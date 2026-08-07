# LLM Comparison Arena

A BYOK (bring-your-own-key) web app for comparing responses from Claude, GPT, and Gemini side by side — scored on both LLM-judged metrics (groundedness, correctness, completeness, safety) and deterministic metrics (cost, latency, coding pass-rate, consistency). Started as a single-response LLM judge dashboard; now a full head-to-head arena.

---

## Overview

Pick 2–4 models from any combination of Anthropic/OpenAI/Google, paste in your own API keys, and either:
- **Custom prompt mode** — ask every selected model a single question and compare the responses side by side, or
- **Suite mode** — run every selected model against a curated 5-item test suite (`reasoning`, `rag_faithfulness`, `safety`, or `coding`) and get an aggregated score.

Every run is scored on:
- **Groundedness** — is the answer supported by the given context (suite mode only, where applicable)?
- **Correctness** — does it match the expected/reference answer?
- **Completeness** — does it cover the full scope of the question?
- **Safety** — is the output free of harmful/inappropriate content?
- **Cost** — computed from real token counts × provider pricing tables.
- **Cost projections** — cost-per-task and cost-per-1k-tasks, extrapolated from the measured run so you can compare providers at production volume, not just per-call.
- **Tokens/sec** — an estimated throughput figure per model.
- **Latency (p50)** — wall-clock response time.
- **Coding pass-rate** — for the `coding` suite, generated code is extracted and executed against real unit tests in an isolated subprocess with a timeout.
- **Consistency** — run the same prompt 1–3 times per model and score how stable the outputs are (`1 − stdev` of per-run judge scores).

Every run produces a ranked leaderboard across all selected models, and a per-run **report page** (with a printable/PDF layout and a downloadable `.md` export) summarizing the full comparison. A winner is declared per run based on the aggregate score, and everything is persisted to SQLite so past runs show up in history.

**BYOK security**: API keys are held only in browser memory (React state) for the duration of the session and sent as per-request headers. They are never logged, never written to disk, and never touch `localStorage`/`sessionStorage`/cookies. See [Security](#security) for how keys are kept out of error messages.

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

One `/compare` call fans out to all 2–4 selected models concurrently, runs judge scoring via Groq (JSON-mode, `asyncio.gather` across metrics), computes cost/latency/consistency/code-pass-rate plus cost-per-task and tokens/sec projections, ranks the models, persists the run, and streams live progress over SSE to the frontend.

---

## Features

- **N-model arena** — compare 2–4 models at once across Anthropic, OpenAI, and Google — same prompt, same judge, same scoring every time, with a ranked leaderboard across every entrant.
- **Two run modes** — a free-form custom prompt, or a curated 5-item test suite (`reasoning`, `rag_faithfulness`, `safety`, `coding`).
- **LLM-as-judge scoring** on groundedness, correctness, completeness, and safety, via a Groq-hosted judge using JSON-mode structured output with metrics scored in parallel.
- **Deterministic metrics alongside quality** — real token-count-based cost (plus cost-per-task/cost-per-1k projections), tokens/sec, p50 latency, and consistency across repeated runs.
- **Executable coding evaluation** — code from the `coding` suite is extracted and run against real unit tests in a sandboxed subprocess with a timeout, so the pass-rate is measured, not judged.
- **Live progress over SSE** — the UI streams `started` → `model_done` (once per selected model) → `judge_done` → `complete` instead of blocking on one long request.
- **Report page** — a per-run report view with a print-friendly layout for PDF export (via the browser's print dialog) and a one-click `.md` markdown export for sharing or archiving results outside the app.
- **Run history** — every comparison is persisted to SQLite and browsable, with charts on the Results and History pages.
- **Demo mode** — view a pre-recorded example run with no API keys required.
- **BYOK by design** — keys live in browser memory only, travel as per-request headers, and are stripped from any error text before it is stored or returned.

---

## Project Structure

```
providers/            — ModelProvider Protocol + Anthropic/OpenAI/Gemini adapters (never call paid APIs in tests — all mocked)
metrics/               — cost.py (pricing tables), latency.py (p50), code_runner.py (sandboxed subprocess execution)
evaluation_pipeline/   — groq_judge.py (LLM-as-judge, JSON-mode + async), metric_definitions.py, score_calculator.py (legacy single-response path)
suites/                — reasoning.json, rag_faithfulness.json, safety.json, coding.json (5 items each)
database/              — arena_store.py (runs/model_results/metric_scores tables) + evaluation_store.py (legacy)
api/                   — dashboard_server.py (FastAPI app + static mount), compare_routes.py (/compare, /suites, /runs, /stream), evaluation_routes.py (legacy /evaluate)
frontend-src/          — React + TypeScript + Vite + Tailwind v4 + Recharts source (Compare / Results / History pages)
frontend/              — built static output served by FastAPI at /dashboard and /static (generated by `npm run build`, do not hand-edit)
tests/                 — full backend test suite (providers, metrics, judge, suites, code runner, compare routes, secret redaction)
docs/                  — PLAN.md, CONTEXT.md, PROGRESS.md, SESSION_LOG.md, ERROR_LOG.md (living project trackers)
```

---

## Tech Stack

- **Backend** — Python 3.11+, FastAPI, Pydantic v2, aiosqlite, sse-starlette, httpx
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

Only `GROQ_API_KEY` is required — it powers the judge. The `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` entries in `.env.example` exist purely for manual local adapter testing; `/compare` never reads them, since provider keys arrive per-request from the browser.

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
```
Output is written to `../frontend`, which FastAPI serves directly — no separate frontend deploy needed for the all-in-one Docker/Render path.

**5. Try it out**
- Go to `http://127.0.0.1:8000/dashboard`, paste in your own Anthropic/OpenAI/Gemini API key(s) for the providers you want to compare, pick 2–4 models, and run a comparison — or view the Results page in **demo mode** (no keys required) to see a pre-recorded example.

---

## API Reference

**Arena (current):**
- `POST /compare` — run an N-model comparison (custom prompt or suite mode) across `models: [{provider, model}, ...]` (2–4 entries), BYOK keys via `X-Anthropic-Key` / `X-OpenAI-Key` / `X-Gemini-Key` headers
- `GET /suites` — list available test suites
- `GET /runs` — paginated list of past comparison runs
- `GET /runs/{run_id}` — full detail for one run, including the ranked leaderboard
- `GET /runs/{run_id}/report.md` — the same run rendered as a downloadable Markdown report
- `GET /stream/{run_id}` — SSE live progress (`started` → `model_done` × N → `judge_done` → `complete`)

**Legacy (single-response judge, still supported):**
- `POST /evaluate`, `GET /evaluations`, `GET /evaluations/{id}`

Auto-generated interactive API docs: `http://127.0.0.1:8000/docs`

---

## Security

The arena handles other people's API keys, so key material is treated as the primary asset to protect.

- **Keys are never persisted.** They live in React state for the session, travel as per-request `X-*-Key` headers, and are never written to disk, logs, `localStorage`, `sessionStorage`, or cookies. The server does not read provider keys from its own environment.
- **Provider errors are redacted before they are stored or returned.** Vendors routinely echo the submitted key back in auth-failure messages. That text becomes `ModelResult.error`, is persisted by `arena_store`, and is served from `GET /runs/{run_id}` — which requires no authentication. `redact_secrets()` in `providers/base.py` strips it on the way out.
- **Redaction matches the known key first, patterns second.** Each adapter passes the exact key in play (`redact_secrets(..., secret=api_key)`), so removal is a literal substring match and does not depend on recognizing a vendor's key shape. Regex patterns remain as a backstop for keys the server was never handed — most importantly its own Groq judge key.
- **Every real key format is covered by a regression matrix.** `tests/test_providers.py` asserts redaction against `sk-…`, `sk-proj-…`, `sk-svcacct-…`, `sk-admin-…`, `sk-ant-api03-…`, `AIza…`, and `gsk_…`, and `tests/test_compare_routes.py` asserts the key is absent from the **HTTP response body** of both `/compare` and `/runs/{run_id}`, not merely from the adapter return value.

A prior version of the pattern list failed open on modern OpenAI and Groq formats; the cause, the fix, and the prevention rule are written up as ERR-003 in [`docs/ERROR_LOG.md`](docs/ERROR_LOG.md).

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

> Render's free tier disk is ephemeral — SQLite history resets on redeploy. Attach a Render persistent disk to keep history across deploys. On startup the app backs up and migrates any existing `arena.db` automatically.

**Vercel (optional, frontend-only)**
`vercel.json` builds `frontend-src/` as a standalone static SPA (useful if you want the frontend on a CDN separate from the API). Set `VITE_API_BASE_URL` to your backend's URL (e.g. the Render deployment) at build time so API calls resolve correctly across origins.

---

## Build Phases

- **Phase 0 — Planning** ✅ Tracking docs (`PLAN.md`, `CONTEXT.md`, `PROGRESS.md`, `SESSION_LOG.md`, `ERROR_LOG.md`).
- **Phase 1 — Core compare loop** ✅ Provider adapters, cost/latency metrics, SQLite arena store, `/compare` for custom prompts.
- **Phase 2 — Suites + judge upgrade** ✅ 4 curated test suites, async JSON-mode judge, sandboxed code runner, consistency scoring.
- **Phase 3 — React frontend** ✅ Vite/React/TS/Tailwind/Recharts app: Compare, Results, History pages, SSE progress, demo mode.
- **Phase 4 — Deploy** ✅ Dockerfile, `render.yaml`, `vercel.json`, this README.
- **Phase 5 — Hardening** ✅ BYOK secret-redaction fix (ERR-003) with a full key-format regression matrix and end-to-end HTTP leak tests.
- **Phase 6 — N-model arena + reports** ✅ `/compare` takes 2–4 models (`models: [{provider, model}, ...]`) instead of a fixed model_a/model_b pair; ranked leaderboard computed at read time; cost-per-task and cost-per-1k-tasks projections plus tokens/sec added alongside existing cost/latency/consistency/coding-pass-rate metrics; a per-run report page (print-to-PDF layout + `.md` export) and `GET /runs/{run_id}/report.md`; schema v2 migration is backup-first and data-safe, with legacy v1 rows still readable; Docker build + container smoke test verified end-to-end.

---

## Why This Matters

Picking between LLM providers shouldn't mean trusting vibes or a single vendor's benchmark. This app runs the same prompt (or the same curated test suite) against multiple real models side by side, scores them the same way every time, and tracks cost and latency alongside quality — so the comparison is systematic and repeatable rather than anecdotal.

---

## Contact

**Gnanadeep Gudapati** — [gnanadeepgudapati@gmail.com](mailto:gnanadeepgudapati@gmail.com) · [LinkedIn](https://linkedin.com/in/gnanadeepgudapati)

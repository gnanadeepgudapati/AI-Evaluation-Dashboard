# PROGRESS.md

> Phase/task checklist. Status: `todo` | `in-progress` | `done` | `blocked`
> Updated after EVERY completed task, with timestamps.

---

## Phase 0 — Planning & Tracking (MANDATORY before any code)

| # | Task | Status | Completed |
|---|---|---|---|
| 0.1 | Create `docs/CONTEXT.md` | done | 2026-07-29 |
| 0.2 | Create `docs/PROGRESS.md` | done | 2026-07-29 |
| 0.3 | Create `docs/ERROR_LOG.md` | done | 2026-07-29 |
| 0.4 | Create `docs/SESSION_LOG.md` | done | 2026-07-29 |
| 0.5 | Create `docs/PLAN.md` | done | 2026-07-29 |
| 0.6 | Present `PLAN.md` for user approval | done | 2026-07-29 (user approved via "start building, finish all the way") |

---

## Phase 1 — Provider Adapters + Cost/Latency + /compare (custom prompt)

| # | Task | Status | Completed |
|---|---|---|---|
| 1.1 | Create `providers/base.py` — `ModelResponse` dataclass + `ModelProvider` Protocol | done | 2026-07-29 |
| 1.2 | Create `providers/anthropic_adapter.py` | done | 2026-07-29 |
| 1.3 | Create `providers/openai_adapter.py` | done | 2026-07-29 |
| 1.4 | Create `providers/gemini_adapter.py` | done | 2026-07-29 |
| 1.5 | Create `metrics/cost.py` (price table + `calculate_cost()`) | done | 2026-07-29 |
| 1.6 | Create `metrics/latency.py` (`p50()` helper) | done | 2026-07-29 |
| 1.7 | Create `database/arena_store.py` (runs + model_results + metric_scores tables, aiosqlite) | done | 2026-07-29 |
| 1.8 | Create `api/compare_routes.py` — `POST /compare` (custom prompt only), `GET /runs`, `GET /runs/{id}`, SSE `/stream/{run_id}` | done | 2026-07-29 |
| 1.9 | Register `compare_routes` router in `api/dashboard_server.py` | done | 2026-07-29 |
| 1.10 | Write tests: `tests/test_providers.py` (adapters mocked, never call paid APIs) | done | 2026-07-29 |
| 1.11 | Write tests: `tests/test_metrics.py` (cost math against known token counts, latency p50) | done | 2026-07-29 |
| 1.12 | Write tests: `tests/test_compare_routes.py` (compare endpoint with mocked adapters) | done | 2026-07-29 |
| 1.13 | Update `requirements.txt`, `.env.example` | done | 2026-07-29 |
| 1.14 | Run full test suite + ruff + mypy; update PROGRESS.md + SESSION_LOG.md | done | 2026-07-29 (27 passed, ruff clean, mypy clean) |

---

## Phase 2 — Suites + Judge Upgrade + Code Runner

| # | Task | Status | Completed |
|---|---|---|---|
| 2.1 | Create `suites/coding.json` (5 items + unit tests) | done | 2026-07-29 |
| 2.2 | Create `suites/reasoning.json` (5 items + expected answers) | done | 2026-07-29 |
| 2.3 | Create `suites/rag_faithfulness.json` (5 context+question pairs) | done | 2026-07-29 |
| 2.4 | Create `suites/safety.json` (5 adversarial prompts) | done | 2026-07-29 |
| 2.5 | Upgrade `evaluation_pipeline/groq_judge.py` — JSON-mode structured output + `asyncio.gather` | done | 2026-07-29 |
| 2.6 | Add `correctness` metric to judge (replaces `relevance` in arena context) | done | 2026-07-29 |
| 2.7 | Create `metrics/code_runner.py` (sandboxed subprocess, timeout, pass rate) | done | 2026-07-29 |
| 2.8 | Add consistency scoring to `POST /compare` (`consistency_runs` 1–3, variance) | done | 2026-07-29 |
| 2.9 | Create `GET /suites` endpoint in `api/compare_routes.py` | done | 2026-07-29 (built in Phase 1, populated by suite fixtures now) |
| 2.10 | Write tests: judge upgrade (mock Groq, verify JSON parse, verify async gather) | done | 2026-07-29 |
| 2.11 | Write tests: `code_runner` (passing, failing, timeout, malicious-input cases) | done | 2026-07-29 |
| 2.12 | Write tests: suite loading + /suites endpoint | done | 2026-07-29 |
| 2.13 | Run full test suite + ruff + mypy; update PROGRESS.md + SESSION_LOG.md | done | 2026-07-29 (54 passed, ruff clean, mypy clean) |

---

## Phase 3 — React Frontend

| # | Task | Status | Completed |
|---|---|---|---|
| 3.1 | Scaffold `frontend-src/` with Vite + React + TypeScript + Tailwind + Recharts | todo | — |
| 3.2 | Create shared types in `frontend-src/src/types/` | todo | — |
| 3.3 | Create `Compare` page — model picker, BYOK key inputs, suite/custom-prompt picker | todo | — |
| 3.4 | Wire SSE live progress to Compare page | todo | — |
| 3.5 | Create `Results` page — side-by-side cards, radar chart, cost/latency bar charts, winner summary | todo | — |
| 3.6 | Create `History` page — table of past runs with winner highlight | todo | — |
| 3.7 | Implement demo mode — load `demo/demo_results.json` when no API key present | todo | — |
| 3.8 | Configure Vite to build into `frontend/` (FastAPI static mount) | todo | — |
| 3.9 | Create `demo/demo_results.json` pre-recorded results | todo | — |
| 3.10 | Run build + verify FastAPI serves React app correctly | todo | — |
| 3.11 | Update PROGRESS.md + SESSION_LOG.md | todo | — |

---

## Phase 4 — Deploy

| # | Task | Status | Completed |
|---|---|---|---|
| 4.1 | Create `Dockerfile` for FastAPI backend | todo | — |
| 4.2 | Create `vercel.json` for frontend (Vercel) | todo | — |
| 4.3 | Create `render.yaml` for backend (Render) | todo | — |
| 4.4 | Update `README.md` — live link, demo GIF, setup instructions | todo | — |
| 4.5 | Final: run full test suite + lint + type check | todo | — |
| 4.6 | Update PROGRESS.md + SESSION_LOG.md | todo | — |

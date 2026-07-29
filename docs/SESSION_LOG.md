# SESSION_LOG.md

> Per work session: date, what was attempted, what changed (files touched), what's next.
> **Append-only.** Never edit or delete past entries.

---

## Session 001 — 2026-07-29

### Attempted
- Phase 0: Create all planning and tracking documents before any application code.
- Full review of existing codebase by reading source files from GitHub.

### Codebase State at Session Start
- FastAPI app serving vanilla HTML dashboard
- Single-model evaluation only (POST /evaluate → Groq judge → SQLite)
- Judge: sequential regex-parsed calls, no JSON mode, no async gather
- DB: single flat `evaluations` table
- Tests: empty placeholder file
- No provider adapters, no cost/latency metrics, no comparison features

### Files Changed / Created
- `docs/CONTEXT.md` — created (architecture, API contracts, DB schema, decisions)
- `docs/PROGRESS.md` — created (phase/task checklist)
- `docs/ERROR_LOG.md` — created (template)
- `docs/SESSION_LOG.md` — created (this file)
- `docs/PLAN.md` — created (full implementation plan, pending user approval)

### What's Next
- Await user approval of `docs/PLAN.md`
- Upon approval: begin Phase 1 (provider adapters + cost/latency + /compare endpoint)

---

## Session 002 — 2026-07-29

### Attempted
- User approved the plan implicitly ("start building, finish all the way — I'll provide resources/keys at the end") and asked to proceed through all phases.
- Executed Phase 1 in full: provider adapters, cost/latency metrics, arena SQLite store, `/compare` + `/suites` + `/runs` + SSE endpoints, tests, dependency install, lint/type gate.

### Files Changed / Created
- `providers/anthropic_adapter.py`, `providers/openai_adapter.py`, `providers/gemini_adapter.py` — created (each wraps its SDK with `asyncio.wait_for` timeout, redacts keys on error, never raises)
- `metrics/__init__.py`, `metrics/cost.py`, `metrics/latency.py` — created
- `database/arena_store.py` — created (aiosqlite, `runs`/`model_results`/`metric_scores` tables)
- `api/models.py` — created (Pydantic v2 contracts: `CompareRequest` with prompt-XOR-suite validator, `ModelResult`, `CompareResponse`, etc.)
- `api/compare_routes.py` — created (`POST /compare` for custom prompts — suite mode deferred to Phase 2 and returns 501; `GET /suites`, `GET /runs`, `GET /runs/{id}`, SSE `GET /stream/{run_id}` backed by an in-memory per-run `asyncio.Queue`)
- `api/dashboard_server.py` — edited: registered `compare_router`, switched `@app.on_event("startup")` to a `lifespan` context manager (removes FastAPI deprecation warning) that calls `initialize_arena_db()`
- `evaluation_pipeline/groq_judge.py` — edited: guarded `chat_response.choices[0].message.content or ""` for mypy (Groq SDK types `content` as `str | None`)
- `api/evaluation_routes.py` — edited: `raise ... from e` for proper exception chaining (ruff B904)
- `tests/test_providers.py`, `tests/test_metrics.py`, `tests/test_compare_routes.py` — created (27 tests total; adapters/judge mocked, no live API calls)
- `pyproject.toml` — created: ruff config (`select = E,F,I,UP,B`; `E501` ignored — long judge-prompt strings; `providers/*_adapter.py` exempt from blind-except since catching broad `Exception` there is intentional design), mypy config, pytest `asyncio_mode = "auto"`
- `requirements.txt` — added `groq`, `anthropic`, `openai`, `google-generativeai`, `aiosqlite`, `sse-starlette`, `pytest`, `pytest-asyncio`, `mypy`, `ruff`
- `.env.example` — added commented-out reference vars for provider keys (not consumed by `/compare`; BYOK keys travel via headers only)
- `.gitignore` — added `database/arena.db`, `.mypy_cache/`, `.ruff_cache/`, `node_modules/`, `frontend-src/dist/`
- Ran `ruff check . --fix` once across the whole repo, which also reformatted pre-existing legacy files (`database/evaluation_store.py`, `evaluation_pipeline/metric_definitions.py`, `evaluation_pipeline/score_calculator.py`) — import sorting + `Optional[X]` → `X | None`. No behavior change.

### Verification
- `pytest tests/ -v` → 27 passed
- `ruff check .` → all checks passed
- `mypy api/ providers/ metrics/ database/ evaluation_pipeline/ --ignore-missing-imports` → no issues

### Deviation from PLAN.md
- None functionally. One addition beyond the literal task list: added `pyproject.toml` (not explicitly called out in PLAN.md) to make ruff/mypy configuration reproducible and to document the intentional broad `except Exception` in adapters — recorded here rather than silently.

### What's Next
- Phase 2: suite JSON fixtures, judge upgrade (JSON-mode + async gather), `metrics/code_runner.py`, consistency scoring, suite-mode support in `/compare`.

---

## Session 003 — 2026-07-29

### Attempted
- Executed Phase 2 in full: suite fixtures, judge upgrade, code runner, consistency scoring, suite-mode `/compare`, tests, lint/type gate.

### Files Changed / Created
- `suites/coding.json`, `suites/reasoning.json`, `suites/rag_faithfulness.json`, `suites/safety.json` — created (5 items each)
- `evaluation_pipeline/groq_judge.py` — edited: added `AsyncGroq` client, `ARENA_METRICS`, `build_json_judge_prompt`/`parse_json_judge_response` (JSON-mode, graceful fallback to score=0.5/"parse error" on malformed JSON), `judge_metric_async`, `judge_all_metrics_async` (asyncio.gather). Legacy `judge_metric`/`build_judge_prompt`/`parse_judge_response` untouched for `/evaluate` backward compat. Added `correctness` metric (checks against `ground_truth` when provided, replaces `relevance` for arena use).
- `evaluation_pipeline/metric_definitions.py` — edited: added optional `ground_truth` field to `EvaluationInput`, `correctness` threshold (0.7)
- `metrics/code_runner.py` — created: `run_code_test()` writes `solution.py` + `test_solution.py` to a fresh temp dir, runs `sys.executable -m pytest` as a subprocess (no `shell=True`) with a hard timeout, always cleans up. Documented as process-isolation + timeout only, NOT a full security sandbox (no seccomp/container boundary) — flagged for anyone deploying with untrusted code.
- `api/compare_routes.py` — edited: `_run_one_model` now uses the async JSON-mode judge and supports `consistency_runs` (repeats + `1 - pstdev` of per-run average scores); new `_run_suite_for_model` executes a full suite (5 items, optionally repeated) against one model — routes to `code_runner` for the coding suite, to suite-specific judge metrics (`SUITE_JUDGE_METRICS`) for reasoning/rag_faithfulness/safety; `_load_suite_items`, `_build_item_prompt` (special-cases `rag_faithfulness`'s context+question shape), `_extract_code` (pulls a fenced code block from the model response); `/compare` now branches on `suite_id` vs `prompt` instead of returning 501 for suites; `_average_judge_score` falls back to `code_pass_rate` so the coding suite can still produce a winner.
- `tests/test_code_runner.py` — created (passing, failing assertion, syntax error, timeout, suspicious-import-doesn't-hang)
- `tests/test_suites.py` — created (all 4 suites load, 5 items each, required keys present, unique IDs)
- `tests/test_groq_judge.py` — created (JSON parsing incl. malformed-JSON fallback, `judge_metric_async` uses `response_format=json_object`, `judge_all_metrics_async` runs 4 calls concurrently)
- `tests/test_evaluation_pipeline.py` — populated (was empty): legacy `parse_judge_response`, metric thresholds, `EvaluationInput.ground_truth` default, `run_full_evaluation` aggregation with a mocked judge
- `tests/test_compare_routes.py` — extended: reasoning-suite aggregation, coding-suite via mocked `code_runner`, suite-not-found 404, `consistency_runs=2` produces `consistency == 1.0` when scores don't vary; updated existing fixture to mock `judge_all_metrics_async` instead of the retired `judge_metric` usage in this module

### Verification
- `pytest tests/ -v` → 54 passed
- `ruff check . --fix` → all checks passed
- `mypy api/ providers/ metrics/ database/ evaluation_pipeline/ --ignore-missing-imports` → no issues

### Deviation from PLAN.md
- Suite-mode aggregation design wasn't fully spelled out in PLAN.md (which focused on per-item suite *content*, not exactly how a 5-item suite collapses into one `ModelResult`). Decision made and recorded in CONTEXT.md: per suite run, `latency_ms`/all raw latencies feed `p50`, `cost_usd` and token counts are summed across items, judge metric scores are averaged across items (and, for `consistency_runs>1`, across repeats too), and `response_text` becomes a truncated per-item preview list. Coding suite skips the judge entirely and reports `code_pass_rate` instead.
- `code_runner.py` uses `sys.executable` as the interpreter (falling back to `shutil.which`) rather than only `shutil.which("python")` as literally written in PLAN.md — guarantees the subprocess uses the same environment (with pytest installed) as the running server, avoiding PATH-dependent failures.

### What's Next
- Phase 3: scaffold `frontend-src/` (Vite + React + TS + Tailwind + Recharts), build Compare/Results/History pages, SSE wiring, demo mode.

---

## Session 004 — 2026-07-29

### Attempted
- Executed Phase 3 in full: scaffolded the React frontend, built all 3 pages, wired SSE progress, demo mode, and verified the FastAPI server serves the production build correctly.

### Files Changed / Created
- `frontend-src/` — created via `npm create vite@latest -- --template react-ts` (Oxlint variant). Installed `tailwindcss` + `@tailwindcss/vite`, `recharts`, `react-router-dom@7.18.2`.
- `frontend-src/vite.config.ts` — edited: added `@tailwindcss/vite` plugin, `base: "/static/"` (matches FastAPI's existing `/static` mount so built asset URLs resolve correctly), `build.outDir: "../frontend"` with `emptyOutDir: true`, and a dev-server proxy for `/compare`, `/runs`, `/suites`, `/stream`, `/evaluate`, `/evaluations` → `http://localhost:8000`.
- `frontend-src/src/index.css` — replaced Vite boilerplate with a Tailwind v4 `@theme` block matching the legacy `frontend/index.html` dark palette (`--color-bg: #080c10`, `--color-surface`, `--color-border`, `--color-accent-blue/green/purple/orange/red`) plus `Syne`/`Space Mono` fonts.
- `frontend-src/index.html` — updated title, added Google Fonts link.
- `frontend-src/src/types/index.ts` — TypeScript interfaces mirroring `api/models.py` exactly (`ModelResult`, `CompareRequest`/`CompareResponse`, `RunSummary`/`RunsListResponse`, `SuiteMetadata`), plus a static `MODELS_BY_PROVIDER` map and `JUDGE_METRIC_LABELS`.
- `frontend-src/src/lib/api.ts` — fetch wrapper; BYOK keys are attached as `X-Anthropic-Key`/`X-OpenAI-Key`/`X-Gemini-Key` headers per-call, never persisted to any storage.
- `frontend-src/src/hooks/useEventSource.ts` — wraps native `EventSource` for `/stream/{run_id}`; documents that the caller must open the stream with a client-generated `run_id` *before* POSTing `/compare` (passing the same id in the body) since `/compare` is a single request/response, not fire-and-forget.
- `frontend-src/src/context/ArenaContext.tsx` — React context holding BYOK keys (in-memory `useState` only) and the most recent `CompareResponse`, so Results can render immediately post-run without a round trip.
- `frontend-src/src/components/` — `Layout.tsx` (nav), `ProgressBar.tsx` (5-stage SSE progress), `ModelCard.tsx` (response + tokens/cost/latency/consistency/code-pass-rate + judge scores), `RadarMetrics.tsx` (Recharts `RadarChart` overlay of both models' judge metrics), `CostLatencyCharts.tsx` (Recharts bar charts), `WinnerBanner.tsx`.
- `frontend-src/src/pages/ComparePage.tsx` — model/provider pickers, 3 BYOK password inputs, Custom Prompt/Run Suite toggle, suite picker fetched from `GET /suites`, consistency-runs selector (1/2/3), live SSE progress bar during submission, posts to `/compare` and stores the result in context before navigating to Results.
- `frontend-src/src/pages/ResultsPage.tsx` — renders `/results` (last in-session result), `/results/:runId` (fetched via `GET /runs/{id}`), or falls back to demo mode (`public/demo/demo_results.json`) when neither is available — page is never empty on first load.
- `frontend-src/src/pages/HistoryPage.tsx` — paginated table from `GET /runs`, click-through to `/results/:runId`.
- `frontend-src/src/App.tsx` — `HashRouter` (chosen over `BrowserRouter` so client-side sub-routes like `#/results` don't 404 on refresh, since FastAPI only serves `index.html` at the single `/dashboard` path, not a catch-all).
- `frontend-src/public/demo/demo_results.json` — pre-recorded Claude 3.5 Haiku vs GPT-4o-mini reasoning-suite comparison with realistic scores/costs/latencies.
- Removed unused Vite template boilerplate: `src/App.css`, `src/assets/`, `public/icons.svg`.
- `frontend/` — regenerated entirely by `npm run build` (old vanilla `index.html`/`dashboard_charts.js` replaced by the built React app's `index.html` + `assets/`).

### Verification
- `npm run build` in `frontend-src/` → succeeds (`tsc -b && vite build`), output correctly lands in `../frontend`
- `npx oxlint` → 1 benign fast-refresh warning in `ArenaContext.tsx` (exports both the provider component and a hook from the same file — acceptable, not worth splitting for this size of app)
- Started `uvicorn api.dashboard_server:app` locally and verified in a real browser:
  - `GET /dashboard` returns the built `index.html` referencing `/static/assets/*` correctly
  - Compare page renders: model/provider dropdowns, BYOK key inputs, prompt/suite toggle, consistency-runs selector
  - Results page in demo mode renders: winner banner, both model cards (response, tokens, cost, latency, consistency, judge scores), radar chart, cost/latency bar charts
  - History page renders (empty state, since no real runs exist yet without real API keys)
  - Confirmed via `grep` that no `localStorage`/`sessionStorage` calls exist anywhere in `frontend-src/src` (the only match is an explanatory code comment)
- `pytest tests/ -q` (backend) → 54 passed, unaffected by frontend work

### Deviation from PLAN.md
- Used `HashRouter` instead of a plain `BrowserRouter`, since PLAN.md didn't specify how FastAPI would serve SPA sub-routes (`/dashboard/results`, `/dashboard/history`) on a hard refresh. FastAPI currently only has a single `@app.get("/dashboard")` route, not a catch-all. `HashRouter` keeps all client routes under the single `/dashboard` URL (`/dashboard#/results`) so no backend routing changes were needed. Documented in CONTEXT.md.
- `npm audit` flagged `react-router-dom@7.12+` for a "high" severity RSC (React Server Components) mode CSRF advisory. Investigated: this only applies to apps using React Router's framework/RSC mode with server actions, which this is a pure client-side SPA does not use. Downgrading to avoid it (`npm audit fix --force` → 7.11.0) reintroduced several *other* high-severity advisories from that older version, so the decision was to stay on the latest (7.18.2) and accept the RSC-specific advisory as not applicable to our usage. Documented in CONTEXT.md.
- Removed the pre-existing vanilla `frontend/index.html` and `frontend/dashboard_charts.js` (Vite's `emptyOutDir: true` overwrites them on build) — this was the explicit intent of Phase 3 ("Replace vanilla HTML with a React/Vite/Tailwind app"), not an accidental deviation, but noting it since those files are no longer in the built output directory (still recoverable from git history if ever needed).

### What's Next
- Phase 4: `Dockerfile`, `vercel.json`, `render.yaml`, README overhaul with architecture diagram/demo instructions, final full verification (backend tests + frontend build + docs).


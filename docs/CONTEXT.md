# CONTEXT.md — Single Source of Truth

> Any future session must be able to read this file alone and continue the work.
> Update this file whenever a decision is made, architecture changes, or a contract is revised.

---

## 1. Project Goal

Upgrade **AI-Evaluation-Dashboard** from a single-response evaluation tool into a full-stack **LLM API Comparison Arena**.

Users bring their own API keys (BYOK), pick two models (Claude / GPT / Gemini), run built-in test suites or a custom prompt, and see a side-by-side comparison dashboard with:

- **LLM-judged metrics** (Groq judge, upgraded): faithfulness/groundedness, correctness vs ground truth, completeness, safety
- **Deterministic metrics**: cost per task (token usage × maintained price table), latency (p50 + per-task), coding ability (execute generated code in sandboxed subprocess → pass rate)
- **Consistency** (score variance across 3 repeated runs — NOT self-reported confidence)

---

## 2. Existing Codebase State (before upgrades)

| Component | Location | Status |
|---|---|---|
| FastAPI app | `api/dashboard_server.py` | Working — serves static frontend, health check |
| Evaluation routes | `api/evaluation_routes.py` | Working — POST /evaluate, GET /evaluations, GET /evaluations/{id} |
| Groq judge | `evaluation_pipeline/groq_judge.py` | Working but sequential, regex-parsed, no JSON mode |
| Score calculator | `evaluation_pipeline/score_calculator.py` | Working but sequential (4 blocking judge calls) |
| Metric definitions | `evaluation_pipeline/metric_definitions.py` | Pydantic v2, 4 metrics: groundedness, relevance, safety, completeness |
| Database | `database/evaluation_store.py` | SQLite, single flat `evaluations` table |
| Frontend | `frontend/index.html` + `frontend/dashboard_charts.js` | Vanilla HTML/JS, dark aesthetic |
| Tests | `tests/test_evaluation_pipeline.py` | Empty/placeholder — no real coverage |
| Env | `.env.example` | Only `GROQ_API_KEY` and `GROQ_MODEL` |

---

## 3. Target Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  React Frontend (Vite + Tailwind + Recharts)                    │
│  Screens: Compare | Results | History                           │
│  BYOK keys: React state only — never localStorage or server     │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTPS
┌──────────────────────────▼──────────────────────────────────────┐
│  FastAPI Backend                                                │
│  POST /compare  GET /suites  GET /runs  GET /runs/{id}         │
│  GET /stream/{run_id}  (SSE progress)                          │
│  POST /evaluate (legacy — keep for backward compat)            │
└──┬─────────────────────────────────┬────────────────────────────┘
   │                                 │
   ▼                                 ▼
┌──────────────────────┐   ┌─────────────────────────────────────┐
│  providers/          │   │  evaluation_pipeline/               │
│  base.py (Protocol)  │   │  groq_judge.py (upgraded)           │
│  anthropic_adapter   │   │  JSON mode + asyncio.gather         │
│  openai_adapter      │   │  metrics: cost, latency, code_runner│
│  gemini_adapter      │   └──────────────┬──────────────────────┘
└──────────────────────┘                  │
                                          ▼
                              ┌───────────────────────────┐
                              │  SQLite                   │
                              │  runs, model_results,     │
                              │  metric_scores            │
                              └───────────────────────────┘
```

---

## 4. Directory Layout (target state after all phases)

```
AI-Evaluation-Dashboard/
├── api/
│   ├── __init__.py
│   ├── dashboard_server.py        # extended: registers new routers
│   ├── evaluation_routes.py       # legacy endpoints (unchanged)
│   └── compare_routes.py          # NEW: /compare, /suites, /runs, /stream
├── database/
│   ├── __init__.py
│   ├── evaluation_store.py        # legacy (unchanged)
│   └── arena_store.py             # NEW: runs, model_results, metric_scores
├── evaluation_pipeline/
│   ├── __init__.py
│   ├── groq_judge.py              # UPGRADED: JSON mode + async
│   ├── metric_definitions.py      # extended with new Pydantic models
│   └── score_calculator.py        # extended: async orchestration
├── providers/
│   ├── __init__.py
│   ├── base.py                    # Protocol: ModelResponse dataclass
│   ├── anthropic_adapter.py
│   ├── openai_adapter.py
│   └── gemini_adapter.py
├── metrics/
│   ├── __init__.py
│   ├── cost.py                    # token × price table
│   ├── latency.py                 # p50 aggregation
│   └── code_runner.py             # sandboxed subprocess execution
├── suites/
│   ├── coding.json                # 5 items + unit tests
│   ├── reasoning.json             # 5 items + expected answers
│   ├── rag_faithfulness.json      # 5 context+question pairs
│   └── safety.json                # 5 adversarial prompts
├── frontend/                      # REPLACED with React build output
│   └── (Vite build output)
├── frontend-src/                  # React source
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   │   ├── Compare.tsx
│   │   │   ├── Results.tsx
│   │   │   └── History.tsx
│   │   ├── hooks/
│   │   ├── types/
│   │   └── main.tsx
│   ├── package.json
│   ├── vite.config.ts
│   └── tailwind.config.ts
├── tests/
│   ├── __init__.py
│   ├── test_evaluation_pipeline.py  # real tests (was empty)
│   ├── test_providers.py
│   ├── test_metrics.py
│   └── test_compare_routes.py
├── demo/
│   └── demo_results.json          # pre-recorded results for demo mode
├── docs/
│   ├── CONTEXT.md                 # this file
│   ├── PLAN.md
│   ├── PROGRESS.md
│   ├── ERROR_LOG.md
│   └── SESSION_LOG.md
├── .env
├── .env.example
├── .gitignore
├── Dockerfile                     # Phase 4
├── requirements.txt               # extended
└── README.md
```

---

## 5. Tech Stack

| Layer | Technology | Rationale |
|---|---|---|
| Backend language | Python 3.11+ | Existing stack; async support |
| API framework | FastAPI | Existing; native async + SSE support |
| Data validation | Pydantic v2 | Existing; strict typing |
| Database | SQLite (aiosqlite) | Existing; zero infra, sufficient for arena |
| Judge provider | Groq (llama-3.3-70b) | Existing; fast + cheap inference |
| LLM providers | Anthropic, OpenAI, Gemini | Requested by spec |
| Frontend framework | React 18 + Vite | Spec requirement; fast HMR |
| CSS framework | Tailwind CSS v3 | Spec requirement; utility-first |
| Charts | Recharts | Spec requirement; React-native |
| Type checker | mypy | Spec requirement |
| Linter/formatter | ruff | Spec requirement |
| Test runner | pytest + pytest-asyncio | Spec requirement |
| HTTP client | httpx | Already in requirements |
| Code sandbox | subprocess + resource limits | spec: sandboxed subprocess |
| Deployment | Docker (API) + Vercel (FE) | Phase 4 |

---

## 6. Metric Definitions

### LLM-Judged (Groq judge, JSON mode)

| Metric | Definition | Range | Threshold |
|---|---|---|---|
| `groundedness` | Every claim in the response is supported by the provided context | 0–1 | 0.7 |
| `correctness` | Response matches the expected/ground-truth answer | 0–1 | 0.7 |
| `completeness` | Response covers all important aspects of the question | 0–1 | 0.6 |
| `safety` | Response contains no harmful, biased, or inappropriate content | 0–1 | 0.8 |

> `relevance` from the old schema is renamed `correctness` for the arena. The legacy `/evaluate` endpoint continues to use the old 4-metric set.

### Deterministic

| Metric | Definition | Unit |
|---|---|---|
| `cost_usd` | (input_tokens × input_price + output_tokens × output_price) / 1_000_000 | USD |
| `latency_ms` | Wall-clock time from request send to first complete response | ms |
| `latency_p50` | Median latency across all items in a suite run | ms |
| `code_pass_rate` | Fraction of generated code snippets that pass their unit tests | 0–1 |
| `consistency` | 1 − (std_dev of judge scores across 3 runs) — higher = more consistent | 0–1 |

---

## 7. API Contracts

### POST /compare

**Request body** (`CompareRequest`):
```json
{
  "model_a": "claude-3-5-haiku-20241022",
  "model_b": "gpt-4o-mini",
  "provider_a": "anthropic",
  "provider_b": "openai",
  "prompt": "Explain recursion with a Python example",
  "suite_id": null,
  "consistency_runs": 1
}
```
- `prompt` XOR `suite_id` must be non-null (validated in Pydantic)
- `consistency_runs`: 1, 2, or 3

**Request headers** (never logged/persisted):
```
X-Anthropic-Key: sk-ant-...
X-OpenAI-Key: sk-...
X-Gemini-Key: AI...
```

**Response** (`CompareResponse`):
```json
{
  "run_id": "uuid",
  "model_a": {
    "provider": "anthropic",
    "model": "claude-3-5-haiku-20241022",
    "response_text": "...",
    "input_tokens": 42,
    "output_tokens": 180,
    "latency_ms": 1234.5,
    "cost_usd": 0.000864,
    "judge_scores": {
      "groundedness": {"score": 0.92, "reasoning": "..."},
      "correctness":  {"score": 0.88, "reasoning": "..."},
      "completeness": {"score": 0.75, "reasoning": "..."},
      "safety":       {"score": 1.0,  "reasoning": "..."}
    },
    "code_pass_rate": null,
    "consistency": null,
    "error": null
  },
  "model_b": { "...same shape..." },
  "winner": "model_a",
  "created_at": "2026-07-29T00:00:00Z"
}
```
- A provider failure sets `error` on that model's cell; the run still completes.
- `winner` = whichever model has higher average judge score; `"tie"` if equal.

### GET /suites

Returns list of available suite IDs with metadata:
```json
[
  {"id": "coding", "name": "Coding Ability", "item_count": 5},
  {"id": "reasoning", "name": "Reasoning", "item_count": 5},
  {"id": "rag_faithfulness", "name": "RAG Faithfulness", "item_count": 5},
  {"id": "safety", "name": "Safety", "item_count": 5}
]
```

### GET /runs

Returns paginated list of past comparison runs (newest first):
```json
{
  "total": 42,
  "runs": [
    {"run_id": "...", "model_a": "...", "model_b": "...", "winner": "...", "created_at": "..."}
  ]
}
```

### GET /runs/{run_id}

Full `CompareResponse` payload for a historical run.

### GET /stream/{run_id}  (SSE)

Server-Sent Events for live progress:
```
data: {"event": "started", "run_id": "..."}
data: {"event": "model_a_done", "run_id": "...", "latency_ms": 1234}
data: {"event": "model_b_done", "run_id": "...", "latency_ms": 890}
data: {"event": "judge_done",   "run_id": "..."}
data: {"event": "complete",     "run_id": "..."}
```

---

## 8. Database Schema

```sql
-- Extended schema (arena_store.py)
-- Legacy `evaluations` table in evaluation_store.py is left untouched.

CREATE TABLE IF NOT EXISTS runs (
    id            TEXT PRIMARY KEY,
    suite_id      TEXT,                      -- null for custom prompt
    prompt        TEXT,                      -- null for suite runs
    model_a       TEXT NOT NULL,
    model_b       TEXT NOT NULL,
    provider_a    TEXT NOT NULL,
    provider_b    TEXT NOT NULL,
    winner        TEXT,                      -- 'model_a' | 'model_b' | 'tie'
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS model_results (
    id              TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs(id),
    slot            TEXT NOT NULL,           -- 'model_a' | 'model_b'
    model_name      TEXT NOT NULL,
    provider        TEXT NOT NULL,
    response_text   TEXT,
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    latency_ms      REAL,
    cost_usd        REAL,
    code_pass_rate  REAL,
    consistency     REAL,
    error           TEXT,                    -- null if success
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS metric_scores (
    id               TEXT PRIMARY KEY,
    model_result_id  TEXT NOT NULL REFERENCES model_results(id),
    metric_name      TEXT NOT NULL,
    score            REAL NOT NULL,
    reasoning        TEXT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 9. Provider Adapter Contract

```python
# providers/base.py
from dataclasses import dataclass
from typing import Protocol

@dataclass
class ModelResponse:
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    error: str | None = None

class ModelProvider(Protocol):
    async def complete(
        self,
        prompt: str,
        api_key: str,
        model: str,
        timeout_s: float = 30.0,
    ) -> ModelResponse: ...
```

Each adapter must:
- Wrap the provider SDK call in `asyncio.wait_for` with the timeout
- Catch all provider-SDK exceptions and return `ModelResponse(error=str(e), ...zeros)`
- Never log or persist the `api_key` argument
- Return exact token counts from the provider response (not estimates)

---

## 10. Security Rules

1. **User API keys never touch the server's persistence layer.** They travel in request headers (`X-Anthropic-Key`, `X-OpenAI-Key`, `X-Gemini-Key`), are passed to adapter `.complete()`, and immediately discarded.
2. **Keys never appear in logs.** Error handlers in adapters must redact key-like strings (regex `sk-[A-Za-z0-9-]{20,}` → `[REDACTED]`) before raising or returning.
3. **Groq key stays server-side** in `.env` / environment variable `GROQ_API_KEY`. It is never sent to the client.
4. **React state only for BYOK keys.** No `localStorage`, no `sessionStorage`, no cookies.
5. **No secrets in commits.** The pre-commit check (`ruff + mypy`) must pass before any commit. `.env` is in `.gitignore`.
6. **Code runner sandbox**: generated code runs in a subprocess with `resource.setrlimit` (Linux) or a 5-second timeout + `terminate()` (Windows); no network access granted; temp directory only.
7. **CORS**: In production, restrict `allow_origins` to the deployed frontend URL. Development allows localhost only.

---

## 11. Decisions Log

| Date | Decision | Rationale |
|---|---|---|
| 2026-07-29 | Keep legacy `/evaluate` endpoint unchanged | Backward compatibility; existing data in `evaluations` table |
| 2026-07-29 | Use `aiosqlite` for new arena store | Avoid blocking the async event loop on DB writes |
| 2026-07-29 | Rename `relevance` → `correctness` in new judge | Better reflects arena use-case (correctness vs ground truth) |
| 2026-07-29 | Frontend source in `frontend-src/`, build output in `frontend/` | FastAPI already mounts `frontend/` as static; Vite builds there |
| 2026-07-29 | Demo mode via `demo/demo_results.json` | Allows visitors without API keys to see a fully populated dashboard |
| 2026-07-29 | Consistency = 1 − std_dev(scores across N runs) | Self-reported confidence is unreliable; variance is objective |
| 2026-07-29 | Windows-compatible sandbox: timeout + terminate | `resource.setrlimit` is Linux-only; cross-platform safety via timeout |
| 2026-07-29 | `groq` package (already installed) for judge | Already in .venv; no new dependency |
| 2026-07-29 | `anthropic`, `openai`, `google-generativeai` packages for adapters | Official provider SDKs; type-safe |

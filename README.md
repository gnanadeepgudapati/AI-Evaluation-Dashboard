# AI-Evaluation-Dashboard

An LLM-as-judge evaluation pipeline and analytics dashboard that scores AI agent
responses on four metrics: **groundedness**, **relevance**, **safety**, and
**completeness**. Built with Python, FastAPI, SQLite, and Groq API.

---

## Project Layout

```
evaluation_pipeline/
  metric_definitions.py  — Pydantic models + scoring criteria for all four metrics
  score_calculator.py    — placeholder scorer functions (Phase 1) / LLM scorers (Phase 2)
  groq_judge.py          — Groq API client stub (Phase 2)

api/
  dashboard_server.py    — FastAPI application entry point
  evaluation_routes.py   — /api/evaluate, /api/history, /api/metrics endpoints

database/
  evaluation_store.py    — SQLite read/write for evaluation history

frontend/
  index.html             — dashboard UI
  dashboard_charts.js    — Chart.js visualisations

tests/
  test_evaluation_pipeline.py
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env to add your GROQ_API_KEY (required for Phase 2)
```

### 3. Run the server

```bash
uvicorn api.dashboard_server:app --reload --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000** in your browser to see the dashboard.

### 4. Interactive API docs

- Swagger UI: http://localhost:8000/docs
- ReDoc:       http://localhost:8000/redoc

---

## API Reference

| Method | Path                      | Description                          |
|--------|---------------------------|--------------------------------------|
| POST   | `/api/evaluate`           | Score a question/response pair       |
| GET    | `/api/history`            | Paginated evaluation history         |
| GET    | `/api/history/{id}`       | Single evaluation by id              |
| GET    | `/api/metrics/averages`   | Aggregate average scores             |
| GET    | `/health`                 | Health check                         |

**POST `/api/evaluate` payload:**

```json
{
  "question": "What is machine learning?",
  "response": "Machine learning is a subset of AI…",
  "context": "(optional) reference text for groundedness scoring"
}
```

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Metric Weights (Overall Score)

| Metric        | Weight |
|---------------|--------|
| Groundedness  | 30 %   |
| Relevance     | 30 %   |
| Safety        | 20 %   |
| Completeness  | 20 %   |

---

## Roadmap

- **Phase 1** ✅ FastAPI server, Pydantic metric models, placeholder scorers, SQLite history, dashboard UI
- **Phase 2** — Integrate Groq API for LLM-as-judge scoring (`groq_judge.py`)
- **Phase 3** — Authentication, export to CSV/JSON, advanced chart filters

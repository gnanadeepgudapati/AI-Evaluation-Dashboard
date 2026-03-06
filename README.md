# AI Evaluation Dashboard

A pipeline that uses an LLM as a judge to score AI agent responses across four metrics — and a dashboard that makes those scores actually useful. Built because evaluating LLM output by hand doesn't scale.

---

## What This Does

You give it three things — a question, the context the AI had access to, and the AI's response. It runs that through four scorers and tells you whether the response was any good, and why.

The four metrics:
- **Groundedness** — is the answer actually supported by the context, or is the model hallucinating?
- **Relevance** — does it address what was actually asked?
- **Safety** — anything harmful, biased, or inappropriate in the output?
- **Completeness** — did it cover the full scope of the question or leave gaps?

Each metric gets a score from 0 to 1 with a short explanation from the judge. Everything gets stored in SQLite and visualized on the dashboard.

---

## Project Structure

evaluation_pipeline/ — core scoring logic:
- `groq_judge.py` — handles all Groq API calls, this is the actual LLM judge
- `score_calculator.py` — runs all four scorers and aggregates the result
- `metric_definitions.py` — Pydantic models and scoring thresholds for all four metrics

api/ — backend:
- `dashboard_server.py` — FastAPI entry point, start the server from here
- `evaluation_routes.py` — all three endpoints live here

database/ — persistence:
- `evaluation_store.py` — SQLite read/write, stores every evaluation run

frontend/ — dashboard UI:
- `index.html` — the dashboard, two pages — Evaluate and History
- `dashboard_charts.js` — API calls, Chart.js visualizations, DOM rendering

tests/:
- `test_evaluation_pipeline.py` — test suite for the scoring logic

---

## How It Works

```
User Input → FastAPI → Groq Judge (×4 calls) → SQLite → Dashboard
```

One evaluation = four separate calls to Groq's Llama model, one per metric. Each call uses a carefully engineered prompt that forces the judge to respond with a score and reasoning in a consistent format. Results get stored in SQLite and show up in the history table immediately.

---

## Build Phases

**Phase 1 — Foundation** ✅
FastAPI server, Pydantic data models, placeholder scorers, three working endpoints.

**Phase 2 — LLM Judge** ✅
Groq API integration, prompt engineering for each metric, real scores with reasoning returned.

**Phase 3 — Dashboard** ✅
HTML/CSS/JS frontend, score cards, Chart.js bar chart, SQLite persistence, evaluation history table.

---

## Tech Stack

- **Backend** — Python + FastAPI
- **Data validation** — Pydantic
- **LLM Judge** — Groq API running Llama 3.3 70B
- **Database** — SQLite
- **Frontend** — plain HTML/CSS/JS
- **Charts** — Chart.js via CDN

---

## Getting Started

**1. Clone the repo**
```bash
git clone https://github.com/gnanadeepgudapati/AI-Evaluation-Dashboard.git
cd AI-Evaluation-Dashboard
```

**2. Create a virtual environment**
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Set up environment variables**
```bash
cp .env.example .env
```
Open `.env` and add your Groq API key:
```env
GROQ_API_KEY=your_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```
Get a free key at [groq.com](https://groq.com)

**5. Run the server**
```bash
uvicorn api.dashboard_server:app --reload
```

**6. Open the dashboard**
```
http://127.0.0.1:8000/dashboard
```

---

## API Endpoints

- `POST /evaluate` — submit an AI response for evaluation
- `GET /evaluations` — get all past evaluations, newest first
- `GET /evaluations/{id}` — get one specific evaluation by ID

Auto-generated API docs available at `http://127.0.0.1:8000/docs`

---

## Example Evaluation

**Input:**
```json
{
  "question": "What are the health benefits of drinking water?",
  "context": "Water helps regulate body temperature, transport nutrients, and flush out toxins. Doctors recommend at least 8 glasses per day. Dehydration causes fatigue, headaches, and poor concentration.",
  "ai_response": "Drinking water helps regulate body temperature, transports nutrients, and flushes out toxins. Staying hydrated prevents fatigue and headaches."
}
```

**Output:**
```json
{
  "overall_score": 0.93,
  "groundedness": { "score": 1.0, "passed": true },
  "relevance":    { "score": 1.0, "passed": true },
  "safety":       { "score": 1.0, "passed": true },
  "completeness": { "score": 0.7, "passed": true }
}
```

The judge caught that the response missed the recommended daily intake — completeness took the hit. That's the pipeline working exactly as intended.

---

## Why This Matters

As LLM-powered applications get more complex, manually reviewing outputs stops being viable. This project makes evaluation systematic, repeatable, and transparent — the same approach used in production by teams building serious AI products. This is a from-scratch implementation of those concepts.

---

## Current Status

- [x] Phase 1 — FastAPI server + Pydantic models
- [x] Phase 2 — Groq judge integration
- [x] Phase 3 — Dashboard frontend + SQLite persistence
- [ ] Parallel API calls for faster evaluation
- [ ] Test suite
- [ ] Docker containerization

# AI Evaluation Dashboard

Built this because evaluating LLM responses by hand doesn't scale. This is a pipeline that uses an LLM as a judge to score AI agent responses across four metrics — and a dashboard that makes those scores actually useful.

---

## What This Does

You give it three things — a question, the context the AI had access to, and the AI's response. It runs that through four scorers and tells you whether the response was any good, and why.

The four metrics:
- **Groundedness** — is the answer actually supported by the context, or is the model hallucinating?
- **Relevance** — does it address what was actually asked?
- **Safety** — anything harmful, biased, or inappropriate in the output?
- **Completeness** — did it cover the full scope of the question or leave gaps?

Each metric gets a score from 0 to 1 with a short explanation from the judge. Everything gets stored and visualized on the dashboard.

---

## Project Structure

Here's how I've structured this project —

evaluation_pipeline/ is where all the core logic lives:
- `groq_judge.py` — handles all the Groq API calls, this is the actual LLM judge
- `score_calculator.py` — processes and aggregates the scores
- `metric_definitions.py` — holds the criteria and prompts for all four metrics

api/ is straightforward:
- `dashboard_server.py` — boots up the FastAPI server, start here
- `evaluation_routes.py` — all the endpoints live here

database/ has one job:
- `evaluation_store.py` — saves and pulls evaluation history using SQLite

Frontend is kept simple for now:
- `index.html` — the dashboard UI
- `dashboard_charts.js` — Chart.js visualizations for scores and trends

tests/:
- `test_evaluation_pipeline.py` — tests for the scoring logic

Also in the root:
- `.env.example` — copy this to `.env` and add your API key
- `requirements.txt` — all Python dependencies

---

## Build Plan

Building this in three phases — each one ships something that actually runs.

**Phase 1 — The Foundation**
Get FastAPI running, define the four metric models with Pydantic, write placeholder scorer functions in score_calculator.py. No LLM calls yet, just the skeleton with the right structure.
- Deliverable: a running API that accepts input and returns dummy scores

**Phase 2 — The LLM Judge**
Plug in Groq API, write prompts for each metric, store results in SQLite. The API now returns real scores with reasoning.
- Deliverable: a working evaluation pipeline you can test with real AI responses

**Phase 3 — The Dashboard**
Build the frontend, visualize scores with Chart.js, show history and per-metric breakdowns.
- Deliverable: a full working product, ready to demo

---

## Tech Stack

- **Backend** — Python + FastAPI, fast to build and async-ready
- **Data validation** — Pydantic, catches bad input before it breaks anything
- **LLM Judge** — Groq API running Llama 3, free tier with no credit card required
- **Database** — SQLite, zero setup and built into Python
- **Frontend** — plain HTML/CSS/JS, no framework overhead
- **Charts** — Chart.js via CDN, simple and well-documented

---

## Getting Started

**1. Clone the repo**
```bash
git clone https://github.com/gnanadeepgudapati/AI_Evaluation_Dashboard.git
cd AI_Evaluation_Dashboard
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Set up environment variables**
```bash
cp .env.example .env
```
Open `.env` and add your Groq API key:
```env
GROQ_API_KEY=your_key_here
GROQ_MODEL=llama3-8b-8192
```
Get a free key at [groq.com](https://groq.com)

**4. Run the server**
```bash
uvicorn api.dashboard_server:app --reload
```
API runs at `http://localhost:8000` — hit `http://localhost:8000/docs` for the auto-generated docs.

---

## API Endpoints

- `POST /evaluate` — submit an AI response for evaluation
- `GET /evaluations` — get all past evaluation results
- `GET /evaluations/{id}` — get a specific evaluation by ID

---

## Current Status

- [x] Repo initialized
- [x] Project structure defined
- [ ] Phase 1 — FastAPI server + Pydantic models
- [ ] Phase 2 — Groq judge integration
- [ ] Phase 3 — Dashboard frontend

---

## Why I Built This

As LLM-powered applications get more complex, manually reviewing outputs stops being viable. This project makes evaluation systematic, repeatable, and transparent — the same approach used in production by teams building serious AI products. This is a from-scratch implementation of those concepts.

# LLM Evaluation Pipeline

> An LLM-as-Judge evaluation pipeline for scoring AI agent responses with a full analytics dashboard.

---

## Overview

The LLM Evaluation Pipeline is an analytics platform that scores AI agent responses across multiple quality dimensions — **groundedness**, **relevance**, **safety**, and **completeness** — and surfaces the results through a FastAPI-powered dashboard. Built for monitoring agent quality across production workflows.

---

## Features

- **LLM-as-Judge evaluation pipeline** that scores AI agent responses on groundedness, relevance, safety, and completeness
- **Analytics dashboard** powered by FastAPI for tracking model and agent quality over time
- **Multi-dimensional scoring** for monitoring response quality across production workflows

---

## Tech Stack

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
```

---

## Contact

**Gnanadeep Gudapati** — [gnanadeepgudapati@gmail.com](mailto:gnanadeepgudapati@gmail.com) · [LinkedIn](https://linkedin.com/in/gnanadeepgudapati)

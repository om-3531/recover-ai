# RecoverAI

## Overview

RecoverAI is an AI-powered autonomous revenue recovery agent, built for the
Razorpay AI Buildathon 2026 — Track 03: AI Revenue Recovery.

## Problem

Failed payments create recoverable revenue loss for merchants. Today,
diagnosing why a payment failed, deciding how to intervene, and following
up is mostly manual, slow, and inconsistent.

## Planned Solution

**Detect → Diagnose → Decide → Recover → Measure → Audit.**

1. Detect revenue at risk from failed/at-risk payments.
2. Diagnose why a payment failed.
3. Estimate the probability of recovery.
4. Recommend an intervention (AI-generated).
5. Apply deterministic safety/policy rules before any action is authorized.
6. Execute a bounded recovery workflow.
7. Record every decision and action in an audit trail.
8. Measure actual revenue recovered.

See [`docs/architecture.md`](docs/architecture.md) for the full flow and
architecture rules — in particular, **the AI never directly authorizes a
financial action**; every recommendation passes through a deterministic
policy engine first.

## Current Status

**Day 4 — Razorpay Payment Integration & Webhook Ingestion.**
- Isolated Razorpay client and application service (`RazorpayClient`, `RazorpayService`).
- HMAC SHA-256 constant-time signature verification for checkouts and webhooks.
- Idempotent webhook receiver endpoint (`POST /api/v1/webhooks/razorpay`) with automatic deduplication.
- Payment & Revenue state synchronization on `payment.captured` and `payment.failed`.
- Order creation endpoint (`POST /api/v1/payments/orders`) and checkout signature verification endpoint (`POST /api/v1/payments/verify-signature`).
- Immutable audit logging for all integration events.
- 42/42 backend tests passing (100% mocked offline testing; zero live secrets required).

## Tech Stack

**Frontend:** React + Vite + Tailwind CSS
**Backend:** FastAPI + Python (SQLAlchemy 2.x, Alembic, Pydantic, HTTPX)
**Database:** PostgreSQL
**AI:** Gemini API *(future milestone)*
**Payments:** Razorpay Test Mode & Webhooks (Integrated)




## Project Structure

```
recover-ai/
├── frontend/        React + Vite + Tailwind dashboard
├── backend/          FastAPI application
│   └── app/
│       ├── api/       Route handlers
│       ├── core/       Config
│       ├── db/         Engine, session, Base
│       ├── models/     SQLAlchemy models
│       ├── schemas/     Pydantic schemas
│       ├── services/    Business logic (future)
│       ├── agents/       AI logic (future)
│       ├── policies/      Policy/authorization engine (future)
│       ├── integrations/razorpay/  Razorpay API layer (future)
│       └── webhooks/       Inbound webhook handlers (future)
├── data/            Local dev data (gitignored)
├── docs/            Architecture docs
├── n8n/              Workflow definitions (future)
└── docker-compose.yml
```

## Local Development

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 16 (or Docker)

### 1. Clone the project

```bash
git clone <repo-url>
cd recover-ai
```

### 2. Configure environment

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env.local
```

Edit `.env` if your local Postgres credentials differ from the defaults.
Never commit `.env`.

### 3. Start PostgreSQL

Using Docker (recommended):

```bash
docker compose up -d postgres
```

Or point `DATABASE_URL` in `.env` at an existing local Postgres instance.

### 4. Apply Database Migrations
```bash
cd backend
source .venv/bin/activate        # Windows: .venv\Scripts\activate
alembic upgrade head
```

### 5. Start the backend

```bash
cd backend
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend runs at `http://localhost:8000`. Check `GET /health`.

### 6. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`.

### 7. Run tests

```bash
cd backend
pytest
```


### Alternative: backend + database via Docker

```bash
docker compose up -d
```

This starts PostgreSQL and the backend container. Run the frontend
locally with `npm run dev` as above (see `docker-compose.yml` for why the
frontend isn't containerized yet).

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the full system
diagram and the architecture rules (AI/policy/execution separation,
integration isolation, etc.).

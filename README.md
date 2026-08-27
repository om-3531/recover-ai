# RecoverAI

**AI-Powered Payment Recovery Automation Platform**
Razorpay Buildathon 2026 — Track 03: AI Revenue Recovery

---

## Overview

RecoverAI detects at-risk and failed payments, diagnoses the cause using AI,
recommends a recovery intervention, applies deterministic policy checks,
and executes a bounded recovery workflow — with a human approval gate for
high-risk actions. Every decision is recorded in an audit trail.

**Architecture principle: AI never directly controls money.**

```
AI recommendation → PolicyEngine → ApprovalService → ExecutionService
```

## Features

- **AI Payment Diagnosis**: MockAIProvider (default) or Gemini (opt-in)
- **Razorpay Webhook Integration**: HMAC-SHA256 signature verification, idempotency dedup
- **Risk Assessment**: Automatic low-risk vs high-risk classification
- **Low-Risk Auto-Recovery**: Automatic execution for low-risk payment failures
- **High-Risk Approval Gate**: Human-in-the-loop approval required for high-risk cases
- **Interactive Approval Dashboard**: Approve/reject pending approvals from the UI
- **Real-Time Live Monitor**: Webhook event feed with case timeline
- **Pipeline Visualization**: 8-stage pipeline showing recovery progress
- **Analytics Dashboard**: KPIs, revenue recovery rates, case distribution
- **Demo Mode**: Full simulation without real Razorpay credentials
- **Comprehensive Audit Trail**: Every state mutation logged

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite, Tailwind CSS |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.x, Pydantic |
| Database | SQLite (local dev), PostgreSQL (Docker/production) |
| AI | MockAIProvider (default), Gemini (opt-in via `AI_PROVIDER=gemini`) |
| Payments | Razorpay Test Mode + Webhooks |
| Deployment | Docker, docker-compose |

## Quick Start (2 terminals)

### Terminal 1 — Backend

```bash
cd D:\Downloads\recover-ai\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Terminal 2 — Frontend

```bash
cd D:\Downloads\recover-ai\frontend
npm run dev
```

### Open Dashboard

Navigate to **http://localhost:5173**

> **Getting ERR_CONNECTION_REFUSED?** This means the frontend dev server
> is not running. Make sure Terminal 2 is active with `npm run dev`.

## URLs

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:5173 |
| Backend API | http://127.0.0.1:8000 |
| Swagger Docs | http://127.0.0.1:8000/docs |
| Health Check | http://127.0.0.1:8000/health |
| Readiness Probe | http://127.0.0.1:8000/ready |

## Demo Instructions

1. Start both backend and frontend (see Quick Start above)
2. Open http://localhost:5173
3. Click **Seed Demo Data** to populate sample data (20 cases)
4. Click **Low-Risk Failure** to simulate automatic recovery
5. Click **High-Risk Failure** to trigger the approval workflow
6. In the **Approval Center**, click **Approve** to authorize recovery
7. Watch the pipeline complete and timeline update

## Environment Variables

Copy `.env.example` to `.env` in the project root:

```bash
cp .env.example .env
```

Key variables (all have safe defaults for local demo):

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_PROVIDER` | `mock` | Set to `gemini` for live AI |
| `DEMO_MODE` | `true` | Enable demo endpoints |
| `RAZORPAY_KEY_ID` | `""` | Empty = no real Razorpay calls |
| `RAZORPAY_KEY_SECRET` | `""` | Empty = no real Razorpay calls |
| `RAZORPAY_WEBHOOK_SECRET` | `""` | Empty = simulation uses mock secret |
| `DATABASE_URL` | PostgreSQL default | SQLite used for local dev |

**Never commit `.env` with real credentials.**

## Running Tests

```bash
cd backend
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

Current: **390/390 tests passing**

## Building for Production

```bash
cd frontend
npm run build
```

Output: `frontend/dist/` (47 modules, ~73KB gzipped)

## Docker Deployment

```bash
# Start PostgreSQL + Backend
docker compose up -d

# Frontend runs locally
cd frontend && npm install && npm run dev
```

The backend Dockerfile creates tables automatically on first startup
(no manual Alembic migration needed for fresh databases).

## Project Structure

```
recover-ai/
├── frontend/                  React + Vite + Tailwind dashboard
│   └── src/
│       ├── components/        ApprovalCenter, Sidebar, TopNav, StatCard
│       ├── pages/             DashboardPage, PolicySettingsPage, WebhookConsolePage
│       ├── services/api.js    API client functions
│       └── hooks/             useSystemStatus
├── backend/                   FastAPI application
│   └── app/
│       ├── api/routes/        REST endpoints (health, payments, webhooks, etc.)
│       ├── ai/                AI provider abstraction + MockAIProvider + Gemini
│       ├── approval/          ApprovalService, ApprovalPolicy, schemas
│       ├── execution/         RecoveryExecutionService, RecoveryExecutor
│       ├── orchestration/     RecoveryOrchestrator (end-to-end coordination)
│       ├── integrations/      Razorpay client, signature verification
│       ├── models/            SQLAlchemy models + enums
│       ├── services/          WebhookService, AuditService, AnalyticsService
│       ├── demo/              Synthetic data generator + scenarios
│       ├── policy/            MerchantPolicy rules engine
│       ├── jobs/              Background execution jobs
│       └── providers/         Multi-channel providers (Mock + real foundations)
├── docs/                      Architecture, demo scripts, checklists
├── docker-compose.yml         PostgreSQL + Backend
└── .env.example               Environment variable template
```

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the full system
diagram and architecture rules.

Key principle: **AI never directly controls money.** The flow is always:

```
AI recommendation → PolicyEngine → ApprovalService → ExecutionService
```

Server-side policy remains authoritative. The frontend never authorizes
financial actions directly.

## Security

- HMAC-SHA256 with constant-time comparison for webhook signatures
- Idempotent duplicate webhook handling
- No secrets in frontend code or API responses
- CORS restricted to localhost
- Demo mode safety gates on all simulation endpoints
- All monetary values stored as integer paise (never float)

## Troubleshooting

**ERR_CONNECTION_REFUSED on localhost:5173**
→ The frontend dev server is not running. Start it with `npm run dev`.

**Backend returns 500 on first request**
→ Database tables may not exist. The app auto-creates tables on startup.
If issues persist, restart the backend server.

**No data in dashboard**
→ Click "Seed Demo Data" to populate sample recovery cases.

**Approval Center is empty**
→ Simulate a high-risk payment failure first. High-risk cases require
human approval; low-risk cases auto-complete.

## License

Built for Razorpay Buildathon 2026.

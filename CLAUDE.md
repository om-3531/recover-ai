# CLAUDE.md

This file gives any future Claude Code session the context needed to work on
RecoverAI safely and consistently. **Read this before making changes.**

## Project Purpose

RecoverAI is an AI-powered autonomous revenue recovery agent for the
Razorpay AI Buildathon 2026 — Track 03: AI Revenue Recovery. It will
detect at-risk/failed payments, diagnose the cause, recommend a recovery
intervention, apply deterministic policy checks, execute a bounded
recovery workflow, and record everything in an audit trail.

Final deadline: **31 August 2026**. Prioritize working software, clean
architecture, reliability, testability, and measurable results over
scope or polish.

## Current Status

Day 2 — Database Foundation complete. See the end of this file for the
Day 2 completion notes and the recommended next task.


## Architecture Principles (do not violate these)

1. **AI never directly controls money.** The flow is always:
   `AI recommendation → Policy Engine → Authorization → Action Executor`.
   Code in `app/agents` must never call payment execution or Razorpay
   directly. It only produces a recommendation object.
2. **Razorpay integration is isolated** in `app/integrations/razorpay`.
   Do not call the Razorpay API from route files, services, or agents
   directly — go through this layer.
3. **AI logic is isolated** in `app/agents`, separate from API routes,
   database models, business rules, and payment execution.
4. **Database access is separated.** Use SQLAlchemy models
   (`app/models`) and the session layer (`app/db`). Do not write raw
   database logic inline in routes or services.
5. **Configuration is environment-driven.** All secrets and config
   (API keys, DB passwords, webhook secrets) come from environment
   variables via `app/core/config.py`. Never hard-code secrets anywhere,
   including in tests, scripts, or committed `.env` files.

## Technology Stack

- **Frontend:** React, Vite, Tailwind CSS, JavaScript (Recharts to be
  added later for analytics)
- **Backend:** Python, FastAPI, SQLAlchemy, Pydantic
- **Database:** PostgreSQL
- **AI:** Gemini API (not yet integrated)
- **Payments:** Razorpay Test Mode + Webhooks (not yet integrated)
- **Workflow:** n8n (optional, not yet integrated — do not add until
  explicitly requested)

## Coding Rules

- Type hints on all Python function signatures.
- Pydantic schemas for all API request/response bodies.
- Small, focused modules — no giant files.
- Clear, descriptive naming; no abbreviations that aren't obvious.
- No duplicated configuration — `app/core/config.py` is the single
  source of truth for settings.
- No unnecessary dependencies — check `requirements.txt` /
  `package.json` before adding a new one.
- Comments should explain *why*, not restate *what* the code does.
- Clear, explicit error handling — no silent `except: pass`.

## Security Rules

- Never expose secrets in frontend code or commit `.env`.
- Never hard-code API credentials anywhere, including "temporary" test
  values.
- Validate environment variables (fail loudly if a required one is
  missing, rather than silently defaulting to something incorrect).
- Never return database credentials or other secrets in API responses.
- Keep payment execution logic isolated so it can be reviewed/audited
  independently of the rest of the codebase.

## Testing Rules

- Every new backend endpoint needs at least a happy-path test.
- Database-touching code should be tested against configuration
  correctness even when a live Postgres instance isn't available in
  the environment (see `backend/tests/test_database.py` for the
  pattern used on Day 1).
- Frontend changes must keep `npm run build` passing.
- Run `pytest` from `backend/` and `npm run build` from `frontend/`
  before considering a task done.

## Development Workflow

1. Read this file before making changes.
2. Check `docs/architecture.md` for the current component map before
   adding new modules.
3. Keep changes scoped to the milestone being worked on — do not
   implement future milestones early (see "Roadmap" below).
4. Add/update tests alongside any new backend functionality.
5. Update this file and `docs/architecture.md` when the architecture
   changes (new services, new integration boundaries, etc.).
6. Never commit secrets. Double-check `git status` / `git diff` before
   committing if `.env` or credentials could plausibly be included.

## Roadmap (do not implement ahead of schedule)

- Day 1 (done): project foundation — backend/frontend/db wiring, health
  check, dashboard shell, Docker config, tests, git init.
- Day 2 (done): database foundation — SQLAlchemy 2.x data models
  (`Payment`, `PaymentEvent`, `RevenueRecord`, `RecoveryCase`, `RecoveryAction`,
  `AuditLog`), enums, mixins, Alembic migrations, test suite.

**Next recommended task:** Day 3 milestone (e.g. Inbound Webhook Ingestion & Idempotency / Event Pipeline).

Explicitly NOT yet implemented (build only when reached in the
roadmap):

- Gemini AI agent and prompts
- Payment recovery / retry execution logic
- Razorpay API live calls and webhook verification
- Policy engine rules
- Revenue analytics dashboard integration
- Synthetic dataset generation
- n8n workflows
- Authentication
- Production deployment

## Day 1 Foundation — What Was Built

- FastAPI backend (`backend/app`) with `GET /health` and
  `GET /api/v1/status`, config via `pydantic-settings`, SQLAlchemy
  engine/session/Base, and a minimal `SystemHealthCheck` model.
- React + Vite + Tailwind frontend (`frontend/src`) with a dashboard
  shell: sidebar, top nav, stat card placeholders, and placeholder pages.
- `docker-compose.yml` (Postgres + backend) and a backend `Dockerfile`.
- Backend tests: `test_health.py`, `test_database.py`.

## Day 2 Database Foundation — What Was Built

- Domain enums (`app/models/enums.py`): `PaymentStatus`, `PaymentMethod`,
  `PaymentEventProcessingStatus`, `RevenueStatus`, `RiskStatus`,
  `RecoveryPriority`, `RecoveryCaseState`, `RecoveryActionStatus`,
  `RecoveryActionType`, `RecoveryActionChannel`.
- Reusable `TimestampMixin` (`app/models/mixins.py`).
- SQLAlchemy 2.x ORM models (`app/models/`):
  - `Payment`: Razorpay payment details, indexed identifiers, integer paise amounts.
  - `PaymentEvent`: Webhook event payloads with unique `razorpay_event_id` for idempotency.
  - `RevenueRecord`: 1:1 linked revenue status and recoverable calculations in integer paise.
  - `RecoveryCase`: 1:N recovery cases per revenue record with risk/priority states.
  - `RecoveryAction`: 1:N bounded recovery interventions per recovery case.
  - `AuditLog`: Generic entity reference with non-colliding `event_metadata` mapping.
- Alembic database migration environment (`backend/alembic/` & `alembic.ini`) with
  `0001_initial_system_health.py` and `0002_payment_recovery_schema.py`.
- Comprehensive test suite (`backend/tests/test_models.py`) with 18/18 passing tests.


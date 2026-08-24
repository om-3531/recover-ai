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

Day 6 — Recovery Approval & Execution Workflow complete. See the end of this file for the
Day 6 completion notes and the recommended next task.






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
  `AuditLog`), enums, mixins, Alembic migrations, model tests.
- Day 3 (done): service & REST API layer — `PaymentService`, `RevenueService`,
  `RecoveryService`, `AuditService`, Pydantic validation schemas, domain exceptions,
  versioned `/api/v1` routes (`/payments`, `/revenue`, `/recovery`, `/audit`), 30/30 tests.
- Day 4 (done): Razorpay integration & webhooks — `RazorpayClient`, `RazorpayService`,
  HMAC SHA-256 constant-time verification, `WebhookService` with idempotency deduplication,
  `POST /api/v1/payments/orders`, `POST /api/v1/payments/verify-signature`,
  `POST /api/v1/webhooks/razorpay`, 42/42 tests passing.
- Day 5 (done): AI decision & policy layer — `RecoveryDecisionEngine`, `PolicyEngine`,
  `MockAIProvider`, sanitized `RecoveryContext`, advisory recommendations with mandatory
  human-review controls, `POST /api/v1/ai/recovery-cases/{case_id}/decision`, 54/54 tests.
- Day 6 (done): Recovery approval & execution workflow — `RecoveryApproval` model & migration 0003,
  `ApprovalService`, `ApprovalPolicy`, `RecoveryExecutionService`, `RecoveryExecutor` ABC,
  `MockRecoveryExecutor`, idempotent execution protection, state machine sync,
  `/api/v1/approvals` routes, 66/66 tests.

**Next recommended task:** Day 7 milestone (e.g. Analytics & Metrics Aggregation Dashboard).

Explicitly NOT yet implemented (build only when reached in the
roadmap):

- Direct customer communication dispatch across live provider networks (Twilio/SendGrid/WhatsApp)
- Live Razorpay automatic refund/retry transactions (mocked for offline test safety)
- Live Gemini API calls in test mode (isolated behind MockAIProvider)
- Revenue analytics dashboard charts & metric rollups
- Synthetic dataset generator
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
- Model test suite (`backend/tests/test_models.py`).

## Day 3 Service & REST API Layer — What Was Built

- Domain exceptions (`app/core/exceptions.py`): `NotFoundError` (404),
  `ConflictError` (409), `BadRequestError` / `InvalidStateTransitionError` (400),
  registered in `main.py`.
- Pydantic schemas (`app/schemas/`): `payments.py`, `revenue.py`, `recovery.py`, `audit.py`.
- Business services (`app/services/`):
  - `PaymentService`: payment CRUD, status updates, duplicate conflict checks, audit log generation.
  - `RevenueService`: 1:1 revenue record creation, recoverable amount computation, mark-at-risk.
  - `RecoveryService`: recovery case state machine, transition validation, recovery action management.
  - `AuditService`: immutable audit logging and filtered querying.
- REST API routes (`app/api/routes/`): `/payments`, `/revenue`, `/recovery`, `/audit`, registered in `router.py`.
- Comprehensive test suite (`test_services.py`, `test_api.py`) with 30/30 tests passing.

## Day 4 Razorpay Integration & Webhooks — What Was Built

- Isolated Razorpay client (`app/integrations/razorpay/client.py`) for order creation using HTTP Basic Auth.
- Cryptographic HMAC-SHA256 signature verification (`app/integrations/razorpay/signature.py`) with constant-time comparison.
- Razorpay application service (`app/integrations/razorpay/service.py`) with audit trail integration.
- Inbound webhook processing pipeline (`app/services/webhook_service.py`) supporting `payment.captured`, `payment.failed`, and unsupported event fallbacks.
- Webhook idempotency deduplication using `PaymentEvent.razorpay_event_id` unique constraint.
- REST API routes:
  - `POST /api/v1/payments/orders`
  - `POST /api/v1/payments/verify-signature`
  - `POST /api/v1/webhooks/razorpay`
- Comprehensive test suite (`test_razorpay.py`) with 42/42 tests passing.

## Day 5 AI Recovery Decision Engine & Policy Layer — What Was Built

- Provider abstraction (`app/ai/provider.py`): `AIProvider` base interface and deterministic `MockAIProvider` with heuristic recovery diagnosis.
- Sanitized context (`app/ai/schemas.py`): `RecoveryContext` stripped of all secrets, tokens, and PII.
- Deterministic Policy Engine (`app/ai/policy_engine.py`): Pre-policy checks (terminal states, zero balances) and post-policy safety constraints (mandatory human review for high/critical risks, retry limits).
- Recovery Decision Engine (`app/ai/decision_engine.py`): Coordinates context loading, policy evaluation, advisory recommendation generation, and audit trail dispatch.
- REST API route:
  - `POST /api/v1/ai/recovery-cases/{case_id}/decision`
- Comprehensive test suite (`test_ai_decision.py`) with 54/54 total tests passing.

## Day 6 Recovery Approval & Execution Workflow — What Was Built

- Persistent approval entity (`app/models/approval.py` & Alembic `0003_recovery_approval_schema.py`): `RecoveryApproval` tracking recommendation, action type, channel, status, approver, timestamps, expiration, and execution results.
- Approval layer (`app/approval/`): `ApprovalService`, `ApprovalPolicy`, schemas, exceptions.
- Execution layer (`app/execution/`): `RecoveryExecutionService`, `RecoveryExecutor` ABC, `MockRecoveryExecutor`, schemas, exceptions.
- Strict authorization & idempotency guards: execution requires server-side `approved` status, blocks pending/rejected/expired approvals, and returns cached results on duplicate executions.
- State machine synchronization: transitions `RecoveryCase` from `open` → `action_pending` → `recovering` on successful action dispatch.
- REST API routes (`app/api/routes/approvals.py`):
  - `POST /api/v1/approvals`
  - `GET /api/v1/approvals`
  - `GET /api/v1/approvals/{approval_id}`
  - `POST /api/v1/approvals/{approval_id}/approve`
  - `POST /api/v1/approvals/{approval_id}/reject`
  - `POST /api/v1/approvals/{approval_id}/execute`
- Comprehensive test suite (`test_approval_execution.py`) with 66/66 total tests passing.






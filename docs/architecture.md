# RecoverAI — Architecture (Day 5 Snapshot)

This document describes the architecture **as planned and built**. Day 1 established
the foundation, Day 2 implemented the core data model and Alembic migrations, Day 3
implemented the application service layer and REST API endpoints, Day 4 implemented
the Razorpay integration and idempotent webhook ingestion pipeline, and Day 5 implemented
the advisory AI Recovery Decision Engine, deterministic Policy Engine, and provider abstraction.
Items marked *(future)* are not implemented yet.

## High-level flow (target end state)

```mermaid
flowchart LR
    A[Payment Failure Event] --> B[Detect Revenue at Risk]
    B --> C[Diagnose Failure Reason]
    C --> D["AI Decision Engine (Advisory)\nRecommend Intervention"]
    D --> E[Policy Engine\nDeterministic Rules]
    E -->|Authorized| F[Action Executor (Future)]
    E -->|Rejected| G[Log & Escalate]
    F --> H[Razorpay Integration]
    F --> I[Audit Trail]
    G --> I
    H --> I
    I --> J[Analytics / Measurement]
```

## Layered Architecture (Day 5)

```mermaid
flowchart TD
    Client[Client / Checkout / Razorpay Webhooks] -->|HTTP POST / JSON / HMAC Sig| Router[FastAPI Router /api/v1]
    Router -->|Signature & Payload Validation| WebhookService[WebhookService / RazorpayService]
    WebhookService -->|Idempotency Check| PaymentEventDB[(PaymentEvent Unique razorpay_event_id)]
    WebhookService -->|State Synchronization| Domain[Payment & Revenue Models]
    Router -->|Generate Decision| AIDecisionEngine[RecoveryDecisionEngine]
    AIDecisionEngine -->|1. Pre-Policy Checks| PolicyEngine[Deterministic Policy Engine]
    AIDecisionEngine -->|2. Context (No Secrets/PII)| Provider[AIProvider / MockAIProvider]
    AIDecisionEngine -->|3. Post-Policy & Human Review| PolicyEngine
    AIDecisionEngine -->|4. Audit Events| Audit[AuditService]
    Domain -->|ORM Transactions| DB[(PostgreSQL / SQLite)]
    Audit -->|Audit Trail| DB
```

## Database Schema & Domain Flow (Day 2 to 5)

```mermaid
erDiagram
    Payment ||--o{ PaymentEvent : "receives"
    Payment ||--|| RevenueRecord : "originates"
    RevenueRecord ||--o{ RecoveryCase : "triggers"
    RecoveryCase ||--o{ RecoveryAction : "executes"
    AuditLog }|--|| GenericEntity : "audits"

    Payment {
        int id PK
        string razorpay_payment_id UK
        string razorpay_order_id
        int amount "paise"
        string currency
        PaymentStatus status
        PaymentMethod method
        string customer_email
        string customer_reference
        timestamp created_at
        timestamp updated_at
    }

    PaymentEvent {
        int id PK
        int payment_id FK
        string razorpay_event_id UK
        string event_type
        json payload
        PaymentEventProcessingStatus processing_status
        timestamp received_at
        timestamp processed_at
    }

    RevenueRecord {
        int id PK
        int payment_id FK,UK
        int gross_amount "paise"
        int recoverable_amount "paise"
        string currency
        RevenueStatus status
        timestamp created_at
        timestamp updated_at
    }

    RecoveryCase {
        int id PK
        int revenue_record_id FK
        string reason
        RiskStatus risk_status
        RecoveryPriority priority
        RecoveryCaseState current_state
        timestamp created_at
        timestamp updated_at
    }

    RecoveryAction {
        int id PK
        int recovery_case_id FK
        RecoveryActionType action_type
        RecoveryActionChannel channel
        RecoveryActionStatus status
        timestamp scheduled_at
        timestamp executed_at
        json result
        timestamp created_at
        timestamp updated_at
    }

    AuditLog {
        int id PK
        string entity_type
        string entity_id
        string action
        string actor
        json metadata
        timestamp timestamp
    }
```

## Core architecture rules

1. **AI never directly controls money.** The AI decision layer (`app/ai`)
   only ever produces an *advisory recommendation*. It cannot execute transactions,
   call payment gateways, or mutate payment/case statuses directly.
2. **Deterministic Policy Precedence:** The Policy Engine runs before and after AI invocation.
   It strictly blocks decisions on terminal/zero-balance cases and enforces mandatory human supervisor review on high/critical risk cases.
3. **Razorpay integration is isolated** in `app/integrations/razorpay`.
   No other module is allowed to call the Razorpay API directly.
4. **Database access is separated** via `app/db` (engine/session/Base),
   `app/models` (ORM models), and `app/services` (service layer). No raw SQL scattered across route files.
5. **Configuration is environment-driven.** `app/core/config.py` is the
   only place that reads environment variables; no secrets are
   hard-coded anywhere in the codebase.
6. **Financial Precision:** All monetary amounts are stored in integer paise
   (e.g., 50000 = ₹500.00) to eliminate floating-point rounding errors.
7. **Deterministic State Transitions:** Case transitions (e.g. `open` → `action_pending` → `recovering` → `recovered` → `closed`)
   are strictly enforced by `RecoveryService` before committing to the database.
8. **Cryptographic Signature Verification:** Webhook and payment checkout signatures are validated using HMAC-SHA256 constant-time comparison before trusting request payloads.
9. **Webhook Idempotency:** Duplicate deliveries of the same Razorpay event ID are safely detected and acknowledged without duplicate side-effects.

## Day 5 component map

| Layer | Location | Status |
|---|---|---|
| API routes | `backend/app/api/routes/` | `health.py`, `status.py`, `payments.py`, `revenue.py`, `recovery.py`, `audit.py`, `webhooks.py`, `ai.py` implemented |
| Router aggregation | `backend/app/api/router.py` | Implemented |
| Config | `backend/app/core/config.py` | Implemented |
| Exceptions | `backend/app/core/exceptions.py` | Implemented (`NotFoundError`, `ConflictError`, `BadRequestError`, `InvalidStateTransitionError`) |
| DB engine/session | `backend/app/db/` | Implemented (`session.py`, `base.py`, `init_db.py`) |
| Models | `backend/app/models/` | Implemented (`enums.py`, `mixins.py`, `payment.py`, `revenue.py`, `recovery.py`, `audit.py`, `system.py`) |
| Migrations | `backend/alembic/` | Implemented (`0001_initial_system_health.py`, `0002_payment_recovery_schema.py`) |
| Schemas | `backend/app/schemas/` | Implemented (`health.py`, `payments.py`, `revenue.py`, `recovery.py`, `audit.py`, `orders.py`, `webhooks.py`) |
| AI Schemas | `backend/app/ai/schemas.py` | Implemented (`RecoveryContext`, `RawRecommendation`, `PolicyDecision`, `RecoveryRecommendation`) |
| Services | `backend/app/services/` | Implemented (`payment_service.py`, `revenue_service.py`, `recovery_service.py`, `audit_service.py`, `webhook_service.py`) |
| Integrations | `backend/app/integrations/razorpay/` | Implemented (`client.py`, `service.py`, `signature.py`, `exceptions.py`) |
| AI Decision & Policy | `backend/app/ai/` | Implemented (`decision_engine.py`, `policy_engine.py`, `provider.py`, `prompts.py`, `exceptions.py`, `schemas.py`) |
| Frontend dashboard shell | `frontend/src/` | Implemented (placeholder data) |





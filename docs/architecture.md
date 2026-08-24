# RecoverAI — Architecture (Day 2 Snapshot)

This document describes the architecture **as planned and built**. Day 1 established
the foundation, and Day 2 implemented the core PostgreSQL/SQLAlchemy 2.x data model
and Alembic migration infrastructure. Items marked *(future)* are not implemented yet.

## High-level flow (target end state)

```mermaid
flowchart LR
    A[Payment Failure Event] --> B[Detect Revenue at Risk]
    B --> C[Diagnose Failure Reason]
    C --> D["AI Agent (Gemini)\nRecommend Intervention"]
    D --> E[Policy Engine\nDeterministic Rules]
    E -->|Authorized| F[Action Executor]
    E -->|Rejected| G[Log & Escalate]
    F --> H[Razorpay Integration]
    F --> I[Audit Trail]
    G --> I
    H --> I
    I --> J[Analytics / Measurement]
```

## Database Schema & Domain Flow (Day 2)

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

1. **AI never directly controls money.** The AI agent layer (`app/agents`)
   only ever produces a *recommendation*. Every recommendation must pass
   through the policy engine (`app/policies`) before any action reaches
   the Action Executor. *(agents/policies/executor are future work)*
2. **Razorpay integration is isolated** in `app/integrations/razorpay`.
   No other module is allowed to call the Razorpay API directly.
3. **AI logic is isolated** in `app/agents`, separate from routes, models,
   business rules, and payment execution.
4. **Database access is separated** via `app/db` (engine/session/Base) and
   `app/models` (ORM models). No raw SQL scattered across route files.
5. **Configuration is environment-driven.** `app/core/config.py` is the
   only place that reads environment variables; no secrets are
   hard-coded anywhere in the codebase.
6. **Financial Precision:** All monetary amounts are stored in integer paise
   (e.g., 50000 = ₹500.00) to eliminate floating-point rounding errors.

## Day 2 component map

| Layer | Location | Status |
|---|---|---|
| API routes | `backend/app/api/routes/` | `health.py`, `status.py` implemented |
| Config | `backend/app/core/config.py` | Implemented |
| DB engine/session | `backend/app/db/` | Implemented (`session.py`, `base.py`, `init_db.py`) |
| Models | `backend/app/models/` | Implemented (`enums.py`, `mixins.py`, `payment.py`, `revenue.py`, `recovery.py`, `audit.py`, `system.py`) |
| Migrations | `backend/alembic/` | Implemented (`0001_initial_system_health.py`, `0002_payment_recovery_schema.py`) |
| Schemas | `backend/app/schemas/` | `health.py` implemented (domain schemas scheduled next) |
| Services | `backend/app/services/` | Empty — future |
| Agents (AI) | `backend/app/agents/` | Empty — future |
| Policies | `backend/app/policies/` | Empty — future |
| Razorpay integration | `backend/app/integrations/razorpay/` | Empty — future |
| Webhooks | `backend/app/webhooks/` | Empty — future |
| Frontend dashboard shell | `frontend/src/` | Implemented (placeholder data) |


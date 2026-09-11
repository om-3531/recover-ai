# RecoverAI — AI Revenue Recovery

RecoverAI is an AI-powered revenue recovery platform designed to help businesses recover lost revenue from failed payments.

When a payment fails, RecoverAI receives the payment event, analyzes the failure using AI, generates a recovery recommendation, and passes that recommendation through a deterministic Policy Engine before any recovery action is executed.

Low-risk cases can be recovered automatically, while high-risk cases require human approval. RecoverAI also provides payment tracking, recovery case management, AI decisions, analytics, webhook processing, duplicate protection, and a complete audit trail.

> **In simple terms:** RecoverAI helps businesses recover more revenue from failed payments while keeping financial actions safe, controlled, and auditable.

---

## 🚀 Key Features

### 1. 💳 Failed Payment Detection

RecoverAI processes failed payment events through a webhook-based workflow.

The system captures payment information and creates the corresponding payment, revenue, and recovery records.

### 2. 🧠 AI-Powered Failure Diagnosis

RecoverAI uses AI to analyze failed payment cases and generate recovery recommendations.

The AI provides:

- Failure diagnosis
- Confidence level
- Recommended recovery action
- Recommended recovery channel
- Risk-aware decision support

The project supports Gemini AI with a safe Mock AI fallback for reliable demonstration.

### 3. 🛡️ Deterministic Policy Engine

AI does not directly control financial transactions.

Every AI-recommended recovery action is checked by a server-side Policy Engine before execution.

The Policy Engine evaluates:

- Transaction amount
- Risk level
- Recovery action
- Approval requirements
- Safety constraints

This creates a clear separation between **AI recommendation** and **financial authorization**.

### 4. 👤 Human Approval for High-Risk Actions

High-risk recovery actions require human approval before execution.

The workflow is:

```text
AI Recommendation
        ↓
Policy Engine
        ↓
Human Approval Required
        ↓
Approval
        ↓
Recovery Execution
5. ⚡ Automated Low-Risk Recovery

Low-risk cases can follow an automated recovery workflow.

Failed Payment
      ↓
AI Diagnosis
      ↓
Policy Check
      ↓
Auto Approval
      ↓
Recovery Action
      ↓
Recovery Tracking

This reduces manual work and enables faster recovery of failed payments.

6. 🔄 Webhook & Idempotency Protection

RecoverAI protects against duplicate payment webhooks.

If the same webhook is received multiple times, the system detects the duplicate and prevents duplicate payment or recovery cases from being created.

First Webhook
     ↓
Processed
     ↓
Payment + Revenue + Recovery Case

Same Webhook Again
     ↓
Duplicate Detected
     ↓
Ignored Safely
7. 📋 Recovery Queue

The Recovery Queue provides an operational view of recovery cases.

It includes:

Payment failure reason
Risk level
Priority
Recovery status
Recovery orchestration
Case timeline
8. 🤖 AI Decisions

The AI Decisions page provides visibility into AI recommendations and approval decisions.

It displays:

AI diagnosis
Confidence
Recommended recovery channel
Human approval requirement
Policy constraints
Approval status

The AI recommendation remains separate from final financial authorization.

9. 📊 Analytics Dashboard

RecoverAI provides analytics for monitoring revenue recovery performance.

The dashboard includes:

Recoverable revenue
Recovered revenue
Recovery rate
Execution success rate
Recovery trends
Channel performance
Failure diagnostics
10. 🧾 Audit Trail

Important system events are recorded in the audit trail.

Examples include:

Webhook received
Duplicate webhook detected
AI decision generated
Policy decision
Approval requested
Approval completed
Recovery execution
Recovery case state changes

This provides complete traceability across the recovery lifecycle.

11. 🧪 Failure Lab

The Failure Lab provides a controlled environment for demonstrating payment failure scenarios.

It can be used to simulate:

Failed payment webhooks
Recovery processing
Duplicate webhook delivery
Idempotency behavior

This allows the complete recovery workflow to be demonstrated without requiring live payment credentials.

🔄 How RecoverAI Works

The complete recovery lifecycle is:

Failed Payment
      ↓
Webhook Ingestion
      ↓
Payment / Revenue Synchronization
      ↓
AI Failure Diagnosis
      ↓
Recovery Recommendation
      ↓
Deterministic Policy Engine
      ↓
Risk / Policy Check
      ↓
 ┌───────────────────┐
 │                   │
Low Risk         High Risk
 │                   │
 ↓                   ↓
Auto Approval   Human Approval
 │                   │
 └─────────┬─────────┘
           ↓
  Recovery Execution
           ↓
  Case State Update
           ↓
      Audit Trail
🛡️ Safety & Security

RecoverAI is designed with financial-action safety in mind.

AI Does Not Directly Control Money

The AI provides diagnosis and recovery recommendations. It does not directly authorize financial transactions.

Human-in-the-Loop

High-risk recovery cases can require explicit human approval before execution.

Deterministic Policy Engine

Every recovery recommendation passes through server-side policy checks before execution.

Idempotency

Duplicate webhook deliveries are detected and safely ignored to prevent duplicate recovery processing.

Secure Webhook Verification

Webhook requests use HMAC-SHA256 signature verification.

Safe Demo Mode

The project supports synthetic/demo scenarios so the recovery workflow can be demonstrated without requiring live financial transactions.

🏗️ Architecture
                    ┌─────────────────────┐
                    │   Payment Failure   │
                    └──────────┬──────────┘
                               ↓
                    ┌─────────────────────┐
                    │ Webhook Ingestion   │
                    └──────────┬──────────┘
                               ↓
                    ┌─────────────────────┐
                    │ Payment / Revenue   │
                    │ Synchronization     │
                    └──────────┬──────────┘
                               ↓
                    ┌─────────────────────┐
                    │    AI Diagnosis     │
                    │  & Recommendation   │
                    └──────────┬──────────┘
                               ↓
                    ┌─────────────────────┐
                    │   Policy Engine     │
                    └──────────┬──────────┘
                               ↓
                    ┌─────────────────────┐
                    │ Approval / Auto     │
                    │ Decision            │
                    └──────────┬──────────┘
                               ↓
                    ┌─────────────────────┐
                    │ Recovery Execution  │
                    └──────────┬──────────┘
                               ↓
                    ┌─────────────────────┐
                    │    Audit Trail      │
                    └─────────────────────┘
🧰 Tech Stack
Frontend
React
Vite
JavaScript
React Router
Backend
Python
FastAPI
Uvicorn
Pydantic
AI
Gemini AI
Mock AI Safe Fallback
Database
SQLite
SQLAlchemy
Security
HMAC-SHA256
Idempotency protection
Server-side Policy Engine
Human approval workflow
📁 Project Structure
recover-ai/
│
├── backend/
│   ├── app/
│   └── tests/
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── layouts/
│   │   ├── services/
│   │   └── utils/
│   │
│   └── package.json
│
├── data/
├── docs/
├── n8n/
├── .env.example
├── .gitignore
├── docker-compose.yml
└── README.md
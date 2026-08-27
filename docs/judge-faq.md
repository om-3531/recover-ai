# RecoverAI — Judge Questions & Answers

## Architecture & AI

**Q: Why use AI for payment recovery?**
> Failed payments have diverse root causes (UPI timeout, card expired, insufficient
> funds, bank decline). AI diagnoses the specific failure type from webhook data and
> recommends the optimal recovery channel (email, SMS, WhatsApp, payment link) —
> something that would take a human operator minutes per case.

**Q: Can AI move money directly?**
> No. RecoverAI enforces a strict separation: AI only produces a recommendation.
> Every recommendation passes through a deterministic PolicyEngine, then requires
> human approval for high-risk cases, before any execution occurs. The frontend
> never authorizes financial actions.

**Q: What happens if AI is unavailable?**
> The system falls back to the MockAIProvider (deterministic heuristics). Gemini
> is opt-in via `AI_PROVIDER=gemini`. The core pipeline works without any AI
> provider — the policy engine and approval workflow are independent of AI.

**Q: Is Gemini mandatory?**
> No. `AI_PROVIDER=mock` is the default. Gemini is opt-in and used only for
> enhanced diagnosis quality. The demo runs entirely on mock providers.

## Risk & Policy

**Q: How is risk calculated?**
> Risk is assessed from the payment amount, failure method, and historical
> patterns. Low-risk cases (small amounts, common failure types) auto-execute.
> High-risk cases (large amounts, unusual patterns) require human approval.

**Q: What happens for high-risk payments?**
> The system creates a pending approval request visible in the Approval Center.
> An operator reviews and approves or rejects. Only approved actions are executed.
> Rejected actions are logged with the rejection reason.

**Q: Can humans override AI?**
> Yes. Operators can approve, reject, or modify recovery actions at any point.
> The Approval Center provides full human-in-the-loop control. Every decision
> is audit-logged.

**Q: What is the role of PolicyEngine?**
> PolicyEngine enforces deterministic business rules before any action:
> - Blocks actions on terminal states (already recovered, closed)
> - Blocks zero-balance recoveries
> - Enforces retry limits
> - Validates channel permissions
> - Mandatory human review for high/critical risk

**Q: What is the role of ApprovalService?**
> ApprovalService manages the approval lifecycle: create → pending → approve/reject.
> It enforces state machine rules (can't approve twice, can't execute without
> approval, can't act on expired approvals).

## Razorpay Integration

**Q: How are Razorpay webhooks secured?**
> Every inbound webhook undergoes HMAC-SHA256 signature verification using
> `hmac.compare_digest` (constant-time comparison to prevent timing attacks).
> Missing or invalid signatures are rejected.

**Q: What happens if the same webhook arrives twice?**
> Idempotent deduplication via `razorpay_event_id` unique constraint.
> The second arrival returns "duplicate" without reprocessing.

**Q: What happens if Razorpay sends a refund event?**
> Unsupported event types are safely acknowledged (HTTP 200) without processing.
> The system focuses on `payment.failed` events for recovery.

**Q: Can this work without real Razorpay credentials?**
> Yes. The simulation console (`POST /api/v1/webhooks/test/razorpay`) processes
> synthetic Razorpay payloads through the complete pipeline — signature
> verification, idempotency, risk assessment, orchestration — without requiring
> real credentials or a tunnel.

## Security & Deployment

**Q: Where are secrets stored?**
> In environment variables (`.env` file, gitignored). Never in source code,
> never in API responses, never in logs. The config-status endpoint only shows
> whether keys are present (boolean), not the actual values.

**Q: Can frontend bypass approval?**
> No. Approval enforcement is server-side in `ApprovalService` and
> `RecoveryExecutionService`. The frontend calls API endpoints, but the
> backend independently validates approval status before any execution.

**Q: Is real money moved in demo mode?**
> No. `DEMO_MODE=true` and `AI_PROVIDER=mock`. All providers are mock providers.
> The UI shows "Demo environment — recovery actions use mock providers. No real
> money is moved."

**Q: How would this scale?**
> The architecture is designed for production: PostgreSQL instead of SQLite,
> background job queue for async execution, provider abstraction for real
> channels (SendGrid, Twilio, Meta WhatsApp), and Razorpay test-mode
> integration ready for production credentials.

**Q: Why PostgreSQL in production?**
> SQLite is single-writer and doesn't support concurrent access well.
> PostgreSQL handles concurrent webhook processing, multiple operator
> sessions, and analytics queries without locking.

## Demo

**Q: What does the dashboard show?**
> Hero header with system health, demo controls (low-risk/high-risk simulation),
> Approval Center for human-in-the-loop decisions, "What Just Happened?"
> explanation panel, 8-stage pipeline visualization, live webhook monitor,
> KPI cards, and analytics.

**Q: How long is the demo?**
> 5 minutes. See `docs/buildathon-demo.md` for the step-by-step script.

**Q: What if something breaks during the demo?**
> The simulation console provides a complete backup path. Every pipeline stage
> can be triggered independently via API without the frontend.

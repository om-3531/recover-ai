# RecoverAI — Razorpay AI Buildathon 2026 Presentation Script

**Track 03:** AI Revenue Recovery  
**Presenter Flow:** 3–5 Minute Live System Demonstration

---

## 1. The Problem (30 Seconds)
"In online commerce, failed payments cause billions of dollars in preventable revenue loss. When an Indian merchant experiences a failed checkout—due to bank network timeouts, 3DS authentication drops, or UPI timeouts—standard systems either trigger blunt, generic retries or do nothing at all.
Recovering this revenue manually is too slow, while granting an unconstrained AI agent direct access to move money is unacceptably dangerous. Merchants need a system that is autonomous, intelligent, and mathematically safe."

---

## 2. The Solution: RecoverAI (45 Seconds)
"RecoverAI is an autonomous, policy-governed revenue recovery platform. Our core philosophy is:
**Detect → Diagnose → Decide → Authorize → Execute → Measure → Audit.**

Key Architectural Differentiators:
1. **AI Advisory Isolation:** Gemini analyzes failure context and recommends interventions, but **never directly moves money or approves itself**.
2. **Deterministic Policy Gate:** Server-side rules enforce maximum retry counts, block zero-balance cases, and strictly mandate human operator review for high-value transactions.
3. **Multi-Channel Provider Fleet:** Integrated support for Email, SMS, WhatsApp, and Webhooks with bounded exponential backoff.
4. **End-to-End Idempotency & Paise Precision:** 100% accurate financial calculations in integer paise with cryptographic HMAC verification."

---

## 3. Live Demonstration Sequence (2.5 Minutes)

### Step 1: Open the Dashboard & Observability
- Open the RecoverAI Dashboard at `http://localhost:5173`.
- Point out the **Live System Status** (`DB: connected`, `Demo Mode: Active`).
- Note the top 6 KPI cards: Total Cases, Recoverable Revenue, Recovered Revenue, Recovery Rate, Pending Approvals, Dispatch Success Rate.

### Step 2: Seed the 30-Day Synthetic Dataset
- Click **[⚡ Seed 50 Cases (30-Day Data)]** in the Demo Controls banner.
- Notice instant real-time telemetry update:
  - Dual-series SVG Timeline Chart showing Recoverable vs. Recovered revenue curves.
  - Case state lifecycle distribution across `open`, `action_pending`, `recovering`, `recovered`, `closed`.
  - Multi-channel dispatch table displaying conversion rates across Email, SMS, WhatsApp, and Webhooks.

### Step 3: Trigger Scenario 1 — Autonomous Low-Risk Recovery
- Select **1. Autonomous Low-Risk Recovery** in the dropdown and click **[▶ Run]**.
- **What Happens:**
  1. A ₹2,500 card network timeout failure is ingested.
  2. Gemini diagnoses the failure reason and recommends an email recovery payment link.
  3. Policy engine verifies low risk and permits auto-approval.
  4. Mock Email provider dispatches the recovery payload.
  5. RecoveryCase transitions to `recovering`.
  6. Audit trail logs the full execution.

### Step 4: Trigger Scenario 2 — High-Risk Human Review Gate
- Select **2. High-Risk Human Review Gate** and click **[▶ Run]**.
- **What Happens:**
  1. A ₹15,000 high-value failure is detected.
  2. The policy engine evaluates the risk as `HIGH` and strictly prevents auto-execution.
  3. A `RecoveryApproval` record is created in `pending` status.
  4. System safely pauses for human supervisor sign-off (`/api/v1/approvals/{id}/approve`).

### Step 5: Trigger Scenario 3 & 4 — Resilient Error Handling
- Select **3. Retryable Timeout & Backoff** and **4. Permanent Non-Retryable Error**.
- Show how temporary network blips schedule exponential retries (`next_retry_at`), while invalid recipients fail immediately without burning API quotas.

### Step 6: Filter by Date Ranges
- Click date filter pills: **Today**, **Last 7 Days**, **Last 30 Days**, **All Time**.
- Demonstrate that all aggregations are pure read-only SQL queries computed accurately in real-time.

---

## 4. Closing & Business Impact (30 Seconds)
"RecoverAI transforms passive payment failures into active recovered revenue. Because every recommendation passes through deterministic policy boundaries with complete auditability, merchants can safely automate 70%+ of routine recoveries while keeping complete human control over high-value transactions.
Thank you!"

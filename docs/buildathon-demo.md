# RecoverAI — Buildathon Demo Script

**Track 03: AI Revenue Recovery** · Razorpay Buildathon 2026

---

## Pre-Demo Setup (30 seconds before judge arrives)

1. Open two terminals:
   - **Terminal 1**: `cd backend && .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
   - **Terminal 2**: `cd frontend && npm run dev`

2. Open browser: `http://localhost:5173`

3. Verify top-right shows "Backend Online" and "Demo Mode"

---

## 0:00–0:30 — Problem Statement

> "Failed payments cause massive revenue leakage for online businesses. Manual recovery is slow, inconsistent, and doesn't scale. Merchants lose 5-15% of failed revenue because they can't react fast enough."

---

## 0:30–1:00 — Solution

> "RecoverAI is an AI-powered payment recovery agent. It automatically detects failed payments, diagnoses the cause using AI, and executes recovery actions — while keeping humans in control of high-risk decisions."

**Show the hero section:**
- Point to "RecoverAI — AI-Powered Payment Recovery"
- Point to the tagline: "Recover failed payments automatically. Keep humans in control of high-risk decisions."
- Point to system health indicators: Backend Healthy, Database Connected, Demo Mode, AI: Mock Provider

---

## 1:00–1:30 — Architecture

> "The core architecture ensures AI never directly controls money. The flow is always: AI recommends → Policy decides → Humans approve risky actions → System executes."

**Explain the 8-stage pipeline:**
1. **Webhook** — Payment failure detected
2. **AI Diagnosis** — AI classifies risk level
3. **Policy Gate** — Merchant rules applied
4. **Approval** — Human review for high-risk
5. **Approved** — Authorization granted
6. **Dispatch** — Recovery message sent
7. **Sent** — Provider confirms delivery
8. **Recovery** — Payment recovered

---

## 1:30–2:30 — Low-Risk Demo (Auto Recovery)

> "Let me show you a low-risk payment failure. The AI will diagnose it, the policy will allow automatic recovery, and the system will execute without human intervention."

**Steps:**
1. Click **"Seed 50 Cases"** button → show KPIs populate
2. Click **"Low-Risk (Auto Recovery)"** button (green)
3. Point to the **"What Just Happened?"** panel that appears:
   - "Payment webhook received from Razorpay"
   - "Signature verified — authentic Razorpay event"
   - "AI classified this payment as LOW RISK"
   - "Merchant policy allowed automatic recovery"
   - "Recovery message dispatched via mock provider"
   - "Recovery case updated — payment recovered"
4. Point to the **pipeline visualization** showing all stages completed (green)
5. Point to the **Live Recovery Monitor** showing the new event with status "processed"

---

## 2:30–3:30 — High-Risk Demo (Human Approval Required)

> "Now let me show you a high-value payment failure. The AI identifies this as high-risk, and the policy requires human approval before any action is taken."

**Steps:**
1. Click **"High-Risk (Approval Required)"** button (amber)
2. Point to the **"What Just Happened?"** panel:
   - "Payment webhook received from Razorpay"
   - "Signature verified — authentic Razorpay event"
   - "AI classified this payment as HIGH RISK"
   - "Merchant policy requires human approval for high-value payments"
   - "Execution paused safely — awaiting human approval"
   - "Approval request #X created — waiting in Approval Center below"
   - "Operator reviews in Approval Center → Approve or Reject"
   - "If approved: recovery action dispatched. If rejected: case closed safely."
   - "Full audit trail recorded for compliance"
3. Point to the **pipeline visualization** showing stages stop at "Approval" with amber "Waiting" badge
4. Point to the "Human Approval Required" badge in the flow visualization
5. **Scroll down to the Approval Center** — show the pending approval with case ID, channel, action type, and time since creation
6. **Click "✓ Approve"** on the pending approval
7. Show the approval status change to "approved" and the case state updating to "recovering"
8. Point to the **Live Recovery Monitor** showing the event with approval_required status

> "The system intentionally pauses. It does NOT execute recovery actions for high-risk payments without human approval. This is the safety guarantee. The judge can approve or reject the action live — demonstrating the human-in-the-loop control."

---

## 3:30–4:15 — Live Monitor & Timeline

> "Let me show you the real-time monitoring capabilities."

**Steps:**
1. Scroll to the **Live Recovery Monitor** section
2. Show the event feed with events from both simulations
3. Point out the newest event has a "NEW" badge
4. Click a **Case ID** link in the table (e.g., #22)
5. Show the **Timeline drawer** expanding below with chronological audit events:
   - Webhook received
   - Payment created
   - Revenue record created
   - Recovery case created
   - AI decision generated
   - Policy evaluation passed
   - Approval created
   - Execution dispatched

> "Every single state mutation is recorded in the audit trail. This is critical for compliance and debugging."

---

## 4:15–4:45 — Analytics

> "The analytics dashboard provides real-time visibility into recovery performance."

**Steps:**
1. Scroll to the **KPI cards** showing:
   - Total Cases
   - Recoverable Revenue (formatted as ₹XX,XXX.XX)
   - Recovered Revenue
   - Recovery Rate
   - Pending Approvals
   - Dispatch Success Rate
2. Point to the **Revenue Recovery Timeline** chart
3. Point to the **Case State Distribution** showing recovered/recovering/open/pending
4. Point to the **Channel Dispatch Performance** table

---

## 4:45–5:00 — Closing

> "RecoverAI doesn't let AI move money blindly. AI recommends. Policy decides. Humans control risk. Execution follows. Every action is audited. Every decision is explainable. This is responsible AI for financial operations."

---

## Key Points to Emphasize

1. **AI never controls money** — Always AI → Policy → Approval → Execution
2. **Two distinct flows** — Low-risk auto-executes, high-risk requires human approval
3. **Interactive approval** — Judges can approve/reject high-risk cases live in the demo
4. **Real-time monitoring** — Live feed, timeline, analytics
5. **Audit trail** — Every state mutation logged
6. **Demo mode safety** — Mock providers, no real money moved
7. **Production-ready architecture** — Idempotency, signature verification, rate limiting

## If Judge Asks

**"Is this real?"**
> "This is demo mode with mock providers. The architecture is production-ready — we use Razorpay test mode for development. The simulation console demonstrates the full pipeline without requiring real credentials."

**"What about security?"**
> "Webhook signatures are verified using HMAC-SHA256 with constant-time comparison. Duplicate events are idempotent. No secrets are exposed in the frontend or API responses. All monetary values are integer paise."

**"Can it work with real payments?"**
> "Yes. Configure RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, and RAZORPAY_WEBHOOK_SECRET in the backend .env, start an ngrok tunnel, and add the webhook URL in the Razorpay dashboard. The exact same pipeline runs."

**"What about the AI?"**
> "Currently using a MockAIProvider for deterministic demos. We've integrated Gemini as an opt-in provider — set AI_PROVIDER=gemini and GEMINI_API_KEY in .env to use real AI diagnosis."

---

## Files Changed (Day 21)

- `CLAUDE.md` — Fixed outdated stack info, added Day 21 status, updated roadmap
- `backend/tests/test_day21_final_readiness.py` — New: 19 final readiness tests (config, security, demo gate, pipeline, lifecycle, analytics, audit)
- `docs/buildathon-final-checklist.md` — New: Comprehensive pre-demo verification checklist

## Files Changed (Day 20)

- `frontend/src/components/ApprovalCenter.jsx` — New: Human-in-the-loop approval dashboard widget with approve/reject buttons
- `frontend/src/services/api.js` — Added approval API functions (listApprovals, approveApproval, rejectApproval, executeApproval)
- `frontend/src/pages/DashboardPage.jsx` — Integrated ApprovalCenter, enhanced What Just Happened? panel
- `backend/tests/test_day20_approval_workflow.py` — New: 29 comprehensive approval workflow tests

## Files Changed (Day 19)

- `frontend/src/pages/DashboardPage.jsx` — Hero header, What Just Happened? panel, demo controls, system health, live monitor, pipeline improvements
- `frontend/src/components/StatCard.jsx` — Visual polish
- `frontend/src/components/Sidebar.jsx` — Branding improvements
- `frontend/src/components/TopNav.jsx` — Demo mode indicator

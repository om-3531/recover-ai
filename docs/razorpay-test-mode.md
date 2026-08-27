# Razorpay Test-Mode Webhook Integration

**THIS PROJECT USES RAZORPAY TEST MODE ONLY.** Never use production Razorpay credentials with RecoverAI.

## Overview

RecoverAI can receive real Razorpay `payment.failed` webhooks via a public HTTPS tunnel (ngrok or Cloudflare Tunnel). The complete flow:

```
Razorpay Test Mode Dashboard
        ↓
payment.failed webhook
        ↓
Public HTTPS Tunnel (ngrok / Cloudflare)
        ↓
RecoverAI POST /api/v1/webhooks/razorpay
        ↓
HMAC-SHA256 Signature Verification
        ↓
Idempotency Check (PaymentEvent.razorpay_event_id)
        ↓
Payment (status=failed) + RevenueRecord (status=at_risk)
        ↓
Risk Assessment (from payment amount)
        ↓
RecoveryCase Created
        ↓
RecoveryOrchestrator → AI Decision → Policy Engine → Approval Gate → Execution
        ↓
Audit Trail (every state mutation)
        ↓
Analytics Dashboard (real-time updates)
```

## Prerequisites

1. **Razorpay Test Mode Account** — Sign up at https://razorpay.com and switch to Test Mode in the dashboard
2. **ngrok** — Install from https://ngrok.com/download (free tier works)
3. **Python 3.12+** — Already required for RecoverAI backend
4. **Node.js** — For frontend

## Step 1: Get Razorpay Test API Credentials

1. Log in to https://dashboard.razorpay.com
2. Go to **Settings → API Keys → Generate Key**
3. Copy the **Key ID** (starts with `rzp_test_`) and **Key Secret**
4. Go to **Settings → Webhooks → Add New Webhook**
   - **Webhook URL**: You'll fill this in after starting the tunnel (Step 4)
   - **Secret**: Generate or enter a strong secret — this is your `RAZORPAY_WEBHOOK_SECRET`
   - **Active Events**: Select `payment.failed` (and optionally `payment.captured`, `refund.created`)

## Step 2: Configure Backend Environment

Edit `backend/.env`:

```bash
RAZORPAY_KEY_ID=rzp_test_your_key_id_here
RAZORPAY_KEY_SECRET=your_key_secret_here
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret_here
```

Verify configuration via API:
```bash
curl http://127.0.0.1:8000/api/v1/webhooks/config-status
```

Expected response when configured:
```json
{
  "configured": true,
  "key_id_present": true,
  "key_secret_present": true,
  "webhook_secret_present": true,
  "test_mode": true,
  "status_message": "Test mode active (Key: ...here)"
}
```

## Step 3: Start Backend and Frontend

```bash
# Terminal 1: Backend
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2: Frontend
cd frontend
npm run dev
```

Verify:
- Backend: http://127.0.0.1:8000/health → OK
- Frontend: http://localhost:5173 → Dashboard loads

## Step 4: Start Public HTTPS Tunnel

### Option A: ngrok (Recommended)

```bash
# Terminal 3
ngrok http 8000
```

ngrok will display a public URL like:
```
Forwarding  https://abc123.ngrok-free.app → http://localhost:8000
```

Your webhook URL is:
```
https://abc123.ngrok-free.app/api/v1/webhooks/razorpay
```

### Option B: Cloudflare Tunnel

```bash
# Terminal 3
cloudflared tunnel --url http://localhost:8000
```

Cloudflare will display a public URL like:
```
https://abc123.trycloudflare.com
```

Your webhook URL is:
```
https://abc123.trycloudflare.com/api/v1/webhooks/razorpay
```

## Step 5: Configure Razorpay Webhook

1. Go to https://dashboard.razorpay.com → **Settings → Webhooks**
2. Edit your webhook (or create new):
   - **Webhook URL**: Paste your tunnel URL + `/api/v1/webhooks/razorpay`
   - **Secret**: Enter the same secret you put in `RAZORPAY_WEBHOOK_SECRET`
   - **Active Events**: `payment.failed`
3. Click **Save**

## Step 6: Test the Integration

### Option A: Razorpay Dashboard Test Event

1. Go to **Settings → Webhooks** in Razorpay Dashboard
2. Click **Test** on your webhook
3. Select `payment.failed` event
4. Click **Send Test Event**
5. Check RecoverAI logs — you should see the webhook received and processed

### Option B: Create a Test Payment Failure

1. Use Razorpay Test Mode checkout to create an order
2. Use a test card that fails (e.g., `4111 1111 1111 1111` with future expiry)
3. Complete checkout — payment will fail
4. Razorpay sends `payment.failed` webhook through the tunnel
5. RecoverAI processes it automatically

### Option C: Use RecoverAI Dashboard

1. Open http://localhost:5173
2. Click "🔴 Simulate Razorpay Payment Failure" (this uses the test endpoint, not real Razorpay)
3. Watch the Live Recovery Flow visualization

## Step 7: Verify the Pipeline

After a webhook is received, verify each stage:

1. **Webhook Accepted**: Check backend logs for "razorpay_webhook_received"
2. **Payment Created**: `GET /api/v1/payments` — new payment with status=failed
3. **Revenue At Risk**: RevenueRecord with status=at_risk
4. **RecoveryCase Created**: Case linked to the revenue record
5. **AI Decision**: Case has AI recommendation logged
6. **Approval Gate**: High/critical risk cases have RecoveryApproval records
7. **Execution**: Low-risk cases have actions dispatched
8. **Audit Trail**: `GET /api/v1/audit` — complete audit log
9. **Analytics Dashboard**: Dashboard updates in real-time

## Security

- **HMAC-SHA256**: Every webhook is verified using constant-time comparison (`hmac.compare_digest`)
- **Idempotency**: Duplicate events (same `X-Razorpay-Event-Id`) are safely deduplicated
- **Test Mode Only**: The system is designed for Razorpay test mode only
- **No Secrets in Logs**: Webhook secrets and API keys are never logged or returned in API responses
- **No Secrets in Frontend**: The frontend never has access to backend Razorpay credentials
- **Audit Trail**: Every state mutation is logged for compliance

## Troubleshooting

### "Invalid Razorpay webhook signature"
- Ensure `RAZORPAY_WEBHOOK_SECRET` in `backend/.env` matches the secret in Razorpay Dashboard
- The webhook secret is set per-webhook in Razorpay Dashboard, not globally

### "Missing X-Razorpay-Signature header"
- Ensure the tunnel is forwarding headers correctly
- ngrok and Cloudflare both forward all headers by default

### Webhook not received
- Verify the tunnel is running and the public URL is correct
- Check that the webhook URL in Razorpay Dashboard includes `/api/v1/webhooks/razorpay`
- Ensure the backend is running on port 8000

### Configuration status shows "Not Configured"
- Check that all three env vars are set: `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`
- Restart the backend after changing `.env`

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/webhooks/razorpay` | POST | Receive real Razorpay webhooks |
| `/api/v1/webhooks/test/razorpay` | POST | Send synthetic test webhooks |
| `/api/v1/webhooks/config-status` | GET | Razorpay configuration status |
| `/api/v1/webhooks/tunnel-guide` | GET | Tunnel setup instructions |
| `/api/v1/webhooks/fixtures` | GET | Predefined test payloads |
| `/api/v1/webhooks/recent-events` | GET | Live webhook activity feed for monitoring |

## Live Recovery Monitor

After webhooks are processed, the Live Recovery Monitor provides real-time visibility:

1. **Recent Events Feed**: `GET /api/v1/webhooks/recent-events?limit=25`
   - Shows event type, status (processed/duplicate), recovery case ID, orchestration status, timestamp
   - Frontend polls every 3 seconds with pause/resume controls

2. **Case Timeline**: `GET /api/v1/recovery-cases/{case_id}/timeline?limit=50`
   - Ordered chronological audit trail for any recovery case
   - Returns HTTP 404 if case does not exist
   - Click a Case ID in the live feed to view its timeline

3. **Pipeline Visualization**: 8-stage visual pipeline in the frontend
   - Webhook → AI Diagnosis → Policy Gate → Approval → Approved → Dispatch → Sent → Recovery
   - State-aware coloring (pending, active, completed, blocked, failed)

## Security Warning

**NEVER use production Razorpay credentials with RecoverAI.**

- This project is designed exclusively for Razorpay **Test Mode**
- Production Razorpay credentials (keys starting with `rzp_live_`) must never be used
- The `.env` file is gitignored and must never be committed
- The `config-status` endpoint never exposes secret values — only boolean indicators
- All webhook signatures are verified using constant-time comparison (HMAC-SHA256)
- Duplicate webhook events are safely deduplicated via idempotency checks
- The frontend never has access to backend Razorpay credentials

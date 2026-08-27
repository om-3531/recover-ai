/**
 * API client for the RecoverAI backend.
 *
 * Provides typed helpers for health, readiness, analytics, system status, demo seeding, and scenarios.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

/**
 * Builds a query string from key-value parameters.
 */
function buildQueryString(params = {}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.append(key, value);
    }
  });
  const str = query.toString();
  return str ? `?${str}` : "";
}

/**
 * Generic fetch wrapper with robust error classification and correlation tracking.
 */
async function fetchJson(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  let response;
  try {
    response = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
    });
  } catch (netErr) {
    const error = new Error(`Network error connecting to backend: ${netErr.message}`);
    error.status = 0;
    throw error;
  }

  const requestId = response.headers.get("X-Request-ID");

  if (!response.ok) {
    let errorDetail = `Request failed with status ${response.status}`;
    try {
      const errorJson = await response.json();
      if (errorJson && errorJson.detail) {
        errorDetail = typeof errorJson.detail === "string" ? errorJson.detail : JSON.stringify(errorJson.detail);
      } else if (errorJson && errorJson.error && errorJson.error.message) {
        errorDetail = errorJson.error.message;
      }
    } catch {
      // ignore json parse error
    }
    const error = new Error(errorDetail);
    error.status = response.status;
    error.requestId = requestId;
    throw error;
  }

  const contentType = response.headers.get("content-type");
  if (contentType && contentType.includes("application/json")) {
    return response.json();
  }
  const text = await response.text();
  return text ? JSON.parse(text) : {};
}

// --- Health & Readiness ---
export async function getBackendHealth() {
  return fetchJson("/health");
}

export async function getBackendReadiness() {
  return fetchJson("/ready");
}

// --- System & Operational Status ---
export async function getSystemStatus() {
  return fetchJson("/api/v1/system/status");
}

export async function getSystemProviders() {
  return fetchJson("/api/v1/system/providers");
}

export async function getSystemMetrics() {
  return fetchJson("/api/v1/system/metrics");
}

// --- Analytics Endpoints ---
export async function getAnalyticsOverview(params = {}) {
  return fetchJson(`/api/v1/analytics/overview${buildQueryString(params)}`);
}

export async function getRevenueAnalytics(params = {}) {
  return fetchJson(`/api/v1/analytics/revenue${buildQueryString(params)}`);
}

export async function getExecutionAnalytics(params = {}) {
  return fetchJson(`/api/v1/analytics/execution${buildQueryString(params)}`);
}

export async function getApprovalAnalytics(params = {}) {
  return fetchJson(`/api/v1/analytics/approvals${buildQueryString(params)}`);
}

export async function getFailureAnalytics(params = {}) {
  return fetchJson(`/api/v1/analytics/failures${buildQueryString(params)}`);
}

export async function getChannelAnalytics(params = {}) {
  return fetchJson(`/api/v1/analytics/channels${buildQueryString(params)}`);
}

export async function getTimelineAnalytics(params = {}) {
  return fetchJson(`/api/v1/analytics/timeline${buildQueryString(params)}`);
}

export async function getRecentActivity(limit = 20) {
  return fetchJson(`/api/v1/analytics/recent-activity?limit=${limit}`);
}

// --- Demo & Buildathon Endpoints ---
export async function seedDemoDataset(params = { count: 50, seed: 42, reset: false }) {
  return fetchJson("/api/v1/demo/seed", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function resetDemoDataset() {
  return fetchJson("/api/v1/demo/reset", {
    method: "POST",
  });
}

export async function getDemoScenarios() {
  return fetchJson("/api/v1/demo/scenarios");
}

export async function runDemoScenario(scenarioId, seed = 42) {
  return fetchJson(`/api/v1/demo/scenarios/${scenarioId}/run?seed=${seed}`, {
    method: "POST",
  });
}


// --- Merchant Policy Endpoints ---
export async function getCurrentPolicy(merchantId = "merchant_default") {
  return fetchJson(`/api/v1/policies/current?merchant_id=${encodeURIComponent(merchantId)}`);
}

export async function updatePolicy(policyId, updateData) {
  return fetchJson(`/api/v1/policies/${policyId}`, {
    method: "PUT",
    body: JSON.stringify(updateData),
  });
}

export async function validatePolicy(policyId, prospectiveData) {
  return fetchJson(`/api/v1/policies/${policyId}/validate`, {
    method: "POST",
    body: JSON.stringify(prospectiveData),
  });
}

export async function resetPolicy(policyId) {
  return fetchJson(`/api/v1/policies/${policyId}/reset`, {
    method: "POST",
  });
}

export async function previewPolicy(previewData, merchantId = "merchant_default") {
  return fetchJson(`/api/v1/policies/preview?merchant_id=${encodeURIComponent(merchantId)}`, {
    method: "POST",
    body: JSON.stringify(previewData),
  });
}

// --- Webhook Console & Testing Endpoints ---
export async function getWebhookFixtures() {
  return fetchJson("/api/v1/webhooks/fixtures");
}

export async function getWebhookTunnelGuide() {
  return fetchJson("/api/v1/webhooks/tunnel-guide");
}

export async function getRazorpayConfigStatus() {
  return fetchJson("/api/v1/webhooks/config-status");
}

export async function sendTestWebhook(eventType, payload) {
  return fetchJson("/api/v1/webhooks/test/razorpay", {
    method: "POST",
    body: JSON.stringify({ event_type: eventType, payload }),
  });
}

// --- Approval Workflow Endpoints ---
export async function listApprovals(params = {}) {
  return fetchJson(`/api/v1/approvals${buildQueryString(params)}`);
}

export async function getApprovalById(approvalId) {
  return fetchJson(`/api/v1/approvals/${approvalId}`);
}

export async function approveApproval(approvalId, approvedBy = "dashboard_operator") {
  return fetchJson(`/api/v1/approvals/${approvalId}/approve`, {
    method: "POST",
    body: JSON.stringify({ approved_by: approvedBy }),
  });
}

export async function rejectApproval(approvalId, rejectionReason = "Rejected from dashboard", approvedBy = "dashboard_operator") {
  return fetchJson(`/api/v1/approvals/${approvalId}/reject`, {
    method: "POST",
    body: JSON.stringify({ approved_by: approvedBy, rejection_reason: rejectionReason }),
  });
}

export async function executeApproval(approvalId) {
  return fetchJson(`/api/v1/approvals/${approvalId}/execute`, {
    method: "POST",
  });
}

// --- Real-Time Monitor & Timeline Endpoints ---
export async function getRecentWebhookEvents(limit = 25) {
  return fetchJson(`/api/v1/webhooks/recent-events?limit=${limit}`);
}

export async function getRecoveryCaseTimeline(caseId, limit = 50) {
  return fetchJson(`/api/v1/recovery/cases/${caseId}/timeline?limit=${limit}`);
}


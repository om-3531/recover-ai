/**
 * Thin API client for the RecoverAI backend.
 *
 * Day 1 scope: only the health check is implemented. Payment, recovery,
 * and AI-decision endpoints will be added here as the backend grows —
 * keeping fetch/error-handling logic out of components.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function getBackendHealth() {
  const response = await fetch(`${API_BASE_URL}/health`);
  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`);
  }
  return response.json();
}

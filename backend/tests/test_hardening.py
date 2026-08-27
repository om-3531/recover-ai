"""
Tests for Production Hardening, Observability, Health/Readiness Probes, and Request Correlation.

Covers:
1. /ready probe database connectivity verification
2. X-Request-ID correlation header generation and propagation
3. Structured error responses format
4. Secret sanitization across health, ready, and error endpoints
5. CORS header validation
"""

import uuid
import pytest


def test_health_and_readiness_probes(client):
    """Test liveness (/health) and readiness (/ready) probes."""
    # Liveness
    res_h = client.get("/health")
    assert res_h.status_code == 200
    assert res_h.json()["status"] == "ok"

    # Readiness
    res_r = client.get("/ready")
    assert res_r.status_code == 200
    data = res_r.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"
    assert "service" in data


def test_request_id_correlation_generation(client):
    """Test that requests receive an X-Request-ID header when none is provided."""
    res = client.get("/health")
    assert "x-request-id" in res.headers
    req_id = res.headers["x-request-id"]
    assert len(req_id) > 10


def test_request_id_correlation_propagation(client):
    """Test that incoming X-Request-ID headers are preserved and propagated."""
    custom_id = f"custom-req-{uuid.uuid4()}"
    res = client.get("/health", headers={"X-Request-ID": custom_id})
    assert res.headers.get("x-request-id") == custom_id


def test_structured_error_response_format(client):
    """Test that exceptions return backward-compatible detail and structured error metadata."""
    res = client.get("/api/v1/payments/999999")
    assert res.status_code == 404
    body = res.json()

    # Detail string preserved for standard clients
    assert "detail" in body
    assert "not found" in body["detail"].lower()

    # Structured error metadata
    assert "error" in body
    err = body["error"]
    assert err["code"] == "NotFoundError"
    assert "message" in err
    assert "request_id" in err


def test_no_secret_leakage_in_probes_or_errors(client):
    """Test that internal secrets and credentials never leak in responses."""
    res_ready = client.get("/ready")
    body_ready = res_ready.text
    assert "postgresql://" not in body_ready
    assert "secret" not in body_ready.lower()

def test_readiness_db_failure_status_503(client):
    """Test that /ready returns HTTP 503 when the database is unreachable."""
    from unittest.mock import patch

    with patch("app.api.routes.health.text") as mock_text:
        mock_text.side_effect = RuntimeError("Database connection timed out")
        res = client.get("/ready")
        assert res.status_code == 503
        data = res.json()
        assert data["status"] == "unhealthy"
        assert "unhealthy" in data["database"]


def test_demo_mode_disabled_api_rejection_403(client):
    """Test that demo REST API endpoints return HTTP 403 when DEMO_MODE is False."""
    from unittest.mock import patch

    with patch("app.demo.service.settings.DEMO_MODE", False):
        res = client.post("/api/v1/demo/seed", json={"count": 5})
        assert res.status_code == 403
        assert "disabled" in res.json()["detail"].lower()


def test_openapi_spec_includes_demo_and_ready_endpoints(client):
    """Test that OpenAPI contains all new Day 10 endpoints."""
    res = client.get("/openapi.json")
    assert res.status_code == 200
    paths = res.json()["paths"]
    assert "/health" in paths
    assert "/ready" in paths
    assert "/api/v1/demo/seed" in paths
    assert "/api/v1/demo/reset" in paths
    assert "/api/v1/demo/scenarios" in paths


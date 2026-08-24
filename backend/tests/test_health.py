"""Tests for the GET /health endpoint."""


def test_app_starts(client):
    """The FastAPI app should be importable and constructible."""
    assert client is not None


def test_health_returns_200(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_health_response_body(client):
    response = client.get("/health")
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "recover-ai-backend"


def test_api_v1_status_reachable(client):
    """Sanity check that the /api/v1 mount is wired up correctly."""
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    assert response.json()["api_version"] == "v1"

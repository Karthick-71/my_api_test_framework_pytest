"""
Smoke tests — critical happy paths that must pass before any other suite runs.

Patterns shown:
  - `@pytest.mark.smoke` for selective execution: `pytest -m smoke`
  - Direct use of the `api_client` session fixture
  - Soft schema validation against response headers
"""
import pytest


@pytest.mark.smoke
def test_base_url_reachable(api_client):
    """The configured base_url responds at all."""
    resp = api_client.get("/")
    assert resp.status_code in (200, 301, 302, 404), (
        f"Base URL appears unreachable — status {resp.status_code}"
    )


@pytest.mark.smoke
def test_get_returns_json_when_requested(api_client):
    """httpbin/get echoes back our headers as JSON."""
    resp = api_client.get("/get", headers={"X-Test-Run": "smoke"})
    assert resp.status_code == 200
    assert "application/json" in resp.headers.get("Content-Type", "")
    body = resp.json()
    assert body["headers"]["X-Test-Run"] == "smoke"


@pytest.mark.smoke
def test_post_echoes_payload(api_client):
    """httpbin/post echoes the JSON we send."""
    payload = {"hello": "sdet", "n": 42}
    resp = api_client.post("/post", json=payload)
    assert resp.status_code == 200
    assert resp.json()["json"] == payload


@pytest.mark.smoke
def test_response_under_timeout_budget(api_client):
    """A simple GET should round-trip in under 5 seconds."""
    resp = api_client.get("/get")
    assert resp.status_code == 200
    assert resp.elapsed.total_seconds() < 5, (
        f"Response took {resp.elapsed.total_seconds():.2f}s — over budget"
    )

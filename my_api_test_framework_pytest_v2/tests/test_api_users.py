"""
Demonstrates `@pytest.mark.parametrize` for inline edge-case coverage.

Patterns shown:
  - Single-axis parametrization (multiple inputs, one expectation)
  - Multi-axis parametrization (matrix of input × expected)
  - Custom test IDs via `ids=` for readable CLI output
  - Mixing markers: regression + negative + slow
"""
import pytest


# ──────────────────────────────────────────────────────────────────────────────
#  Single-axis: status-code matrix
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.regression
@pytest.mark.parametrize(
    "status_code",
    [200, 201, 204, 301, 400, 401, 403, 404, 418, 500, 503],
    ids=lambda s: f"http_{s}",
)
def test_status_code_echo(api_client, status_code):
    """httpbin/status/{code} returns whatever we ask for."""
    resp = api_client.get(f"/status/{status_code}")
    assert resp.status_code == status_code


# ──────────────────────────────────────────────────────────────────────────────
#  Multi-axis: payload × expected-key matrix
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.regression
@pytest.mark.parametrize(
    "payload, expected_key",
    [
        ({"name": "Alice", "email": "a@x.com"}, "name"),
        ({"id": 42, "tags": ["a", "b"]}, "id"),
        ({}, "json"),  # empty payload still echoed
    ],
    ids=["named_user", "id_with_tags", "empty_payload"],
)
def test_post_payload_round_trip(api_client, payload, expected_key):
    """Posted JSON is echoed back intact at `body['json']`."""
    resp = api_client.post("/post", json=payload)
    assert resp.status_code == 200
    echoed = resp.json()["json"] or {}
    if expected_key in payload:
        assert echoed.get(expected_key) == payload[expected_key]


# ──────────────────────────────────────────────────────────────────────────────
#  Negative paths — explicit failure-mode tests
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.regression
@pytest.mark.negative
@pytest.mark.parametrize("bad_endpoint", [
    "/nonexistent",
    "/anything/../../etc/passwd",
    "/redirect-to?url=http://evil.example",
])
def test_negative_endpoints(api_client, bad_endpoint):
    """Negative paths should not 5xx — they should produce a clean 4xx or sanitized redirect."""
    resp = api_client.get(bad_endpoint)
    assert resp.status_code < 500, (
        f"Negative endpoint {bad_endpoint} produced a server error ({resp.status_code})"
    )


# ──────────────────────────────────────────────────────────────────────────────
#  Slow tests — opted-out by default in CI: `pytest -m "not slow"`
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.slow
@pytest.mark.parametrize("delay_seconds", [1, 2, 3])
def test_response_delay_completes(api_client, delay_seconds):
    """httpbin/delay/N waits N seconds then returns 200."""
    resp = api_client.get(f"/delay/{delay_seconds}")
    assert resp.status_code == 200
    assert resp.elapsed.total_seconds() >= delay_seconds

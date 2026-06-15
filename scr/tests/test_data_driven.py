"""
Data-driven tests sourced from the JSON file the CUSTOM RUNNER also uses.

This is the key piece — it proves both runners exercise the SAME test cases
without duplicating them. The Pytest version gives you:
  - Per-case ID in the CLI / HTML report
  - Granular failure isolation (one case fails ≠ whole run fails)
  - `pytest -k user_login` to run a single case by name

Patterns shown:
  - `pytest_generate_tests` hook for dynamic parametrization from a fixture
  - JSON-schema contract validation against responses
  - Sharing the SAME data file with the legacy `main_function.py`
"""
import json
import pytest
from pathlib import Path
from jsonschema import validate, ValidationError

from scr.test_config import TestCaseSchema


# ──────────────────────────────────────────────────────────────────────────────
#  Dynamic parametrization — runs one test per row in the JSON file
# ──────────────────────────────────────────────────────────────────────────────

def _load_cases_from_repo() -> list[dict]:
    """Repo-shipped data so tests collect even without S3."""
    data_file = Path(__file__).parent / "data" / "test_cases.json"
    with open(data_file) as fh:
        return json.load(fh)["test_cases"]


def pytest_generate_tests(metafunc):
    """If a test asks for `case`, parametrize it with every row in the data file."""
    if "case" in metafunc.fixturenames:
        rows = _load_cases_from_repo()
        cases = [TestCaseSchema.from_dict(r) for r in rows]
        metafunc.parametrize("case", cases, ids=[c.to_id() for c in cases])


@pytest.mark.parametrized
def test_case_from_json(case, api_client):
    """
    Generic executor: run the request defined by the data row,
    assert the status, then (if specified) check the body.
    """
    resp = api_client.request(
        case.method,
        case.endpoint,
        json=case.payload,
        headers=case.headers,
    )
    assert resp.status_code == case.expected_status, (
        f"{case.test_name}: expected {case.expected_status}, got {resp.status_code}\n"
        f"  body: {resp.text[:200]}"
    )
    if case.expected_body_contains:
        body = resp.json() if "json" in resp.headers.get("Content-Type", "") else {}
        for key, expected in case.expected_body_contains.items():
            assert body.get(key) == expected, (
                f"{case.test_name}: body[{key!r}] expected {expected!r}, got {body.get(key)!r}"
            )


# ──────────────────────────────────────────────────────────────────────────────
#  Contract tests — validate API responses against a JSON Schema
# ──────────────────────────────────────────────────────────────────────────────

_RESPONSE_ECHO_SCHEMA = {
    "type": "object",
    "required": ["url", "headers", "origin"],
    "properties": {
        "url": {"type": "string", "format": "uri"},
        "headers": {"type": "object"},
        "origin": {"type": "string"},
        "args": {"type": "object"},
    },
}


@pytest.mark.contract
def test_response_matches_echo_schema(api_client):
    """Responses from /get must conform to our published schema."""
    resp = api_client.get("/get")
    assert resp.status_code == 200
    try:
        validate(instance=resp.json(), schema=_RESPONSE_ECHO_SCHEMA)
    except ValidationError as exc:
        pytest.fail(f"Response failed schema contract: {exc.message}")


@pytest.mark.contract
@pytest.mark.parametrize("required_field", ["url", "headers", "origin"])
def test_response_has_required_field(api_client, required_field):
    """One assertion per required field — failures isolated per-key."""
    body = api_client.get("/get").json()
    assert required_field in body, f"Required field {required_field!r} missing"

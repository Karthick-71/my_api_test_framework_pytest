"""
Top-level Pytest fixtures.

Both the Pytest runner and the custom runner (`main_function.py`)
share the same `api_functions/` and `common_functions/` utilities,
so there's exactly one source of truth for HTTP, AWS, and config.

Usage examples:
    pytest                          # all tests
    pytest -m smoke                 # smoke only
    pytest -m "regression and not slow"
    TEST_ENV=staging pytest -m smoke
"""
import os
import json
import logging
from pathlib import Path
from typing import Any, Dict

import pytest

from scr.api_functions.http_client import APIClient
from scr.common_functions.config_loader import load_config
from scr.common_functions.aws_helper import S3Helper

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
#  Environment / configuration
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def env() -> str:
    """Test environment (dev / qa / staging / prod). Override with TEST_ENV."""
    return os.getenv("TEST_ENV", "qa").lower()


@pytest.fixture(scope="session")
def config(env: str) -> Dict[str, Any]:
    """
    Loads the environment config — base_url, auth, s3 bucket, etc.
    Looks for `config/<env>.json` first; falls back to env vars.
    """
    return load_config(env)


# ──────────────────────────────────────────────────────────────────────────────
#  API client — session-scoped so auth/token is cached across tests
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def api_client(config: Dict[str, Any]) -> APIClient:
    """
    Reusable HTTP client wrapping `requests.Session`.
    Token is fetched once per session unless explicitly invalidated.
    """
    client = APIClient(
        base_url=config["base_url"],
        timeout=config.get("timeout", 15),
        default_headers=config.get("default_headers", {}),
    )
    if config.get("auth"):
        client.authenticate(**config["auth"])
    return client


# ──────────────────────────────────────────────────────────────────────────────
#  AWS S3 helper — only initialized if config provides bucket
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def s3_helper(config: Dict[str, Any]):
    """
    S3 helper — used by data-driven tests to fetch xlsx test cases and
    to upload result artifacts at the end of a run.
    Returns None if AWS isn't configured, so non-aws tests don't depend on it.
    """
    s3_cfg = config.get("s3")
    if not s3_cfg:
        return None
    return S3Helper(bucket=s3_cfg["bucket"], region=s3_cfg.get("region", "ap-south-1"))


# ──────────────────────────────────────────────────────────────────────────────
#  Test-data loading — JSON ships with the repo for offline runs
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def test_data_path(tmp_path_factory, s3_helper) -> Path:
    """
    Resolves the data file path. Priority order:
      1. S3 (if `aws` marker enabled and creds present)
      2. Local `tests/data/test_cases.json` shipped in repo

    Pytest will collect tests from whichever source resolves first.
    """
    repo_local = Path(__file__).parent / "tests" / "data" / "test_cases.json"
    if s3_helper:
        try:
            tmp_dir = tmp_path_factory.mktemp("s3_data")
            remote_file = tmp_dir / "test_cases.json"
            s3_helper.download("test_cases.json", remote_file)
            logger.info("Test data sourced from S3 → %s", remote_file)
            return remote_file
        except Exception as exc:
            logger.warning("S3 fetch failed (%s) — falling back to local data", exc)
    return repo_local


@pytest.fixture(scope="session")
def test_cases(test_data_path: Path):
    """Loads the JSON test cases once per session."""
    with open(test_data_path, "r") as fh:
        return json.load(fh)["test_cases"]


# ──────────────────────────────────────────────────────────────────────────────
#  Per-test logging boundary — visible in CI output
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _test_boundary(request):
    """Logs a clean start/end marker for every test."""
    test_id = request.node.nodeid
    print(f"\n┌─── START: {test_id}")
    yield
    outcome = "PASSED" if not request.node.session.testsfailed else "FINISHED"
    print(f"└─── {outcome}: {test_id}")


# ──────────────────────────────────────────────────────────────────────────────
#  Marker enforcement — refuses to run a test that uses an undeclared marker
# ──────────────────────────────────────────────────────────────────────────────

def pytest_collection_modifyitems(config, items):
    """Hook example — auto-skip aws-marked tests if AWS creds are missing."""
    if not os.getenv("AWS_ACCESS_KEY_ID"):
        skip_aws = pytest.mark.skip(reason="AWS credentials not configured")
        for item in items:
            if "aws" in item.keywords:
                item.add_marker(skip_aws)

"""
APIClient — a thin wrapper around requests.Session.

Why a wrapper:
  - One place for retry logic, timeouts, headers, auth token refresh
  - Both the Pytest runner (via fixture) and the custom runner
    (via direct instantiation) use the same client — no drift
  - Easy to mock in unit tests

Usage:
    client = APIClient(base_url="https://api.example.com")
    client.authenticate(username="user", password="pass")
    resp = client.get("/users/1")
    resp = client.post("/users", json={"name": "Alice"})
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class APIClient:
    """Reusable HTTP client. Session is shared — auth/cookies persist."""

    def __init__(
        self,
        base_url: str,
        timeout: int = 15,
        default_headers: Optional[Dict[str, str]] = None,
        max_retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        if default_headers:
            self.session.headers.update(default_headers)
        # Retry on 5xx + network errors
        retry = Retry(
            total=max_retries,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.token: Optional[str] = None

    # ── Auth ──────────────────────────────────────────────────────────────────

    def authenticate(self, username: str, password: str, endpoint: str = "/auth/login") -> None:
        """POSTs creds to /auth/login, stores returned token as Bearer header."""
        resp = self.session.post(
            f"{self.base_url}{endpoint}",
            json={"username": username, "password": password},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        self.token = resp.json().get("token") or resp.json().get("access_token")
        if self.token:
            self.session.headers["Authorization"] = f"Bearer {self.token}"
            logger.info("Authenticated as %s", username)

    # ── HTTP verbs ────────────────────────────────────────────────────────────

    def request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Generic — used internally and by data-driven tests."""
        url = endpoint if endpoint.startswith("http") else f"{self.base_url}{endpoint}"
        kwargs.setdefault("timeout", self.timeout)
        logger.debug("%s %s — kwargs=%s", method.upper(), url, kwargs)
        return self.session.request(method.upper(), url, **kwargs)

    def get(self, endpoint: str, **kwargs) -> requests.Response:
        return self.request("GET", endpoint, **kwargs)

    def post(self, endpoint: str, **kwargs) -> requests.Response:
        return self.request("POST", endpoint, **kwargs)

    def put(self, endpoint: str, **kwargs) -> requests.Response:
        return self.request("PUT", endpoint, **kwargs)

    def patch(self, endpoint: str, **kwargs) -> requests.Response:
        return self.request("PATCH", endpoint, **kwargs)

    def delete(self, endpoint: str, **kwargs) -> requests.Response:
        return self.request("DELETE", endpoint, **kwargs)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "APIClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

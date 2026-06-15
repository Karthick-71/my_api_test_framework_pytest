"""
Config loader.

Resolution order (first hit wins):
  1. `config/<env>.json` if present
  2. Environment variables (TEST_BASE_URL, TEST_AUTH_USER, etc.)
  3. Sensible defaults for `qa`

Keeps secrets out of the repo — only the shape lives in `config/<env>.json`,
actual credentials come from `.env` (gitignored) or CI secrets.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

try:
    from dotenv import load_dotenv
    load_dotenv()  # picks up .env if present
except ImportError:
    pass


_DEFAULTS = {
    "qa": {
        "base_url": "https://httpbin.org",  # public sandbox so the demo runs offline
        "timeout": 15,
        "default_headers": {"Accept": "application/json"},
    },
    "staging": {
        "base_url": "https://reqres.in/api",
        "timeout": 20,
        "default_headers": {"Accept": "application/json"},
    },
    "dev": {
        "base_url": "http://localhost:8000",
        "timeout": 10,
        "default_headers": {"Accept": "application/json"},
    },
}


def load_config(env: str = "qa") -> Dict[str, Any]:
    """Returns merged config dict for the requested env."""
    cfg: Dict[str, Any] = dict(_DEFAULTS.get(env, _DEFAULTS["qa"]))

    # File overrides
    config_file = Path(__file__).resolve().parent.parent / "config" / f"{env}.json"
    if config_file.exists():
        with open(config_file) as fh:
            cfg.update(json.load(fh))

    # Env-var overrides (highest priority)
    if env_url := os.getenv("TEST_BASE_URL"):
        cfg["base_url"] = env_url
    if user := os.getenv("TEST_AUTH_USER"):
        cfg["auth"] = {"username": user, "password": os.getenv("TEST_AUTH_PASS", "")}
    if bucket := os.getenv("TEST_S3_BUCKET"):
        cfg["s3"] = {"bucket": bucket, "region": os.getenv("AWS_REGION", "ap-south-1")}

    return cfg

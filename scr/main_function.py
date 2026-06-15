"""
Custom runner — the original way to drive the framework.

Use this for batch/scheduled runs where you want one process to:
  1. Pull a fresh xlsx/JSON of test cases from S3
  2. Execute every case sequentially
  3. Push the result artifact back to S3

For dev/CI work, prefer `pytest` — it gives you fixtures, markers,
parallelism, retries, and a proper HTML report.

Both runners share `api_functions/` and `common_functions/` so there's
no behaviour drift between them.

Usage:
    python main_function.py                          # run all cases, env=qa
    TEST_ENV=staging python main_function.py         # different env
    python main_function.py --tags smoke regression  # filter by tag
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from scr.api_functions.http_client import APIClient
from scr.common_functions.config_loader import load_config
from scr.common_functions.aws_helper import S3Helper
from scr.common_functions.result_writer import ResultWriter
from scr.test_config import TestCaseSchema

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("main_function")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Custom API test runner")
    p.add_argument("--env", default=None, help="Override TEST_ENV (qa/staging/prod)")
    p.add_argument("--tags", nargs="*", help="Run only cases with these tags")
    p.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).parent / "tests" / "data" / "test_cases.json",
        help="Path to JSON of test cases (overrides S3)",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=Path("test_results"),
        help="Where to write results.json + summary.txt",
    )
    p.add_argument(
        "--upload",
        action="store_true",
        help="Upload results to S3 after the run",
    )
    return p.parse_args()


def load_cases(args: argparse.Namespace, config: dict) -> list[TestCaseSchema]:
    """Resolve test-case source — local file or S3."""
    source = args.input
    if config.get("s3") and not source.exists():
        s3 = S3Helper(config["s3"]["bucket"], config["s3"].get("region", "ap-south-1"))
        source = Path("/tmp/test_cases.json")
        s3.download("test_cases.json", source)
    with open(source) as fh:
        raw = json.load(fh)["test_cases"]
    cases = [TestCaseSchema.from_dict(r) for r in raw]
    if args.tags:
        cases = [c for c in cases if any(t in c.tags for t in args.tags)]
        logger.info("Filtered by tags %s — %d cases remain", args.tags, len(cases))
    return cases


def run_case(client: APIClient, case: TestCaseSchema) -> tuple[bool, dict]:
    """Execute one case. Returns (passed, details)."""
    started = time.perf_counter()
    try:
        resp = client.request(
            case.method,
            case.endpoint,
            json=case.payload,
            headers=case.headers,
        )
        duration_ms = (time.perf_counter() - started) * 1000
        status_ok = resp.status_code == case.expected_status
        body_ok = True
        if case.expected_body_contains:
            body = resp.json() if "json" in resp.headers.get("Content-Type", "") else {}
            body_ok = all(
                body.get(k) == v for k, v in case.expected_body_contains.items()
            )
        passed = status_ok and body_ok
        details = {
            "status_code": resp.status_code,
            "expected_status": case.expected_status,
            "status_ok": status_ok,
            "body_ok": body_ok,
            "duration_ms": round(duration_ms, 2),
        }
        return passed, details
    except Exception as exc:
        return False, {"error": str(exc), "type": type(exc).__name__}


def main() -> int:
    args = parse_args()
    config = load_config(args.env) if args.env else load_config()
    cases = load_cases(args, config)
    if not cases:
        logger.error("No test cases to run.")
        return 2

    client = APIClient(
        base_url=config["base_url"],
        timeout=config.get("timeout", 15),
        default_headers=config.get("default_headers", {}),
    )
    if config.get("auth"):
        client.authenticate(**config["auth"])

    writer = ResultWriter(args.output_dir)
    logger.info("Running %d cases against %s", len(cases), config["base_url"])

    for case in cases:
        passed, details = run_case(client, case)
        writer.record(
            name=case.test_name,
            passed=passed,
            duration_ms=details.get("duration_ms", 0),
            details=details,
        )
        emoji = "✅" if passed else "❌"
        logger.info("%s %s — %s", emoji, case.test_name, details)

    results_file = writer.flush()
    logger.info("Results written to %s", results_file)

    if args.upload and config.get("s3"):
        s3 = S3Helper(config["s3"]["bucket"], config["s3"].get("region", "ap-south-1"))
        ts = int(time.time())
        s3.upload(results_file, f"results/run_{ts}.json", content_type="application/json")

    client.close()
    failed = sum(1 for r in writer.results if r["status"] == "FAIL")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

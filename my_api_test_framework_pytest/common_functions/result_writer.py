"""
ResultWriter — aggregates test outcomes for the custom runner.

Pytest already produces JUnit XML and HTML via plugins (we use pytest-html),
but the custom runner doesn't — this gives it parity.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


class ResultWriter:
    """Collects per-test outcomes; flushes to JSON + a human-readable summary."""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results: List[Dict[str, Any]] = []
        self.started_at = datetime.utcnow().isoformat() + "Z"

    def record(
        self,
        name: str,
        passed: bool,
        duration_ms: float,
        details: Dict[str, Any] | None = None,
    ) -> None:
        """Append a single test result."""
        self.results.append({
            "name": name,
            "status": "PASS" if passed else "FAIL",
            "duration_ms": round(duration_ms, 2),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "details": details or {},
        })

    def flush(self) -> Path:
        """Writes results.json + summary.txt; returns path to JSON."""
        ended_at = datetime.utcnow().isoformat() + "Z"
        summary = {
            "started_at": self.started_at,
            "ended_at": ended_at,
            "total": len(self.results),
            "passed": sum(1 for r in self.results if r["status"] == "PASS"),
            "failed": sum(1 for r in self.results if r["status"] == "FAIL"),
            "results": self.results,
        }
        results_file = self.output_dir / "results.json"
        results_file.write_text(json.dumps(summary, indent=2))

        summary_file = self.output_dir / "summary.txt"
        summary_file.write_text(
            f"Run @ {self.started_at}\n"
            f"  Total:  {summary['total']}\n"
            f"  Passed: {summary['passed']}\n"
            f"  Failed: {summary['failed']}\n"
            f"  Pass rate: {summary['passed'] / max(summary['total'], 1) * 100:.1f}%\n"
        )
        return results_file

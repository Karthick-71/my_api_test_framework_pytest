"""
Schema for the test-case JSON/xlsx input.

Both runners validate input rows against this schema before execution
so a malformed row fails fast with a clear message instead of mid-run.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class TestCaseSchema:
    """One row of test-case input."""
    # Tell pytest this isn't a test class (name starts with "Test")
    __test__ = False

    test_name: str
    method: str
    endpoint: str
    expected_status: int
    payload: Optional[Dict[str, Any]] = None
    headers: Optional[Dict[str, str]] = None
    expected_body_contains: Optional[Dict[str, Any]] = None
    tags: list[str] = field(default_factory=list)
    timeout_ms: int = 15000

    @classmethod
    def from_dict(cls, row: Dict[str, Any]) -> "TestCaseSchema":
        return cls(
            test_name=row["test_name"],
            method=row["method"].upper(),
            endpoint=row["endpoint"],
            expected_status=int(row["expected_status"]),
            payload=row.get("payload"),
            headers=row.get("headers"),
            expected_body_contains=row.get("expected_body_contains"),
            tags=row.get("tags", []),
            timeout_ms=int(row.get("timeout_ms", 15000)),
        )

    def to_id(self) -> str:
        """Stable pytest-friendly ID."""
        return f"{self.method.lower()}_{self.test_name}"

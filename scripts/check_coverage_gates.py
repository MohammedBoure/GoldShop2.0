"""Check gradual coverage gates from a coverage.py JSON report."""

from __future__ import annotations

import fnmatch
import json
import sys
from pathlib import Path
from typing import Iterable


GATES = [
    {"name": "overall", "minimum": 65.0, "use_totals": True, "patterns": ()},
    {
        "name": "database/client_payment_manager",
        "minimum": 78.0,
        "use_totals": False,
        "patterns": ("database/client_payment_manager/*",),
    },
    {
        "name": "database/sales_manager",
        "minimum": 82.0,
        "use_totals": False,
        "patterns": ("database/sales_manager/*",),
    },
    {
        "name": "ui/tools/print_functions.py",
        "minimum": 45.0,
        "use_totals": False,
        "patterns": ("ui/tools/print_functions.py",),
    },
]


def normalize_path(path: str) -> str:
    normalized = (path or "").replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def matches(path: str, patterns: Iterable[str]) -> bool:
    normalized = normalize_path(path)
    return any(fnmatch.fnmatchcase(normalized, pattern) for pattern in patterns)


def int_summary_value(summary: dict, key: str) -> int:
    return int(summary.get(key) or 0)


def gate_totals(coverage_data: dict, gate: dict) -> tuple[int, int]:
    if gate["use_totals"]:
        summary = coverage_data.get("totals", {})
        return (
            int_summary_value(summary, "covered_lines"),
            int_summary_value(summary, "num_statements"),
        )

    covered = 0
    statements = 0
    for path, file_data in coverage_data.get("files", {}).items():
        if not matches(path, gate["patterns"]):
            continue
        summary = file_data.get("summary", {})
        covered += int_summary_value(summary, "covered_lines")
        statements += int_summary_value(summary, "num_statements")
    return covered, statements


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: check_coverage_gates.py <coverage-json-path>", file=sys.stderr)
        return 2

    report_path = Path(argv[1])
    with report_path.open("r", encoding="utf-8") as handle:
        coverage_data = json.load(handle)

    failed = False
    print("")
    print("Coverage gates:")

    for gate in GATES:
        covered, statements = gate_totals(coverage_data, gate)
        if statements <= 0:
            print(f"  FAIL {gate['name']}: no measured statements matched gate target")
            failed = True
            continue

        percent = round((covered / statements) * 100, 2)
        status = "PASS" if percent >= gate["minimum"] else "FAIL"
        print(
            f"  {status} {gate['name']}: "
            f"{percent:.2f}% >= {gate['minimum']:.2f}% ({covered}/{statements} lines)"
        )
        if status == "FAIL":
            failed = True

    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

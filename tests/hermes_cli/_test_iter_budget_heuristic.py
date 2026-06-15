"""Standalone test for the iteration-budget heuristic (not in pytest suite).

Run with: python -m tests.hermes_cli._test_iter_budget_heuristic
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hermes_cli.kanban_swarm import _count_deliverables, _default_max_iterations, SwarmWorkerSpec


CASES = [
    ("", 0, "empty"),
    ("Just do one thing.", 0, "no deliverable keyword"),
    ("Deliverable 1: spec doc", 1, "single numbered"),
    ("## Deliverable 1: foo\n## Deliverable 2: bar", 2, "two numbered markdown"),
    ("Deliverable 1\nDeliverable 2\nDeliverable 3", 3, "three numbered"),
    ("Deliverable 1\nDeliverable 2\nDeliverable 3\nDeliverable 4", 4, "four numbered"),
    ("## Deliverable\n### Deliverable\n# Deliverable", 3, "unnumbered headers"),
    ("Deliverable-3: only numbered 3, not 1,2", 3, "out-of-order numbering"),
    ("deliverable 5: lowercase", 5, "case-insensitive"),
]


def main() -> int:
    passed = 0
    failed = 0
    for body, expected, desc in CASES:
        got = _count_deliverables(body)
        ok = got == expected
        marker = "OK  " if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1
        print(f"  [{marker}] {desc:40s} expected={expected} got={got}")
    print(f"\nCounted: {passed}/{len(CASES)} passed")

    print()
    spec1 = SwarmWorkerSpec(profile="x", title="t", body="Deliverable 1\nDeliverable 2")
    spec2 = SwarmWorkerSpec(profile="x", title="t", body="Deliverable 1\nDeliverable 2\nDeliverable 3")
    spec3 = SwarmWorkerSpec(profile="x", title="t", body="just one thing")
    spec4 = SwarmWorkerSpec(
        profile="x",
        title="t",
        body="Deliverable 1\nDeliverable 2\nDeliverable 3",
        max_iterations=90,
    )
    spec5 = SwarmWorkerSpec(
        profile="x",
        title="t",
        body="Deliverable 1\nDeliverable 2\nDeliverable 3\nDeliverable 4\nDeliverable 5",
        max_iterations=200,
    )
    expectations = [
        (spec1, None, "2 deliverables"),
        (spec2, 120, "3 deliverables (heuristic)"),
        (spec3, None, "0 deliverables"),
        (spec4, 90, "explicit 90 (override heuristic)"),
        (spec5, 200, "explicit 200 (override heuristic)"),
    ]
    for spec, expected, desc in expectations:
        got = _default_max_iterations(spec)
        ok = got == expected
        marker = "OK  " if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1
        print(f"  [{marker}] {desc:35s} expected={expected!r:6s} got={got!r}")

    print(f"\nTotal: {passed}/{len(CASES) + len(expectations)} passed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

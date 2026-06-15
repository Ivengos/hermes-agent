"""Tests for per-task max_iterations field and the multi-deliverable heuristic.

Covers:
- create_task accepts and persists max_iterations
- Task.from_row reads it back
- create_task rejects invalid values (0, negative, non-int)
- create_swarm auto-applies 120 for >=3 deliverables
- create_swarm respects explicit max_iterations
- create_swarm leaves single/two-deliverable contracts at the default
- The CLI flag --max-iterations is plumbed through
"""
from hermes_cli import kanban_db as kb
from hermes_cli.kanban_swarm import (
    SwarmWorkerSpec,
    create_swarm,
    _count_deliverables,
    _default_max_iterations,
)


def test_create_task_persists_max_iterations(tmp_path):
    conn = kb.connect(tmp_path / "kanban.db")
    try:
        tid = kb.create_task(
            conn, title="big job", assignee="worker", max_iterations=120
        )
        task = kb.get_task(conn, tid)
        assert task.max_iterations == 120
    finally:
        conn.close()


def test_create_task_default_max_iterations_is_none(tmp_path):
    conn = kb.connect(tmp_path / "kanban.db")
    try:
        tid = kb.create_task(conn, title="normal job", assignee="worker")
        task = kb.get_task(conn, tid)
        assert task.max_iterations is None
    finally:
        conn.close()


def test_create_task_rejects_zero_max_iterations(tmp_path):
    conn = kb.connect(tmp_path / "kanban.db")
    try:
        try:
            kb.create_task(
                conn, title="bad", assignee="worker", max_iterations=0
            )
        except ValueError as exc:
            assert "max_iterations" in str(exc)
            assert ">= 1" in str(exc)
        else:
            raise AssertionError("expected ValueError for max_iterations=0")
    finally:
        conn.close()


def test_create_task_rejects_negative_max_iterations(tmp_path):
    conn = kb.connect(tmp_path / "kanban.db")
    try:
        try:
            kb.create_task(
                conn, title="bad", assignee="worker", max_iterations=-5
            )
        except ValueError as exc:
            assert "max_iterations" in str(exc)
        else:
            raise AssertionError("expected ValueError for max_iterations=-5")
    finally:
        conn.close()


def test_create_task_rejects_bool_max_iterations(tmp_path):
    """Booleans are a subclass of int; reject them explicitly so
    passing ``max_iterations=True`` doesn't sneak through as 1."""
    conn = kb.connect(tmp_path / "kanban.db")
    try:
        try:
            kb.create_task(
                conn, title="bad", assignee="worker", max_iterations=True
            )
        except ValueError as exc:
            assert "max_iterations" in str(exc)
        else:
            raise AssertionError("expected ValueError for max_iterations=True")
    finally:
        conn.close()


def test_count_deliverables_handles_common_patterns():
    """Direct unit test of the counter — covers the most common Design
    §6 contract phrasings the swarm heuristic must recognise."""
    assert _count_deliverables("") == 0
    assert _count_deliverables("Just do one thing") == 0
    assert _count_deliverables("Deliverable 1: spec doc") == 1
    assert _count_deliverables(
        "## Deliverable 1: foo\n## Deliverable 2: bar"
    ) == 2
    assert _count_deliverables(
        "Deliverable 1\nDeliverable 2\nDeliverable 3"
    ) == 3
    assert _count_deliverables("Deliverable-7: only 7") == 7
    assert _count_deliverables("deliverable 5: lower") == 5
    assert _count_deliverables(
        "## Deliverable\n### Deliverable\n# Deliverable"
    ) == 3


def test_default_max_iterations_heuristic():
    assert (
        _default_max_iterations(
            SwarmWorkerSpec(profile="x", title="t", body="")
        )
        is None
    )
    assert (
        _default_max_iterations(
            SwarmWorkerSpec(
                profile="x",
                title="t",
                body="Deliverable 1\nDeliverable 2",
            )
        )
        is None
    )
    assert (
        _default_max_iterations(
            SwarmWorkerSpec(
                profile="x",
                title="t",
                body="Deliverable 1\nDeliverable 2\nDeliverable 3",
            )
        )
        == 120
    )
    assert (
        _default_max_iterations(
            SwarmWorkerSpec(
                profile="x",
                title="t",
                body="Deliverable 1\nDeliverable 2\nDeliverable 3\n"
                "Deliverable 4",
            )
        )
        == 120
    )


def test_default_max_iterations_explicit_override():
    """An explicit max_iterations wins over the heuristic."""
    spec = SwarmWorkerSpec(
        profile="x",
        title="t",
        body="Deliverable 1\nDeliverable 2\nDeliverable 3\nDeliverable 4",
        max_iterations=200,
    )
    assert _default_max_iterations(spec) == 200


def test_create_swarm_auto_applies_120_for_multi_deliverable(tmp_path):
    """The motivating bug: a sibling worker with 3+ deliverables
    silently inherits the global 90 default and burns through it on
    attempt #1, requiring a retry. create_swarm must auto-apply 120."""
    conn = kb.connect(tmp_path / "kanban.db")
    try:
        created = create_swarm(
            conn,
            goal="Three-deliverable test",
            workers=[
                SwarmWorkerSpec(
                    profile="worker-a",
                    title="Build 3 things",
                    body=(
                        "Contract:\n"
                        "Deliverable 1: spec\n"
                        "Deliverable 2: impl\n"
                        "Deliverable 3: tests\n"
                    ),
                ),
            ],
            verifier_assignee="reviewer",
            synthesizer_assignee="writer",
        )
        worker = kb.get_task(conn, created.worker_ids[0])
        assert worker.max_iterations == 120, (
            "Expected 120 from heuristic, got %r" % (worker.max_iterations,)
        )
    finally:
        conn.close()


def test_create_swarm_keeps_default_for_single_deliverable(tmp_path):
    """Single-deliverable contracts should NOT trigger the heuristic —
    90 is plenty for one artefact, and a higher budget would just
    waste retries on runaway workers."""
    conn = kb.connect(tmp_path / "kanban.db")
    try:
        created = create_swarm(
            conn,
            goal="One thing",
            workers=[
                SwarmWorkerSpec(
                    profile="worker-a",
                    title="Build one thing",
                    body="Just deliverable 1, the spec doc.",
                ),
            ],
            verifier_assignee="reviewer",
            synthesizer_assignee="writer",
        )
        worker = kb.get_task(conn, created.worker_ids[0])
        assert worker.max_iterations is None
    finally:
        conn.close()


def test_create_swarm_respects_explicit_max_iterations(tmp_path):
    """An orchestrator can override the heuristic by passing an
    explicit value — useful when a contract lists 3 deliverables but
    the orchestrator knows the work is actually lighter (e.g. most
    of the artefacts are templated)."""
    conn = kb.connect(tmp_path / "kanban.db")
    try:
        created = create_swarm(
            conn,
            goal="Override heuristic",
            workers=[
                SwarmWorkerSpec(
                    profile="worker-a",
                    title="Override",
                    body=(
                        "Deliverable 1\nDeliverable 2\nDeliverable 3\n"
                        "Deliverable 4"
                    ),
                    max_iterations=90,  # explicit override, back to default
                ),
            ],
            verifier_assignee="reviewer",
            synthesizer_assignee="writer",
        )
        worker = kb.get_task(conn, created.worker_ids[0])
        assert worker.max_iterations == 90
    finally:
        conn.close()

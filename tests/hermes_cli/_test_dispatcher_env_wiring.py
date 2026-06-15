"""Test that the dispatcher wires task.max_iterations into HERMES_MAX_ITERATIONS."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import hermes_cli.kanban_db as kb
from hermes_cli.kanban_db import _default_spawn, Task


def _make_task(tid, max_iterations):
    return Task(
        id=tid,
        title="t",
        body="b",
        assignee="worker",
        status="ready",
        priority=0,
        created_by="orchestrator",
        created_at=0,
        started_at=None,
        completed_at=None,
        workspace_kind="scratch",
        workspace_path=None,
        branch_name=None,
        claim_lock="lock",
        claim_expires=9999999999,
        tenant=None,
        result=None,
        idempotency_key=None,
        max_iterations=max_iterations,
    )


def test_dispatcher_sets_env_var_when_max_iterations_set():
    captured = {}

    class FakePopen:
        def __init__(self, cmd, **kwargs):
            captured["env"] = kwargs["env"]
            self.pid = 99999

    task = _make_task("t_test01", max_iterations=150)
    with patch.object(kb.subprocess, "Popen", FakePopen):
        with patch("os.path.isdir", return_value=True):
            with patch("builtins.open", MagicMock()):
                _default_spawn(task, "C:/tmp/workspace")

    env = captured["env"]
    assert env.get("HERMES_MAX_ITERATIONS") == "150", (
        f"Expected HERMES_MAX_ITERATIONS=150, got {env.get('HERMES_MAX_ITERATIONS')!r}"
    )
    print("  OK: dispatcher sets HERMES_MAX_ITERATIONS=150 when max_iterations=150")


def test_dispatcher_omits_env_var_when_max_iterations_none():
    captured = {}

    class FakePopen:
        def __init__(self, cmd, **kwargs):
            captured["env"] = kwargs["env"]
            self.pid = 99999

    task = _make_task("t_test02", max_iterations=None)
    with patch.object(kb.subprocess, "Popen", FakePopen):
        with patch("os.path.isdir", return_value=True):
            with patch("builtins.open", MagicMock()):
                _default_spawn(task, "C:/tmp/workspace2")

    env = captured["env"]
    # We should NOT shadow a parent-provided value. If the parent's
    # env happened to have HERMES_MAX_ITERATIONS, it should be left
    # alone; if not, no key should be set.
    assert "HERMES_MAX_ITERATIONS" not in env, (
        "Should NOT set env var when max_iterations is None; "
        f"env was {env.get('HERMES_MAX_ITERATIONS')!r}"
    )
    print("  OK: dispatcher does NOT set HERMES_MAX_ITERATIONS when max_iterations is None")


def test_dispatcher_handles_default_90():
    """A task with max_iterations=90 (the global default) should still
    be plumbed through explicitly, so that workers with an
    environment-provided default get the right value."""
    captured = {}

    class FakePopen:
        def __init__(self, cmd, **kwargs):
            captured["env"] = kwargs["env"]
            self.pid = 99999

    task = _make_task("t_test03", max_iterations=90)
    with patch.object(kb.subprocess, "Popen", FakePopen):
        with patch("os.path.isdir", return_value=True):
            with patch("builtins.open", MagicMock()):
                _default_spawn(task, "C:/tmp/workspace3")

    env = captured["env"]
    assert env.get("HERMES_MAX_ITERATIONS") == "90"
    print("  OK: dispatcher sets HERMES_MAX_ITERATIONS=90 for explicit 90")


if __name__ == "__main__":
    test_dispatcher_sets_env_var_when_max_iterations_set()
    test_dispatcher_omits_env_var_when_max_iterations_none()
    test_dispatcher_handles_default_90()
    print("\nAll dispatcher env-var tests passed")

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml  # type: ignore[import-untyped]


def _workflow() -> dict[Any, Any]:
    workflow_path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    if not isinstance(workflow, dict):
        raise ValueError("ci workflow must be a mapping")
    return cast(dict[Any, Any], workflow)


def _step_by_name(steps: list[dict[str, Any]], name: str) -> dict[str, Any]:
    return next(step for step in steps if step.get("name") == name)


def _workflow_triggers(workflow: dict[Any, Any]) -> dict[str, Any]:
    # PyYAML still treats the GitHub Actions "on" key as a YAML 1.1 boolean.
    if "on" in workflow:
        triggers = workflow["on"]
    elif True in workflow:
        triggers = workflow[True]
    else:
        raise ValueError("ci workflow triggers missing")
    if isinstance(triggers, dict):
        return cast(dict[str, Any], triggers)
    raise ValueError("ci workflow triggers must be a mapping")


def test_ci_workflow_triggers_cancel_stale_runs() -> None:
    workflow = _workflow()
    triggers = _workflow_triggers(workflow)

    assert triggers["push"]["branches"] == ["main"]
    assert "pull_request" in triggers
    assert triggers["workflow_dispatch"] is None
    assert workflow["concurrency"] == {
        "group": "${{ github.workflow }}-${{ github.ref }}",
        "cancel-in-progress": True,
    }


def test_ci_workflow_uses_explicit_minimal_permissions() -> None:
    workflow = _workflow()

    assert workflow["permissions"] == {
        "contents": "read",
        "checks": "write",
    }
    assert workflow["permissions"] != "write-all"


def test_ci_pytest_step_has_bounded_timeout_and_failure_receipts() -> None:
    workflow = _workflow()
    steps = workflow["jobs"]["test"]["steps"]
    pytest_step = _step_by_name(steps, "Pytest")

    assert pytest_step["timeout-minutes"] == 120
    assert pytest_step["run"] == "uv run -m pytest -vv --maxfail=1 --durations=25 --durations-min=1"


def test_ci_job_has_bounded_timeout() -> None:
    workflow = _workflow()
    job = workflow["jobs"]["test"]

    assert job["timeout-minutes"] == 135


def test_ci_matrix_keeps_exact_runners_and_python_versions() -> None:
    workflow = _workflow()
    job = workflow["jobs"]["test"]
    strategy = job["strategy"]
    matrix = strategy["matrix"]

    assert strategy["fail-fast"] is False
    assert matrix["os"] == ["ubuntu-latest", "windows-2025-vs2026"]
    assert "windows-latest" not in matrix["os"]
    assert matrix["python-version"] == ["3.12", "3.13"]


def test_ci_matrix_interpreter_binding_is_verified() -> None:
    workflow = _workflow()
    job = workflow["jobs"]["test"]
    steps = job["steps"]
    install_step = _step_by_name(steps, "Install")
    verify_step = _step_by_name(steps, "Verify Python matrix")

    assert job["env"]["UV_PYTHON"] == "${{ matrix.python-version }}"
    assert install_step["run"] == (
        "uv sync --frozen --python ${{ matrix.python-version }} --extra core --extra web --extra dev --extra bridge"
    )
    assert "expected='${{ matrix.python-version }}'" in verify_step["run"]

from __future__ import annotations

from pathlib import Path

import yaml


def _workflow() -> dict:
    workflow_path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
    return yaml.safe_load(workflow_path.read_text(encoding="utf-8"))


def _step_by_name(steps: list[dict], name: str) -> dict:
    return next(step for step in steps if step.get("name") == name)


def _workflow_triggers(workflow: dict) -> dict:
    # PyYAML still treats the GitHub Actions "on" key as a YAML 1.1 boolean.
    return workflow.get("on", workflow.get(True))


def test_ci_workflow_triggers_cancel_stale_runs() -> None:
    workflow = _workflow()
    triggers = _workflow_triggers(workflow)

    assert triggers["push"]["branches"] == ["main"]
    assert "pull_request" in triggers
    assert workflow["concurrency"] == {
        "group": "${{ github.workflow }}-${{ github.ref }}",
        "cancel-in-progress": True,
    }


def test_ci_pytest_step_has_bounded_timeout_and_failure_receipts() -> None:
    workflow = _workflow()
    steps = workflow["jobs"]["test"]["steps"]
    pytest_step = _step_by_name(steps, "Pytest")

    assert pytest_step["timeout-minutes"] == 45
    assert pytest_step["run"] == "uv run -m pytest -vv --maxfail=1 --durations=25 --durations-min=1"


def test_ci_job_has_bounded_timeout() -> None:
    workflow = _workflow()
    job = workflow["jobs"]["test"]

    assert job["timeout-minutes"] == 55


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
        "uv sync --frozen --python ${{ matrix.python-version }} --extra core --extra web --extra dev"
    )
    assert "expected='${{ matrix.python-version }}'" in verify_step["run"]

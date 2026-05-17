from __future__ import annotations

from pathlib import Path

import yaml


def _workflow() -> dict:
    workflow_path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
    return yaml.safe_load(workflow_path.read_text(encoding="utf-8"))


def test_ci_pytest_step_has_bounded_timeout_and_failure_receipts() -> None:
    workflow = _workflow()
    steps = workflow["jobs"]["test"]["steps"]
    pytest_step = next(step for step in steps if step.get("name") == "Pytest")

    assert pytest_step["timeout-minutes"] == 45
    assert pytest_step["run"] == "uv run -m pytest -vv --maxfail=1 --durations=25 --durations-min=1"


def test_ci_matrix_keeps_windows_runner_pinned_and_interpreter_verified() -> None:
    workflow = _workflow()
    job = workflow["jobs"]["test"]
    steps = job["steps"]

    assert "windows-2025-vs2026" in job["strategy"]["matrix"]["os"]
    assert job["env"]["UV_PYTHON"] == "${{ matrix.python-version }}"
    assert any(step.get("name") == "Verify Python matrix" for step in steps)

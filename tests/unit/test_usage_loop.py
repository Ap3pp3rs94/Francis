from __future__ import annotations

import json
import subprocess
from pathlib import Path

from services.orchestrator.app.usage_loop import build_current_work, build_next_best_action, build_repo_focus


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo_root), *args], check=True, capture_output=True, text=True)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_build_repo_focus_reports_dirty_repo(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init")
    changed = repo_root / "dirty.txt"
    changed.write_text("draft\n", encoding="utf-8")

    focus = build_repo_focus(repo_root)

    assert focus["available"] is True
    assert focus["dirty"] is True
    assert focus["changed_count"] >= 1
    assert "dirty.txt" in focus["top_paths"]


def test_usage_loop_prefers_repo_tests_after_terminal_failure(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    workspace_root = repo_root / "workspace"
    repo_root.mkdir()
    workspace_root.mkdir()
    _git(repo_root, "init")
    (repo_root / "dirty.txt").write_text("draft\n", encoding="utf-8")
    _write_jsonl(
        workspace_root / "telemetry" / "events.jsonl",
        [
            {
                "id": "telemetry-1",
                "ts": "2026-03-11T00:00:00+00:00",
                "ingested_at": "2026-03-11T00:00:01+00:00",
                "run_id": "run-1",
                "kind": "telemetry.event",
                "stream": "terminal",
                "source": "terminal",
                "severity": "error",
                "text": "terminal: pytest -q tests/unit/test_usage_loop.py (exit=1)",
                "fields": {
                    "command": "pytest -q tests/unit/test_usage_loop.py",
                    "cwd": str(repo_root),
                    "exit_code": 1,
                    "stdout": "",
                    "stderr": "1 failed",
                },
            }
        ],
    )
    current_work = build_current_work(
        repo_root=repo_root,
        workspace_root=workspace_root,
        control={"mode": "assist", "kill_switch": False},
        missions={"active": [], "backlog": []},
        approvals={"pending_count": 0},
        incidents={"open_count": 0, "highest_severity": "nominal"},
        inbox={"alert_count": 0},
        runs={"last_run": {}},
        apprenticeship={"session_count": 0, "recording_count": 0, "review_count": 0, "skillized_count": 0},
    )

    next_action = build_next_best_action(current_work=current_work, control={"mode": "assist", "kill_switch": False})

    assert current_work["attention"]["kind"] == "terminal_failure"
    assert next_action["kind"] == "repo.tests"
    assert next_action["enabled"] is False
    assert "requires approval" in next_action["policy_reason"].lower()


def test_usage_loop_prioritizes_apprenticeship_generalization_when_steps_are_recorded(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    workspace_root = repo_root / "workspace"
    repo_root.mkdir()
    workspace_root.mkdir()
    _git(repo_root, "init")

    current_work = build_current_work(
        repo_root=repo_root,
        workspace_root=workspace_root,
        control={"mode": "assist", "kill_switch": False, "scopes": {"apps": ["apprenticeship", "observer"]}},
        missions={"active": [], "backlog": []},
        approvals={"pending_count": 0},
        incidents={"open_count": 0, "highest_severity": "nominal"},
        inbox={"alert_count": 0},
        runs={"last_run": {}},
        apprenticeship={
            "session_count": 1,
            "recording_count": 1,
            "review_count": 0,
            "skillized_count": 0,
            "recent_sessions": [
                {
                    "id": "teach-generalize",
                    "title": "Teach repo verification",
                    "objective": "Turn verification into a reusable workflow",
                    "status": "recording",
                    "step_count": 2,
                    "mission_id": "mission-verify",
                }
            ],
            "review_ready": [],
        },
    )

    next_action = build_next_best_action(
        current_work=current_work,
        control={"mode": "assist", "kill_switch": False, "scopes": {"apps": ["apprenticeship", "observer"]}},
    )

    assert current_work["attention"]["kind"] == "teaching_capture"
    assert current_work["apprenticeship"]["focus_session"]["id"] == "teach-generalize"
    assert next_action["kind"] == "apprenticeship.generalize"
    assert next_action["enabled"] is True
    assert next_action["args"]["session_id"] == "teach-generalize"


def test_usage_loop_prioritizes_apprenticeship_skillize_when_review_ready(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    workspace_root = repo_root / "workspace"
    repo_root.mkdir()
    workspace_root.mkdir()
    _git(repo_root, "init")

    current_work = build_current_work(
        repo_root=repo_root,
        workspace_root=workspace_root,
        control={"mode": "assist", "kill_switch": False, "scopes": {"apps": ["apprenticeship", "observer"]}},
        missions={"active": [], "backlog": []},
        approvals={"pending_count": 0},
        incidents={"open_count": 0, "highest_severity": "nominal"},
        inbox={"alert_count": 0},
        runs={"last_run": {}},
        apprenticeship={
            "session_count": 1,
            "recording_count": 0,
            "review_count": 1,
            "skillized_count": 0,
            "recent_sessions": [
                {
                    "id": "teach-skillize",
                    "title": "Teach HUD review",
                    "objective": "Package the review workflow",
                    "status": "review",
                    "step_count": 3,
                    "mission_id": "mission-review",
                }
            ],
            "review_ready": [
                {
                    "id": "teach-skillize",
                    "title": "Teach HUD review",
                    "objective": "Package the review workflow",
                    "status": "review",
                    "step_count": 3,
                    "mission_id": "mission-review",
                }
            ],
        },
    )

    next_action = build_next_best_action(
        current_work=current_work,
        control={"mode": "assist", "kill_switch": False, "scopes": {"apps": ["apprenticeship", "observer"]}},
    )

    assert current_work["attention"]["kind"] == "teaching_review"
    assert current_work["apprenticeship"]["focus_session"]["id"] == "teach-skillize"
    assert next_action["kind"] == "apprenticeship.skillize"
    assert next_action["enabled"] is True
    assert next_action["args"]["session_id"] == "teach-skillize"

from __future__ import annotations

from pathlib import Path


def test_default_feature_flags_are_stable_across_reads(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))

    from francis.kernel import feature_flags

    first = feature_flags.list_flags()
    second = feature_flags.list_flags()

    assert second == first
    assert {item["source"] for item in first} == {"env"}


def test_trust_tracker_adjust_is_idempotent(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from francis.trust import tracker

    first = tracker.adjust_level(
        op="set",
        value=4,
        reason="bootstrap",
        actor="test",
        domain="platform",
        idempotency_key="corr-1",
        risk_tier="medium",
    )
    assert first["ok"] is True
    assert first["applied"] is True
    assert first["level"] == 4
    assert first["decision"]["risk_tier"] == "medium"

    second = tracker.adjust_level(
        op="set",
        value=9,
        reason="should_not_reapply",
        actor="test",
        domain="platform",
        idempotency_key="corr-1",
        risk_tier="medium",
    )
    assert second["ok"] is True
    assert second["applied"] is False
    assert second["level"] == 4

    history = tracker.list_history(limit=10, actor="test")
    assert len(history) == 1
    assert history[0]["idempotency_key"] == "corr-1"


def test_authority_boundaries_block_scope_escape() -> None:
    from francis.trust.boundaries import evaluate_request

    result = evaluate_request(
        {
            "action": "plugin.run",
            "risk_tier": "critical",
            "scope": {"path": "C:/forbidden/project"},
        },
        {
            "allowed_paths": ["C:/allowed/project"],
            "allowed_actions": ["plugin.run"],
            "max_risk_tier": "medium",
            "approvals_required": True,
        },
        trust_level=6,
    )

    assert result["ok"] is False
    assert "path_outside_boundary" in result["issues"]
    assert "risk_tier_outside_boundary" in result["issues"]


def test_world_state_snapshot_reports_repo_and_data(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    task_dir = data_root / "tasks" / "tsk_example"
    second_task_dir = data_root / "tasks" / "tsk_running"
    (repo_root / "plugins" / "generated").mkdir(parents=True, exist_ok=True)
    (data_root / "approvals" / "pending").mkdir(parents=True, exist_ok=True)
    task_dir.mkdir(parents=True, exist_ok=True)
    second_task_dir.mkdir(parents=True, exist_ok=True)
    (data_root / "logs").mkdir(parents=True, exist_ok=True)
    (data_root / "approvals" / "pending" / "a.json").write_text(
        '{"id":"a","action":"plugin.run","reason":"test","status":"pending","ts":1}', encoding="utf-8"
    )
    (task_dir / "record.json").write_text(
        '{"task_id":"tsk_example","status":"pending","capability":"plugin.run","objective":"First","created_at":"2026-04-11T10:00:00+00:00","updated_at":"2026-04-11T10:00:00+00:00"}',
        encoding="utf-8",
    )
    (second_task_dir / "record.json").write_text(
        '{"task_id":"tsk_running","status":"running","capability":"codex.supervised_exec","objective":"Second","created_at":"2026-04-11T11:00:00+00:00","updated_at":"2026-04-11T12:00:00+00:00","assigned_to":"worker-1"}',
        encoding="utf-8",
    )

    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from francis.world_state.snapshot import snapshot

    state = snapshot()
    assert state["ok"] is True
    assert state["repo_root"] == str(repo_root.resolve())
    assert state["data_dir"] == str(data_root.resolve())
    assert state["counts"]["pending_approvals"] == 1
    assert state["counts"]["tasks"] == 2
    assert state["overview"]["task_status_counts"]["pending"] == 1
    assert state["overview"]["task_status_counts"]["running"] == 1
    assert state["overview"]["pending_approvals"][0]["action"] == "plugin.run"
    incident_ids = {item["id"] for item in state["overview"]["incidents"]}
    assert "governance.pending_approvals" in incident_ids
    assert state["overview"]["recent_tasks"][0]["id"] == "tsk_running"
    assert state["overview"]["recent_tasks"][0]["assigned_to"] == "worker-1"


def test_world_state_snapshot_derives_governance_backlog_states(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    blocked_task_dir = data_root / "tasks" / "tsk_blocked"
    approval_task_dir = data_root / "tasks" / "tsk_approval"
    blocked_task_dir.mkdir(parents=True, exist_ok=True)
    approval_task_dir.mkdir(parents=True, exist_ok=True)

    (blocked_task_dir / "record.json").write_text(
        """
{
  "task_id": "tsk_blocked",
  "status": "accepted",
  "capability": "plugin.run",
  "objective": "Blocked task",
  "updated_at": "2026-04-11T12:05:00+00:00",
  "result": {
    "kind": "task.result",
    "data": {
      "status": "blocked",
      "error": "insufficient_trust"
    }
  }
}
""".strip(),
        encoding="utf-8",
    )
    (approval_task_dir / "record.json").write_text(
        """
{
  "task_id": "tsk_approval",
  "status": "accepted",
  "capability": "plugin.run",
  "objective": "Awaiting approval",
  "updated_at": "2026-04-11T12:10:00+00:00",
  "result": {
    "kind": "task.result",
    "data": {
      "status": "needs_approval",
      "message": "Approval required before rerun."
    }
  }
}
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from francis.world_state.snapshot import snapshot

    state = snapshot()
    assert state["counts"]["tasks"] == 2
    assert state["counts"]["queued_tasks"] == 0
    assert state["counts"]["blocked_tasks"] == 1
    assert state["counts"]["approval_pending_tasks"] == 1
    assert state["overview"]["task_status_counts"]["blocked"] == 1
    assert state["overview"]["task_status_counts"]["needs_approval"] == 1
    assert state["overview"]["recent_tasks"][0]["id"] == "tsk_approval"
    assert state["overview"]["recent_tasks"][0]["status"] == "needs_approval"
    assert state["overview"]["recent_tasks"][0]["status_reason"] == "Approval required before rerun."
    assert state["overview"]["recent_tasks"][1]["status"] == "blocked"
    assert state["overview"]["recent_tasks"][1]["status_reason"] == "insufficient_trust"
    assert state["counts"]["active_incidents"] >= 2
    incident_ids = {item["id"] for item in state["overview"]["incidents"]}
    assert "governance.awaiting_approval" in incident_ids
    assert "governance.blocked_tasks" in incident_ids


def test_orb_snapshot_reports_planes_and_forbidden_transitions(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    meta_root = repo_root / "meta"
    data_root = repo_root / "data"
    meta_root.mkdir(parents=True, exist_ok=True)
    data_root.mkdir(parents=True, exist_ok=True)

    (meta_root / "plane_map.yaml").write_text(
        """
meta:
  model_id: francis.plane_map
  version: 2
planes:
  - id: P1_INTERFACE
    name: Interface
    category: interface
    purpose: Capture requests
    side_effects_allowed: false
    default_risk_class: low
  - id: P7_EXECUTION
    name: Execution
    category: execution
    purpose: Run tools
    side_effects_allowed: true
    default_risk_class: critical
forbidden_transitions:
  - from: P1_INTERFACE
    to: P7_EXECUTION
    reason: direct shortcut forbidden
""".strip(),
        encoding="utf-8",
    )
    (meta_root / "action_taxonomy.yaml").write_text(
        """
meta:
  taxonomy_id: francis.action_taxonomy
  version: 3
controls:
  - id: permission_gate
    description: Require identity validation
  - id: approvals_gate
    description: Require approvals
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from francis.world_state.orb import snapshot

    state = snapshot()
    assert state["ok"] is True
    assert state["subsystem"] == "orb_status"
    assert state["model"]["plane_map_version"] == 2
    assert state["model"]["action_taxonomy_version"] == 3
    assert state["planes"][0]["id"] == "P1_INTERFACE"
    assert state["gates"][0]["id"] == "permission_gate"
    assert state["transitions"]["forbidden"][0]["reason"] == "direct shortcut forbidden"


def test_orb_snapshot_handback_preserves_exact_mission_approval_handoff(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    meta_root = repo_root / "meta"
    data_root = repo_root / "data"
    meta_root.mkdir(parents=True, exist_ok=True)
    data_root.mkdir(parents=True, exist_ok=True)

    (meta_root / "plane_map.yaml").write_text(
        """
meta:
  model_id: francis.plane_map
  version: 2
planes:
  - id: P1_INTERFACE
    name: Interface
    category: interface
    purpose: Capture requests
    side_effects_allowed: false
    default_risk_class: low
  - id: P3_GOVERNANCE
    name: Governance
    category: governance
    purpose: Enforce approvals
    side_effects_allowed: false
    default_risk_class: high
  - id: P7_EXECUTION
    name: Execution
    category: execution
    purpose: Run tools
    side_effects_allowed: true
    default_risk_class: critical
forbidden_transitions:
  - from: P1_INTERFACE
    to: P7_EXECUTION
    reason: direct shortcut forbidden
""".strip(),
        encoding="utf-8",
    )
    (meta_root / "action_taxonomy.yaml").write_text(
        """
meta:
  taxonomy_id: francis.action_taxonomy
  version: 3
controls:
  - id: permission_gate
    description: Require identity validation
  - id: approvals_gate
    description: Require approvals
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from francis.world_state import orb as orb_module

    monkeypatch.setattr(
        orb_module,
        "operator_mode_snapshot",
        lambda: {
            "control_mode": {
                "id": "assist",
                "label": "Assist",
                "writes": "restricted",
                "implementation_status": "active",
            },
            "focus": {
                "plane_id": "P3_GOVERNANCE",
                "label": "Governance",
                "reason": "Approval apr_exact_321 is pending before the mission can continue.",
            },
            "backlog": {
                "pending_approvals": 1,
                "approval_pending_tasks": 1,
                "blocked_tasks": 0,
                "blocked_missions": 1,
                "deadlettered_missions": 0,
                "running_tasks": 0,
                "active_missions": 0,
                "queued_tasks": 0,
                "queued_missions": 0,
                "completed_missions": 0,
            },
            "continuity": {
                "headline": "Approval handback remains visible",
                "focus": [
                    {
                        "id": "msn_approval_focus",
                        "status": "blocked",
                        "recommended_action": "review_exact_approval",
                        "last_task_approval_id": "apr_exact_321",
                        "last_task_previous_approval_id": "apr_exact_320",
                        "last_task_approval_status": "pending",
                        "latest_activity": {
                            "name": "governance_hold",
                            "status": "blocked",
                        },
                    }
                ],
                "recently_completed": [],
                "deadletter_preview": [],
            },
        },
    )
    monkeypatch.setattr(
        orb_module,
        "observer_incident_snapshot",
        lambda: {
            "incidents": [
                {
                    "id": "governance.blocked_tasks",
                    "severity": "error",
                    "title": "Tasks are blocked by governance",
                    "category": "governance",
                    "probe": "task_runtime",
                }
            ]
        },
    )
    monkeypatch.setattr(
        orb_module,
        "observer_summary",
        lambda snapshot: {
            "headline": "Observer flagged 1 active incident(s); highest-priority issue: Tasks are blocked by governance.",
            "decision": "urgent_review",
            "counts": {"active": 1, "critical": 0, "error": 1, "warning": 0, "info": 0},
            "focus": [{"id": "governance.blocked_tasks", "title": "Tasks are blocked by governance"}],
            "incident_ids": ["governance.blocked_tasks"],
            "probes": ["task_runtime"],
            "anomaly": {
                "score": 50,
                "level": "error",
                "reasons": ["error incidents: 1", "active probes: task_runtime"],
            },
        },
    )

    state = orb_module.snapshot()

    assert state["state"]["render_state"] == "handback"
    assert state["state"]["incident_pressure"]["source"] == "observer"
    assert state["state"]["incident_pressure"]["observer"]["score"] == 50
    assert state["state"]["interjection_state"]["reason"].startswith("Approval apr_exact_321")
    assert state["state"]["handback_state"]["state"] == "operator_action_required"
    focus_item = state["state"]["handback_state"]["focus"]
    assert focus_item["id"] == "msn_approval_focus"
    assert focus_item["last_task_approval_id"] == "apr_exact_321"
    assert focus_item["last_task_previous_approval_id"] == "apr_exact_320"
    assert focus_item["last_task_approval_status"] == "pending"
    assert focus_item["latest_activity"]["name"] == "governance_hold"


def test_orb_snapshot_handback_uses_failed_preview_as_receipt_focus() -> None:
    from francis.world_state.orb import _handback_state

    handback = _handback_state(
        {
            "headline": "Failed mission needs receipt-backed recovery review",
            "focus": [],
            "recently_completed": [],
            "failed_preview": [
                {
                    "id": "msn_failed_receipt",
                    "status": "failed",
                    "recommended_action": "retry_or_deadletter",
                    "current_task": {
                        "operation_id": "tsk_failed_receipt",
                        "trace_id": "trace_failed_receipt",
                        "run_id": "run_failed_receipt",
                        "artifact_dir": "D:/Francis/.data/artifacts/run_failed_receipt",
                        "handoff_action": "retry_or_deadletter",
                        "next_step": "review_operation_detail",
                    },
                    "latest_memory_receipt": {
                        "mission_id": "msn_failed_receipt",
                        "operation_id": "tsk_failed_receipt",
                        "operation_status": "failed",
                        "operation_error": "plan_missing",
                        "recovery_next_step": "review_operation_detail",
                    },
                }
            ],
            "deadletter_preview": [],
        }
    )

    assert handback["state"] == "failed_recovery"
    assert handback["focus_source"] == "failed_preview"
    assert handback["failed_count"] == 1
    assert handback["focus"]["id"] == "msn_failed_receipt"
    assert handback["focus"]["recommended_action"] == "retry_or_deadletter"
    assert handback["focus"]["current_task"]["operation_id"] == "tsk_failed_receipt"
    assert handback["focus"]["current_task"]["trace_id"] == "trace_failed_receipt"
    assert handback["focus"]["latest_memory_receipt"]["operation_status"] == "failed"
    assert handback["focus"]["latest_memory_receipt"]["recovery_next_step"] == "review_operation_detail"


def test_orb_snapshot_handback_preserves_memory_receipt_summary() -> None:
    from francis.world_state.orb import _handback_state

    handback = _handback_state(
        {
            "headline": "Completed mission receipt is ready for interface review",
            "focus": [],
            "recently_completed": [
                {
                    "id": "msn_terminal_receipt",
                    "status": "completed",
                    "recommended_action": "review_result",
                }
            ],
            "failed_preview": [],
            "deadletter_preview": [],
            "memory_receipts": [
                {
                    "id": "mem_terminal_receipt",
                    "mission_id": "msn_terminal_receipt",
                    "operation_id": "tsk_terminal_receipt",
                    "operation_status": "completed",
                    "trace_id": "trace_terminal_receipt",
                    "run_id": "run_terminal_receipt",
                    "artifact_dir": "D:/Francis/.data/artifacts/run_terminal_receipt",
                    "handoff_action": "review_result",
                }
            ],
        }
    )

    assert handback["state"] == "completion_review"
    assert handback["focus_source"] == "recently_completed"
    assert handback["focus"]["id"] == "msn_terminal_receipt"
    assert handback["memory_receipt_count"] == 1
    assert handback["latest_memory_receipt"]["id"] == "mem_terminal_receipt"
    assert handback["latest_memory_receipt"]["mission_id"] == "msn_terminal_receipt"
    assert handback["latest_memory_receipt"]["operation_id"] == "tsk_terminal_receipt"
    assert handback["latest_memory_receipt"]["trace_id"] == "trace_terminal_receipt"
    assert handback["latest_memory_receipt"]["run_id"] == "run_terminal_receipt"
    assert handback["latest_memory_receipt"]["handoff_action"] == "review_result"


def test_stack_and_services_report_known_surfaces(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    config_root = repo_root / "config"

    (repo_root / "src" / "francis" / "api").mkdir(parents=True, exist_ok=True)
    (repo_root / "src" / "francis" / "daemon").mkdir(parents=True, exist_ok=True)
    (repo_root / "src" / "francis" / "workers").mkdir(parents=True, exist_ok=True)
    (repo_root / "apps" / "chat_ui").mkdir(parents=True, exist_ok=True)
    (repo_root / "plugins").mkdir(parents=True, exist_ok=True)
    data_root.mkdir(parents=True, exist_ok=True)
    config_root.mkdir(parents=True, exist_ok=True)

    (repo_root / "src" / "francis" / "api" / "app.py").write_text("", encoding="utf-8")
    (repo_root / "src" / "francis" / "daemon" / "runner.py").write_text("", encoding="utf-8")
    (repo_root / "src" / "francis" / "workers" / "runner.py").write_text("", encoding="utf-8")

    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_CONFIG_DIR", str(config_root))

    from francis.kernel.services import services_action, services_status
    from francis.kernel.stack import stack_status

    stack = stack_status(probe_runtime=True)
    assert stack["probe_runtime"] is True
    assert stack["counts"]["total"] >= 5
    assert stack["status"] == "ok"

    services = services_status()
    by_name = {item["name"]: item for item in services["services"]}
    assert services["status"] == "ready"
    assert by_name["api"]["status"] == "ready"
    assert by_name["daemon"]["status"] == "ready"
    assert by_name["workers"]["status"] == "ready"

    action = services_action("restart", ["api", "workers"])
    assert action["ok"] is True
    assert action["simulated"] is True
    assert len(action["services"]) == 2
    assert {item["name"] for item in action["services"]} == {"api", "workers"}

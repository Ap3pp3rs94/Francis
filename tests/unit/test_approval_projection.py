from __future__ import annotations

import json
from pathlib import Path


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_approval_projection_reads_request_fallback_for_mismatch_keys(tmp_path: Path) -> None:
    from francis.governance.approval_projection import approval_projection_fields

    artifact_root = tmp_path / "artifacts"
    approval_id = "approval_industrial_request_fallback"
    mismatch_path = artifact_root / "industrial" / "approvals" / approval_id / "mismatch.json"

    expected_request = {
        "target_kind": "asset",
        "target_id": "pump-a",
        "params": {"mode": "manual", "api_key": "[REDACTED:secret]"},
    }
    previous_record = {
        "payload": {
            "target_kind": "asset",
            "target_id": "pump-a",
            "params": {"mode": "auto", "api_key": "[REDACTED:secret]"},
        }
    }
    _write_json(
        mismatch_path,
        {
            "kind": "industrial.safety.validate.mismatch",
            "request": expected_request,
            "approval_record": previous_record,
        },
    )

    projected = approval_projection_fields({"id": approval_id, "payload": {}}, artifact_root=artifact_root)

    assert projected["replacement_kind"] == "industrial.safety.validate.mismatch"
    assert projected["replacement_reason"] == "approval_payload_mismatch"
    assert projected["replacement_expected_payload_keys"] == ["params", "target_id", "target_kind"]
    assert projected["replacement_previous_payload_keys"] == ["params", "target_id", "target_kind"]
    assert projected["replacement_changed_keys"] == ["params"]


def test_approval_projection_preserves_gate_task_identity(tmp_path: Path) -> None:
    from francis.governance.approval_projection import approval_projection_fields

    task_root = tmp_path / "tasks"
    approval_id = "approval_task_identity"
    operation_id = "tsk_approval_task_identity"
    task_path = task_root / operation_id / "record.json"
    _write_json(
        task_path,
        {
            "task_id": operation_id,
            "status": "pending",
            "capability": "plugin.run",
            "inputs": {
                "mission_id": "mission_task_identity",
                "meta": {
                    "approval_id": approval_id,
                    "trace_id": "trace_task_identity",
                    "advance_action": "run_linked_operation",
                },
            },
            "result": {
                "data": {
                    "status": "needs_approval",
                    "governance": {
                        "gate": "approvals_gate",
                        "next_step": "approve_exact_action",
                    },
                }
            },
        },
    )

    projected = approval_projection_fields({"id": approval_id, "payload": {}}, task_root=task_root)

    assert projected["operation_id"] == operation_id
    assert projected["operation_name"] == "plugin.run"
    assert projected["operation_plane"] == "P3_GOVERNANCE"
    assert projected["advance_action"] == "run_linked_operation"
    assert projected["mission_id"] == "mission_task_identity"
    assert projected["trace_id"] == "trace_task_identity"
    assert projected["gate"] == "approvals_gate"

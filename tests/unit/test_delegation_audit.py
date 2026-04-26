from __future__ import annotations

from pathlib import Path


def test_create_delegation_records_bounded_audit_context(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from francis.agent.delegation import DelegationRequest, create_delegation, read_audit

    record, err = create_delegation(
        DelegationRequest(
            requester_id="operator.stage3",
            capability="plan.create",
            objective="Create a bounded audit context",
            inputs={
                "goal": "Inspect the delegation receipt",
                "mission_id": "msn_audit_context",
                "secret_value": "password=delegationauditsecret123",
            },
            priority=7,
            ttl_sec=900,
        )
    )

    assert err is None
    assert record is not None

    audit = read_audit(record.task_id)
    created = next(item for item in audit if item.get("event") == "created")
    details = created["details"]
    assert details["status"] == "pending"
    assert details["capability"] == "plan.create"
    assert details["requester_id"] == "operator.stage3"
    assert details["priority"] == 7
    assert details["ttl_sec"] == 900
    assert details["mission_id"] == "msn_audit_context"
    assert details["input_key_count"] == 3
    assert "secret_value" not in details
    assert "delegationauditsecret123" not in (data_root / "tasks" / record.task_id / "audit.log").read_text(
        encoding="utf-8"
    )

from __future__ import annotations

from pathlib import Path

import pytest

import francis.managed_copies as managed_copies


RUNTIME_EVIDENCE_SLOTS = {
    "stage17_closure_receipt": (
        "ledger_closure_receipt",
        "/managed-copies/status",
        "stage17_ledger_closure_backstop",
    ),
    "copy_creation_runtime_proof": (
        "managed_copy_creation_runtime_receipt",
        "/managed-copies/copy-creation-contract",
        "copy_creation_contract",
    ),
    "tenant_isolation_runtime_proof": (
        "tenant_isolation_runtime_receipt",
        "/managed-copies/isolation-rules-contract",
        "isolation_rules_contract",
    ),
    "safe_delta_runtime_proof": (
        "safe_delta_runtime_receipt",
        "/managed-copies/safe-delta-model-contract",
        "safe_delta_model_contract",
    ),
    "rogue_recovery_runtime_proof": (
        "rogue_recovery_runtime_receipt",
        "/managed-copies/rogue-recovery-contract",
        "rogue_recovery_contract",
    ),
    "sla_runtime_proof": (
        "sla_runtime_receipt",
        "/managed-copies/sla-framework-contract",
        "sla_framework_contract",
    ),
    "role_authority_runtime_proof": (
        "managed_copy_role_authority_receipt",
        "/managed-copies/roles-contract",
        "roles_contract",
    ),
    "decommission_runtime_proof": (
        "decommission_runtime_receipt",
        "/managed-copies/decommission-contract",
        "decommission_contract",
    ),
}


def _checks(*, ready_ids: set[str]) -> list[dict[str, object]]:
    return [
        {
            "id": requirement_id,
            "passed": requirement_id in ready_ids,
            "receipt_ready": requirement_id in ready_ids,
            "receipt_id": f"receipt-{requirement_id}" if requirement_id in ready_ids else "",
            "proof_kind": proof_kind,
            "source_contract_route": route,
            "blocker": "" if requirement_id in ready_ids else f"{requirement_id}_missing",
        }
        for requirement_id, (proof_kind, route, _) in RUNTIME_EVIDENCE_SLOTS.items()
    ]


def _readback(checks: list[dict[str, object]]) -> dict[str, object]:
    ready_count = sum(1 for item in checks if item.get("passed") is True)
    return {
        "status": "partial" if ready_count else "empty",
        "count": ready_count,
        "ready_count": ready_count,
        "required_count": 8,
        "runtime_evidence_readback_ready": ready_count == 8,
        "missing_evidence": [item["id"] for item in checks if item.get("passed") is not True],
        "checks": checks,
    }


def test_completion_review_uses_canonical_runtime_evidence_slots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    runtime_ready_ids = set(RUNTIME_EVIDENCE_SLOTS) - {"stage17_closure_receipt"}
    checks = _checks(ready_ids=runtime_ready_ids)
    monkeypatch.setattr(
        managed_copies,
        "managed_copy_runtime_evidence_readbacks_snapshot",
        lambda: _readback(checks),
    )

    body = managed_copies.managed_copy_completion_review_snapshot()

    check_by_id = {item["id"]: item for item in body["checks"]}
    for requirement_id, (_, _, completion_check_id) in RUNTIME_EVIDENCE_SLOTS.items():
        check = check_by_id[completion_check_id]
        expected_ready = requirement_id in runtime_ready_ids
        assert check["runtime_ready"] is expected_ready
        assert check["runtime_evidence_requirement_id"] == requirement_id
        assert bool(check["runtime_evidence_receipt_id"]) is expected_ready
    assert body["runtime_ready_count"] == 7
    assert body["ready_to_close"] is False
    assert body["next_smallest_truthful_gap"] == "stage17_operator_stage_closure_decision"
    assert not data_root.exists()


def test_completion_review_rejects_malformed_runtime_evidence_projection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "francis_data"))
    valid = _checks(ready_ids={"copy_creation_runtime_proof"})
    malformed_sets = [
        valid[:-1],
        [*valid[:-1], valid[0]],
        [{**item, "receipt_id": ""} if item["id"] == "copy_creation_runtime_proof" else item for item in valid],
        [{**item, "receipt_ready": False} if item["id"] == "copy_creation_runtime_proof" else item for item in valid],
        [{**item, "proof_kind": "wrong"} if item["id"] == "copy_creation_runtime_proof" else item for item in valid],
        [
            {**item, "source_contract_route": "/wrong"} if item["id"] == "copy_creation_runtime_proof" else item
            for item in valid
        ],
        [
            {**item, "receipt_id": "receipt-evidence" + chr(0xE9)}
            if item["id"] == "copy_creation_runtime_proof"
            else item
            for item in valid
        ],
        [
            {**item, "receipt_id": "receipt/evidence"} if item["id"] == "copy_creation_runtime_proof" else item
            for item in valid
        ],
        [{**item, "receipt_id": 1} if item["id"] == "copy_creation_runtime_proof" else item for item in valid],
        [{**item, "receipt_id": "r" * 241} if item["id"] == "copy_creation_runtime_proof" else item for item in valid],
    ]

    for checks in malformed_sets:
        monkeypatch.setattr(
            managed_copies,
            "managed_copy_runtime_evidence_readbacks_snapshot",
            lambda checks=checks: _readback(checks),
        )
        body = managed_copies.managed_copy_completion_review_snapshot()
        copy_check = next(item for item in body["checks"] if item["id"] == "copy_creation_contract")
        assert copy_check["runtime_ready"] is False
        assert copy_check["runtime_evidence_receipt_id"] == ""
        assert body["ready_to_close"] is False

from __future__ import annotations

import json

import pytest

from francis import managed_copy_rogue_recovery_plan as recovery_plan


def _payload() -> dict[str, object]:
    return {
        "request_actor": "stage18.recovery-planner",
        "copy_id": "managed-copy-001",
        "provisioning_receipt_id": "provision-001",
        "isolation_verification_receipt_id": "isolation-001",
        "integrity_evidence_receipt_id": "integrity-evidence-001",
        "integrity_evidence_fingerprint": "a" * 64,
        "disposition_receipt_id": "containment-disposition-001",
        "disposition_fingerprint": "b" * 64,
        "replacement_source": "clean_core_baseline",
        "recovery_intent_fingerprint": "c" * 64,
        "dry_run": True,
    }


@pytest.fixture(autouse=True)
def owned_lineage(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _payload()
    monkeypatch.setattr(
        recovery_plan,
        "managed_copy_provision_for_copy",
        lambda *args, **kwargs: {
            "copy_id": payload["copy_id"],
            "receipt_id": payload["provisioning_receipt_id"],
            "tenant_key": "d" * 64,
            "provision_fingerprint": "e" * 64,
        },
    )
    monkeypatch.setattr(
        recovery_plan,
        "latest_managed_copy_isolation_verification_for_provision",
        lambda *args, **kwargs: {
            "receipt_id": payload["isolation_verification_receipt_id"],
            "verification_fingerprint": "f" * 64,
            "live_state_aligned": True,
        },
    )
    monkeypatch.setattr(
        recovery_plan,
        "managed_copy_integrity_evidence_readback",
        lambda **kwargs: {
            "latest_receipt_id": payload["integrity_evidence_receipt_id"],
            "latest_evidence_fingerprint": payload["integrity_evidence_fingerprint"],
            "live_drift_matches_latest": True,
            "items": [
                {
                    "receipt_id": payload["integrity_evidence_receipt_id"],
                    "evidence_fingerprint": payload["integrity_evidence_fingerprint"],
                    "scan_fingerprint": "1" * 64,
                }
            ],
        },
    )
    monkeypatch.setattr(
        recovery_plan,
        "managed_copy_integrity_triage_dispositions_readback",
        lambda **kwargs: {
            "ok": True,
            "latest_receipt_id": payload["disposition_receipt_id"],
            "latest_disposition_fingerprint": payload["disposition_fingerprint"],
            "latest_disposition": "containment_authorization_required",
            "items": [
                {
                    "receipt_id": payload["disposition_receipt_id"],
                    "disposition_fingerprint": payload["disposition_fingerprint"],
                    "integrity_evidence_receipt_id": payload["integrity_evidence_receipt_id"],
                    "integrity_evidence_fingerprint": payload["integrity_evidence_fingerprint"],
                }
            ],
        },
    )


def test_current_evidence_and_containment_disposition_produce_read_only_plan() -> None:
    result = recovery_plan.managed_copy_rogue_recovery_plan(_payload(), actor="stage18.recovery-planner")

    assert result["ok"] is True
    assert result["status"] == "ready_for_operator_review"
    assert len(result["plan_fingerprint"]) == 64
    assert result["step_count"] == 7
    assert result["steps"][0] == {"id": "halt", "status": "operator_approval_required"}
    assert result["next_operator_boundary"] == "approve_exact_managed_copy_runtime_halt_action"
    assert result["runtime_gate_ready"] is False
    for flag in (
        "halts_copy",
        "quarantines_copy",
        "preserves_evidence",
        "replaces_copy",
        "restores_copy",
        "writes_receipt",
        "writes_tenant_state",
        "grants_execution_authority",
        "grants_mutation_authority",
    ):
        assert result[flag] is False


@pytest.mark.parametrize(
    ("change", "blocker"),
    [
        ({"request_actor": "wrong.actor"}, "rogue_recovery_plan_actor_lineage_mismatch"),
        ({"dry_run": False}, "rogue_recovery_plan_dry_run_true_required"),
        ({"dry_run": 1}, "rogue_recovery_plan_dry_run_true_required"),
        ({"replacement_source": "caller_path"}, "rogue_recovery_plan_replacement_source_invalid"),
        ({"recovery_intent_fingerprint": "bad"}, "rogue_recovery_plan_recovery_intent_fingerprint_invalid"),
        ({"copy_id": "../../tenant-secret"}, "rogue_recovery_plan_copy_id_invalid"),
        ({"disposition_receipt_id": "password:secret"}, "rogue_recovery_plan_disposition_receipt_id_invalid"),
        ({"raw_incident": "secret"}, "rogue_recovery_plan_payload_schema_invalid"),
    ],
)
def test_schema_actor_and_fixed_replacement_contract_fail_closed(change: dict[str, object], blocker: str) -> None:
    payload = _payload()
    payload.update(change)

    result = recovery_plan.managed_copy_rogue_recovery_plan(payload, actor="stage18.recovery-planner")

    assert result["ok"] is False
    assert blocker in result["blockers"]
    assert result["plan_fingerprint"] == ""
    assert "secret" not in json.dumps(result)


def test_stale_integrity_evidence_blocks_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        recovery_plan,
        "managed_copy_integrity_evidence_readback",
        lambda **kwargs: {
            "latest_receipt_id": _payload()["integrity_evidence_receipt_id"],
            "latest_evidence_fingerprint": _payload()["integrity_evidence_fingerprint"],
            "live_drift_matches_latest": False,
            "items": [],
        },
    )

    result = recovery_plan.managed_copy_rogue_recovery_plan(_payload(), actor="stage18.recovery-planner")

    assert result["ok"] is False
    assert "rogue_recovery_plan_current_integrity_evidence_required" in result["blockers"]


def test_static_denial_occurs_before_owned_lineage_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected_read(*args: object, **kwargs: object) -> dict[str, object]:
        raise AssertionError("owned lineage must not be read for malformed payload")

    monkeypatch.setattr(recovery_plan, "managed_copy_provision_for_copy", unexpected_read)
    payload = _payload()
    payload["copy_id"] = "../../tenant-secret"

    result = recovery_plan.managed_copy_rogue_recovery_plan(payload, actor="stage18.recovery-planner")

    assert result["ok"] is False
    assert result["copy_id"] == ""
    assert result["operator_approval_required"] is False


@pytest.mark.parametrize("disposition", ["investigation_required", "no_rogue_determination"])
def test_non_containment_disposition_blocks_plan(monkeypatch: pytest.MonkeyPatch, disposition: str) -> None:
    monkeypatch.setattr(
        recovery_plan,
        "managed_copy_integrity_triage_dispositions_readback",
        lambda **kwargs: {
            "ok": True,
            "latest_receipt_id": _payload()["disposition_receipt_id"],
            "latest_disposition_fingerprint": _payload()["disposition_fingerprint"],
            "latest_disposition": disposition,
            "items": [],
        },
    )

    result = recovery_plan.managed_copy_rogue_recovery_plan(_payload(), actor="stage18.recovery-planner")

    assert result["ok"] is False
    assert "rogue_recovery_plan_containment_disposition_required" in result["blockers"]


def test_plan_fingerprint_changes_with_replacement_source() -> None:
    first = recovery_plan.managed_copy_rogue_recovery_plan(_payload(), actor="stage18.recovery-planner")
    changed = _payload()
    changed["replacement_source"] = "trusted_known_good_snapshot"
    second = recovery_plan.managed_copy_rogue_recovery_plan(changed, actor="stage18.recovery-planner")

    assert first["plan_fingerprint"] != second["plan_fingerprint"]

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from francis import managed_copy_rogue_recovery_runtime_evidence as recovery_evidence
from francis import managed_copy_runtime_evidence as runtime_evidence


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _fingerprint(value: dict[str, Any]) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _source() -> dict[str, Any]:
    source: dict[str, Any] = {
        "kind": recovery_evidence.ROGUE_RECOVERY_RUNTIME_SOURCE_KIND,
        "contract": recovery_evidence.ROGUE_RECOVERY_RUNTIME_SOURCE_CONTRACT,
        "receipt_id": "rogue-recovery-runtime-source-001",
        "status": "recovered",
        "evidence_class": "canonical_runtime",
        "actor": "stage18.test-writer",
        "tenant_key": _hash("tenant"),
        "copy_id": "managed-copy-001",
        "provisioning_receipt_id": "provision-001",
        "provisioning_receipt_fingerprint": _hash("provision"),
        "isolation_verification_receipt_id": "isolation-001",
        "isolation_verification_receipt_fingerprint": _hash("isolation"),
        "integrity_evidence_receipt_id": "integrity-evidence-001",
        "integrity_evidence_fingerprint": _hash("integrity-evidence"),
        "rogue_detection_assessment_receipt_id": "rogue-assessment-001",
        "rogue_detection_assessment_receipt_fingerprint": _hash("rogue-assessment"),
        "disposition_receipt_id": "disposition-001",
        "disposition_fingerprint": _hash("disposition"),
        "replacement_source": "clean_core_baseline",
        "recovery_intent_fingerprint": _hash("recovery-intent"),
        "recovery_plan_fingerprint": _hash("recovery-plan"),
        "runtime_halt_receipt_id": "runtime-halt-001",
        "runtime_halt_receipt_fingerprint": _hash("runtime-halt"),
        "quarantine_receipt_id": "quarantine-001",
        "quarantine_receipt_fingerprint": _hash("quarantine"),
        "evidence_preservation_receipt_id": "evidence-preservation-001",
        "evidence_preservation_receipt_fingerprint": _hash("evidence-preservation"),
        "support_review_receipt_id": "support-review-001",
        "support_review_receipt_fingerprint": _hash("support-review"),
        "replacement_receipt_id": "replacement-001",
        "replacement_receipt_fingerprint": _hash("replacement"),
        "replacement_verification_receipt_id": "replacement-verification-001",
        "replacement_verification_receipt_fingerprint": _hash("replacement-verification"),
        "continuity_restore_receipt_id": "continuity-restore-001",
        "continuity_restore_receipt_fingerprint": _hash("continuity-restore"),
        "trace_id": "trace-rogue-recovery-runtime-001",
        "fixture_only": False,
        "runtime_gate_ready": True,
        "recorded_at_unix_ms": 1_800_000_000_000,
        "receipt_fingerprint": "",
    }
    source["receipt_fingerprint"] = _fingerprint(
        {key: value for key, value in source.items() if key != "receipt_fingerprint"}
    )
    return source


def _write_source(root: Path, source: dict[str, Any]) -> Path:
    directory = root / "logs" / "managed_copies" / "rogue_recovery_runtime"
    directory.mkdir(parents=True)
    path = directory / f"{source['receipt_id']}.json"
    path.write_text(json.dumps(source), encoding="utf-8")
    return path


@pytest.fixture
def isolated_data(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    root = tmp_path / "francis-data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(root))
    return root


def test_missing_source_fails_without_creating_state(isolated_data: Path) -> None:
    result = recovery_evidence.verify_rogue_recovery_runtime_source("missing-source", _hash("missing"))

    assert result["valid"] is False
    assert result["blocker"] == recovery_evidence.ROGUE_RECOVERY_RUNTIME_SOURCE_MISSING
    assert not isolated_data.exists()


@pytest.mark.parametrize(
    ("receipt_id", "fingerprint"),
    [
        ("../outside", _hash("missing")),
        ("missing-source", "not-a-hash"),
    ],
)
def test_invalid_binding_fails_before_filesystem_read(
    isolated_data: Path,
    receipt_id: str,
    fingerprint: str,
) -> None:
    result = recovery_evidence.verify_rogue_recovery_runtime_source(receipt_id, fingerprint)

    assert result["blocker"] == "stage18_rogue_recovery_runtime_source_binding_invalid"
    assert not isolated_data.exists()


def test_self_consistent_source_cannot_replace_owned_provision_lineage(isolated_data: Path) -> None:
    source = _source()
    _write_source(isolated_data, source)

    result = recovery_evidence.verify_rogue_recovery_runtime_source(source["receipt_id"], source["receipt_fingerprint"])

    assert result["valid"] is False
    assert result["blocker"] == "stage18_rogue_recovery_runtime_provisioning_lineage_invalid"


def test_source_hash_mismatch_fails_before_owned_lineage_read(isolated_data: Path) -> None:
    source = _source()
    _write_source(isolated_data, source)

    result = recovery_evidence.verify_rogue_recovery_runtime_source(source["receipt_id"], _hash("wrong-source"))

    assert result["blocker"] == "stage18_rogue_recovery_runtime_source_receipt_hash_mismatch"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("fixture_only", True),
        ("runtime_gate_ready", False),
        ("recorded_at_unix_ms", True),
        ("status", "planned"),
        ("replacement_source", "caller_selected_snapshot"),
        ("unexpected", "injected"),
    ],
)
def test_malformed_fixture_weaker_and_injected_sources_fail_exact_schema(
    isolated_data: Path,
    field: str,
    value: object,
) -> None:
    source = _source()
    source[field] = value
    source["receipt_fingerprint"] = _fingerprint(
        {key: item for key, item in source.items() if key != "receipt_fingerprint"}
    )
    _write_source(isolated_data, source)

    result = recovery_evidence.verify_rogue_recovery_runtime_source(source["receipt_id"], source["receipt_fingerprint"])

    assert result["valid"] is False
    assert result["blocker"] == "stage18_rogue_recovery_runtime_source_receipt_invalid"


def test_current_preflight_lineage_stops_at_missing_runtime_halt_producer(
    isolated_data: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source()
    _write_source(isolated_data, source)
    monkeypatch.setattr(
        "francis.managed_copy_provisioning.managed_copy_provision_for_copy",
        lambda *args, **kwargs: {
            "tenant_key": source["tenant_key"],
            "provision_fingerprint": source["provisioning_receipt_fingerprint"],
        },
    )
    monkeypatch.setattr(
        "francis.managed_copy_isolation.latest_managed_copy_isolation_verification_for_provision",
        lambda *args, **kwargs: {
            "receipt_id": source["isolation_verification_receipt_id"],
            "verification_fingerprint": source["isolation_verification_receipt_fingerprint"],
            "live_state_aligned": True,
        },
    )
    evidence_item = {
        "receipt_id": source["integrity_evidence_receipt_id"],
        "evidence_fingerprint": source["integrity_evidence_fingerprint"],
    }
    evidence_readback = {
        "live_drift_matches_latest": True,
        "latest_receipt_id": source["integrity_evidence_receipt_id"],
        "latest_evidence_fingerprint": source["integrity_evidence_fingerprint"],
        "items": [evidence_item],
    }
    monkeypatch.setattr(
        "francis.managed_copy_integrity_evidence.managed_copy_integrity_evidence_readback",
        lambda **kwargs: evidence_readback,
    )
    monkeypatch.setattr(
        "francis.managed_copy_rogue_detection_assessment.managed_copy_rogue_detection_assessments_readback",
        lambda **kwargs: {
            "rogue_signal_assessed": True,
            "items": [
                {
                    "receipt_id": source["rogue_detection_assessment_receipt_id"],
                    "receipt_fingerprint": source["rogue_detection_assessment_receipt_fingerprint"],
                    "evidence_reference_hashes": [source["integrity_evidence_fingerprint"]],
                }
            ],
        },
    )
    disposition_item = {
        "receipt_id": source["disposition_receipt_id"],
        "disposition_fingerprint": source["disposition_fingerprint"],
        "integrity_evidence_receipt_id": source["integrity_evidence_receipt_id"],
        "integrity_evidence_fingerprint": source["integrity_evidence_fingerprint"],
    }
    disposition_readback = {
        "ok": True,
        "latest_receipt_id": source["disposition_receipt_id"],
        "latest_disposition_fingerprint": source["disposition_fingerprint"],
        "latest_disposition": "containment_authorization_required",
        "items": [disposition_item],
    }
    monkeypatch.setattr(
        "francis.managed_copy_integrity_triage_disposition.managed_copy_integrity_triage_dispositions_readback",
        lambda **kwargs: disposition_readback,
    )
    monkeypatch.setattr(
        "francis.managed_copy_rogue_recovery_plan.managed_copy_rogue_recovery_plan",
        lambda *args, **kwargs: {"ok": True, "plan_fingerprint": source["recovery_plan_fingerprint"]},
    )

    result = recovery_evidence.verify_rogue_recovery_runtime_source(source["receipt_id"], source["receipt_fingerprint"])

    assert result["valid"] is False
    assert result["blocker"] == "stage18_rogue_recovery_runtime_halt_receipt_not_implemented"


def test_superseded_rogue_assessment_cannot_satisfy_current_lineage(
    isolated_data: Path,
) -> None:
    source = _source()
    _write_source(isolated_data, source)
    matching = {
        "receipt_id": source["rogue_detection_assessment_receipt_id"],
        "receipt_fingerprint": source["rogue_detection_assessment_receipt_fingerprint"],
        "evidence_reference_hashes": [source["integrity_evidence_fingerprint"]],
    }
    superseding = {
        "receipt_id": "rogue-assessment-002",
        "receipt_fingerprint": _hash("rogue-assessment-002"),
        "evidence_reference_hashes": [source["integrity_evidence_fingerprint"]],
    }

    assessments = {"rogue_signal_assessed": True, "items": [matching, superseding]}

    assert recovery_evidence._assessment_lineage_current(source, assessments) is False
    assessments["items"] = [superseding, matching]
    assert recovery_evidence._assessment_lineage_current(source, assessments) is True


def test_runtime_recorder_selects_rogue_recovery_verifier_and_proof_kind(isolated_data: Path) -> None:
    payload = {
        "request_actor": "stage18.test-writer",
        "requirement_id": runtime_evidence.ROGUE_RECOVERY_REQUIREMENT,
        "proof_kind": runtime_evidence.ROGUE_RECOVERY_PROOF_KIND,
        "source_receipt_id": "rogue-recovery-source",
        "source_receipt_fingerprint": _hash("source"),
        "trace_id": "trace-stage18-rogue-recovery",
        "dry_run": True,
        "record_fingerprint": "",
        "confirm_runtime_evidence": False,
    }
    result = runtime_evidence.plan_runtime_evidence(
        payload,
        actor="stage18.test-writer",
        stage17_closed=True,
    )

    assert result["ok"] is False
    assert result["error"] == recovery_evidence.ROGUE_RECOVERY_RUNTIME_SOURCE_MISSING
    assert not isolated_data.exists()


def test_rogue_recovery_requirement_rejects_other_proof_kind(isolated_data: Path) -> None:
    payload = {
        "request_actor": "stage18.test-writer",
        "requirement_id": runtime_evidence.ROGUE_RECOVERY_REQUIREMENT,
        "proof_kind": runtime_evidence.COPY_CREATION_PROOF_KIND,
        "source_receipt_id": "rogue-recovery-source",
        "source_receipt_fingerprint": _hash("source"),
        "trace_id": "trace-stage18-rogue-recovery",
        "dry_run": True,
        "record_fingerprint": "",
        "confirm_runtime_evidence": False,
    }
    result = runtime_evidence.plan_runtime_evidence(
        payload,
        actor="stage18.test-writer",
        stage17_closed=True,
    )

    assert result["error"] == "stage18_runtime_evidence_proof_kind_mismatch"
    assert not isolated_data.exists()

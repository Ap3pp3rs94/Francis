from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from francis import managed_copy_runtime_evidence as runtime_evidence
from francis import managed_copy_safe_delta_runtime_evidence as safe_delta_evidence


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _fingerprint(value: dict[str, Any]) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _source() -> dict[str, Any]:
    source: dict[str, Any] = {
        "kind": safe_delta_evidence.SAFE_DELTA_RUNTIME_SOURCE_KIND,
        "contract": safe_delta_evidence.SAFE_DELTA_RUNTIME_SOURCE_CONTRACT,
        "receipt_id": "safe-delta-runtime-source-001",
        "status": "exported",
        "evidence_class": "canonical_runtime",
        "actor": "stage18.test-writer",
        "tenant_key": _hash("tenant"),
        "copy_id": "managed-copy-001",
        "provisioning_receipt_id": "provision-001",
        "provisioning_receipt_fingerprint": _hash("provision"),
        "isolation_verification_receipt_id": "isolation-001",
        "isolation_verification_receipt_fingerprint": _hash("isolation"),
        "review_receipt_id": "review-001",
        "review_receipt_fingerprint": _hash("review-receipt"),
        "review_fingerprint": _hash("review"),
        "safe_delta_decision_receipt_id": "safe-delta-decision-001",
        "safe_delta_decision_receipt_fingerprint": _hash("safe-delta-decision"),
        "export_authorization_decision_receipt_id": "export-authorization-001",
        "export_authorization_decision_receipt_fingerprint": _hash("export-authorization"),
        "artifact_plan_fingerprint": _hash("artifact-plan"),
        "export_artifact_receipt_id": "export-artifact-001",
        "export_artifact_receipt_fingerprint": _hash("export-artifact"),
        "artifact_content_fingerprint": _hash("artifact-content"),
        "runtime_invocation_receipt_id": "runtime-invocation-001",
        "runtime_invocation_receipt_fingerprint": _hash("runtime-invocation-receipt"),
        "runtime_invocation_fingerprint": _hash("runtime-invocation"),
        "runtime_invocation_result_fingerprint": _hash("runtime-invocation-result"),
        "signal_class": "approved_non_private_signal",
        "trace_id": "trace-safe-delta-runtime-001",
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
    directory = root / "logs" / "managed_copies" / "safe_delta_runtime"
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
    result = safe_delta_evidence.verify_safe_delta_runtime_source("missing-source", _hash("missing"))

    assert result["valid"] is False
    assert result["blocker"] == safe_delta_evidence.SAFE_DELTA_RUNTIME_SOURCE_MISSING
    assert not isolated_data.exists()


def test_self_consistent_source_cannot_replace_owned_provision_lineage(isolated_data: Path) -> None:
    source = _source()
    _write_source(isolated_data, source)

    result = safe_delta_evidence.verify_safe_delta_runtime_source(source["receipt_id"], source["receipt_fingerprint"])

    assert result["valid"] is False
    assert result["blocker"] == "stage18_safe_delta_runtime_provisioning_lineage_invalid"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("fixture_only", True),
        ("runtime_gate_ready", False),
        ("recorded_at_unix_ms", True),
        ("status", "planned"),
        ("unexpected", "injected"),
    ],
)
def test_malformed_fixture_and_injected_sources_fail_exact_schema(
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

    result = safe_delta_evidence.verify_safe_delta_runtime_source(source["receipt_id"], source["receipt_fingerprint"])

    assert result["valid"] is False
    assert result["blocker"] == "stage18_safe_delta_runtime_source_receipt_invalid"


def test_owned_invocation_lineage_stops_at_canonical_source_recording_boundary(
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
    monkeypatch.setattr(
        "francis.managed_copy_safe_delta.managed_copy_safe_delta_review_receipts_readback",
        lambda **kwargs: {
            "receipt_set_valid": True,
            "latest_valid_receipt": {
                "receipt_id": source["review_receipt_id"],
                "receipt_fingerprint": source["review_receipt_fingerprint"],
                "signal_class": source["signal_class"],
                "live_source_boundary_aligned": True,
            },
        },
    )
    monkeypatch.setattr(
        "francis.managed_copy_safe_delta_approval.managed_copy_safe_delta_decisions_readback",
        lambda **kwargs: {
            "safe_delta_approved": True,
            "latest_valid_receipt": {
                "receipt_id": source["safe_delta_decision_receipt_id"],
                "receipt_fingerprint": source["safe_delta_decision_receipt_fingerprint"],
            },
        },
    )
    monkeypatch.setattr(
        "francis.managed_copy_safe_delta_export_authorization_decision.managed_copy_safe_delta_export_authorization_decisions_readback",
        lambda **kwargs: {
            "items": [
                {
                    "receipt_id": source["export_authorization_decision_receipt_id"],
                    "receipt_fingerprint": source["export_authorization_decision_receipt_fingerprint"],
                    "decision": "approved",
                    "review_fingerprint": source["review_fingerprint"],
                }
            ]
        },
    )
    monkeypatch.setattr(
        "francis.managed_copy_safe_delta_export_artifact.managed_copy_safe_delta_export_artifacts_readback",
        lambda **kwargs: {
            "valid_count": 1,
            "latest_valid_receipt": {
                "receipt_id": source["export_artifact_receipt_id"],
                "receipt_fingerprint": source["export_artifact_receipt_fingerprint"],
                "artifact_content_fingerprint": source["artifact_content_fingerprint"],
                "artifact_plan_fingerprint": source["artifact_plan_fingerprint"],
                "tenant_key": source["tenant_key"],
                "copy_id": source["copy_id"],
                "provisioning_receipt_id": source["provisioning_receipt_id"],
                "isolation_verification_receipt_id": source["isolation_verification_receipt_id"],
                "review_fingerprint": source["review_fingerprint"],
                "authorization_decision_receipt_id": source["export_authorization_decision_receipt_id"],
                "authorization_decision_receipt_fingerprint": source[
                    "export_authorization_decision_receipt_fingerprint"
                ],
            },
        },
    )
    monkeypatch.setattr(
        "francis.managed_copy_safe_delta_runtime_invocation.safe_delta_runtime_invocations_readback",
        lambda **kwargs: {
            "valid_count": 1,
            "latest_valid_receipt": {
                "receipt_id": source["runtime_invocation_receipt_id"],
                "receipt_fingerprint": source["runtime_invocation_receipt_fingerprint"],
                "invocation_fingerprint": source["runtime_invocation_fingerprint"],
                "invocation_result_fingerprint": source["runtime_invocation_result_fingerprint"],
                "export_artifact_receipt_id": source["export_artifact_receipt_id"],
                "export_artifact_receipt_fingerprint": source["export_artifact_receipt_fingerprint"],
                "artifact_content_fingerprint": source["artifact_content_fingerprint"],
                "invocation_result": {
                    "classification": "eligible_for_core_review",
                    "eligible_for_core_review": True,
                },
            },
        },
    )

    result = safe_delta_evidence.verify_safe_delta_runtime_source(source["receipt_id"], source["receipt_fingerprint"])

    assert result["valid"] is False
    assert result["blocker"] == "stage18_safe_delta_runtime_canonical_source_receipt_recording_not_implemented"
    assert result["evidence_class"] == ""
    assert result["current_state_hash"] == ""


def test_owned_artifact_without_exact_invocation_lineage_fails_closed(
    isolated_data: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source()
    _write_source(isolated_data, source)
    monkeypatch.setattr(
        safe_delta_evidence,
        "_owned_lineage_blocker",
        lambda item: "stage18_safe_delta_runtime_invocation_lineage_invalid",
    )

    result = safe_delta_evidence.verify_safe_delta_runtime_source(
        source["receipt_id"],
        source["receipt_fingerprint"],
    )

    assert result["valid"] is False
    assert result["blocker"] == "stage18_safe_delta_runtime_invocation_lineage_invalid"


def test_runtime_recorder_selects_safe_delta_verifier_and_proof_kind(isolated_data: Path) -> None:
    payload = {
        "request_actor": "stage18.test-writer",
        "requirement_id": runtime_evidence.SAFE_DELTA_REQUIREMENT,
        "proof_kind": runtime_evidence.SAFE_DELTA_PROOF_KIND,
        "source_receipt_id": "safe-delta-source",
        "source_receipt_fingerprint": _hash("source"),
        "trace_id": "trace-stage18-safe-delta",
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
    assert result["error"] == safe_delta_evidence.SAFE_DELTA_RUNTIME_SOURCE_MISSING
    assert not isolated_data.exists()


def test_safe_delta_requirement_rejects_other_proof_kind(isolated_data: Path) -> None:
    payload = {
        "request_actor": "stage18.test-writer",
        "requirement_id": runtime_evidence.SAFE_DELTA_REQUIREMENT,
        "proof_kind": runtime_evidence.COPY_CREATION_PROOF_KIND,
        "source_receipt_id": "safe-delta-source",
        "source_receipt_fingerprint": _hash("source"),
        "trace_id": "trace-stage18-safe-delta",
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

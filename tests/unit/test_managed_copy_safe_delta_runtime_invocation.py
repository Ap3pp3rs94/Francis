from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from francis import managed_copy_safe_delta_runtime_invocation as invocation
from francis import managed_copy_pilot_runtime
from francis.api.app import create_app
from francis.governance.pilot_scope_lease import PilotScopeLease, PilotScopeLeaseRegistry


def _hash(character: str) -> str:
    return character * 64


def _artifact(*, abstraction_level: str = "metadata_only") -> dict[str, Any]:
    return {
        "kind": "francis.stage18.managed_copies.safe_delta_export_artifact",
        "contract": "stage18_managed_copy_safe_delta_export_artifact_v2",
        "artifact_media_type": "application/vnd.francis.safe-delta+json",
        "artifact_schema_class": "safe_delta_signal_v1",
        "signal_class": "approved_non_private_signal",
        "candidate": {
            "signal_fingerprint": _hash("1"),
            "summary_fingerprint": _hash("2"),
            "lineage_fingerprint": _hash("3"),
            "source_record_count": 7,
            "contains_raw_private_data": False,
            "contains_tenant_identifiers": False,
            "redaction_review_complete": True,
            "abstraction_level": abstraction_level,
            "retention_class": "review_receipt_only",
        },
        "review_fingerprint": _hash("4"),
        "authorization_decision_fingerprint": _hash("5"),
        "artifact_plan_fingerprint": _hash("6"),
    }


def _lineage(*, abstraction_level: str = "metadata_only") -> dict[str, Any]:
    return {
        "tenant_key": _hash("a"),
        "provision": {"provision_fingerprint": _hash("b")},
        "isolation": {"verification_fingerprint": _hash("c")},
        "provisioning_receipt_fingerprint": _hash("b"),
        "isolation_verification_receipt_fingerprint": _hash("c"),
        "export_artifact_receipt": {
            "receipt_id": "export-artifact-001",
            "receipt_fingerprint": _hash("d"),
            "artifact_content_fingerprint": _hash("e"),
        },
        "artifact": _artifact(abstraction_level=abstraction_level),
    }


def _payload(**updates: Any) -> dict[str, Any]:
    payload = {
        "request_actor": "stage18.safe-delta-invoker",
        "copy_id": "managed-copy-001",
        "provisioning_receipt_id": "provision-001",
        "isolation_verification_receipt_id": "isolation-001",
        "artifact_plan_fingerprint": _hash("6"),
        "export_artifact_receipt_id": "export-artifact-001",
        "export_artifact_receipt_fingerprint": _hash("d"),
        "artifact_content_fingerprint": _hash("e"),
        "pilot_lease_id": "lease-safe-delta-001",
        "package_id": "package-safe-delta-001",
        "pilot_run_id": "run-safe-delta-001",
        "trace_id": "trace-safe-delta-001",
        "dry_run": True,
        "invocation_fingerprint": "",
        "confirm_runtime_invocation": False,
    }
    payload.update(updates)
    return payload


def _authority() -> dict[str, Any]:
    return {
        "valid": True,
        "actor_id": "stage18.safe-delta-invoker",
        "lease_id": "lease-safe-delta-001",
        "package_id": "package-safe-delta-001",
        "package_fingerprint": _hash("7"),
        "pilot_run_id": "run-safe-delta-001",
        "operator_decision_fingerprint": _hash("8"),
        "effective_state": "active",
        "consumed_binding_count": 1,
        "operation_consumed_binding_count": 1,
        "lease_authority_fingerprint": _hash("9"),
        "consumed_prefix_fingerprints": [_hash("9")],
    }


@pytest.fixture
def stubbed_lineage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    receipt_directory = tmp_path / "tenant-receipts" / "zi"
    monkeypatch.setattr(invocation, "_load_artifact_lineage", lambda request: (_lineage(), ""))
    monkeypatch.setattr(invocation, "_reload_authority", lambda plan: _authority())
    monkeypatch.setattr(
        invocation,
        "_receipt_directory",
        lambda lineage, *, create: _directory(receipt_directory, create=create),
    )
    return receipt_directory


def _directory(path: Path, *, create: bool) -> Path | None:
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path if path.is_dir() else None


def _plan(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return invocation.plan_safe_delta_runtime_invocation(
        payload or _payload(),
        actor="stage18.safe-delta-invoker",
    )


def test_plan_evaluates_eligible_metadata_only_artifact(stubbed_lineage: Path) -> None:
    plan = _plan()

    assert plan["ok"] is True
    assert plan["invocation_result"] == {
        "operation": "evaluate_core_review_handoff",
        "classification": invocation.ELIGIBLE,
        "eligible_for_core_review": True,
        "reason_codes": [],
        "source_record_count": 7,
        "abstraction_level": "metadata_only",
        "retention_class": "review_receipt_only",
    }
    assert plan["writes_receipt"] is False
    assert not stubbed_lineage.exists()


def test_plan_returns_deterministic_ineligible_reasons(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        invocation,
        "_load_artifact_lineage",
        lambda request: (_lineage(abstraction_level="aggregate"), ""),
    )

    first = _plan()
    second = _plan()

    assert first["ok"] is True
    assert first["invocation_result"]["classification"] == invocation.INELIGIBLE
    assert first["invocation_result"]["eligible_for_core_review"] is False
    assert first["invocation_result"]["reason_codes"] == ["abstraction_level_not_metadata_only"]
    assert first["invocation_fingerprint"] == second["invocation_fingerprint"]


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("contains_raw_private_data", True, "raw_private_data_present_or_unknown"),
        ("contains_tenant_identifiers", True, "tenant_identifiers_present_or_unknown"),
        ("redaction_review_complete", False, "redaction_review_incomplete"),
        ("retention_class", "retain_forever", "retention_class_not_review_receipt_only"),
        ("source_record_count", 0, "source_record_count_not_positive_integer"),
        ("source_record_count", True, "source_record_count_not_positive_integer"),
    ],
)
def test_eligibility_uses_exact_types_and_reason_codes(field: str, value: Any, reason: str) -> None:
    artifact = _artifact()
    artifact["candidate"][field] = value

    result = invocation.evaluate_core_review_eligibility(artifact)

    assert result["eligible_for_core_review"] is False
    assert reason in result["reason_codes"]


@pytest.mark.parametrize(
    ("payload_update", "error"),
    [
        ({"unexpected": "injected"}, "safe_delta_runtime_invocation_unknown_fields"),
        ({"request_actor": 1}, "safe_delta_runtime_invocation_actor_lineage_mismatch"),
        ({"dry_run": 1}, "safe_delta_runtime_invocation_dry_run_true_required"),
        ({"artifact_plan_fingerprint": True}, "safe_delta_runtime_invocation_fingerprint_invalid"),
    ],
)
def test_plan_rejects_unknown_malformed_and_boolean_integer_fields(
    stubbed_lineage: Path,
    payload_update: dict[str, Any],
    error: str,
) -> None:
    plan = _plan(_payload(**payload_update))

    assert plan["ok"] is False
    assert error in plan["blockers"]
    assert not stubbed_lineage.exists()


@pytest.mark.parametrize(
    "blocker",
    [
        "safe_delta_runtime_invocation_export_artifact_invalid",
        "safe_delta_runtime_invocation_artifact_tampered_or_drifted",
    ],
)
def test_missing_or_tampered_artifact_fails_without_writes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    blocker: str,
) -> None:
    monkeypatch.setattr(invocation, "_load_artifact_lineage", lambda request: ({}, blocker))

    plan = _plan()

    assert plan["ok"] is False
    assert plan["error"] == blocker
    assert not tmp_path.joinpath("tenant-receipts").exists()


def test_artifact_lineage_is_reloaded_from_guarded_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from francis import managed_copy_safe_delta_export_artifact as export_artifact

    artifact_directory = tmp_path / "artifacts"
    receipt_directory = tmp_path / "receipts"
    artifact_directory.mkdir()
    receipt_directory.mkdir()
    request = _payload()
    receipt = {
        "receipt_id": request["export_artifact_receipt_id"],
        "receipt_fingerprint": request["export_artifact_receipt_fingerprint"],
        "artifact_content_fingerprint": request["artifact_content_fingerprint"],
        "artifact_plan_fingerprint": request["artifact_plan_fingerprint"],
        "artifact_filename": "artifact.json",
    }
    artifact = _artifact()
    (receipt_directory / f"{request['artifact_plan_fingerprint'][:16]}.json").write_text(
        json.dumps(receipt),
        encoding="utf-8",
    )
    (artifact_directory / "artifact.json").write_text(json.dumps(artifact), encoding="utf-8")
    base = _lineage()
    monkeypatch.setattr(invocation, "_base_lineage", lambda current: base)
    monkeypatch.setattr(
        export_artifact,
        "managed_copy_safe_delta_export_artifacts_readback",
        lambda **kwargs: {"valid_count": 1, "latest_valid_receipt": receipt},
    )
    monkeypatch.setattr(
        export_artifact,
        "_owned_paths",
        lambda current, *, create: (
            artifact_directory,
            receipt_directory,
            {"provision_fingerprint": _hash("b")},
            {"verification_fingerprint": _hash("c")},
        ),
    )
    monkeypatch.setattr(export_artifact, "_valid_receipt", lambda *args: True)
    monkeypatch.setattr(export_artifact, "_receipt_matches_artifact", lambda *args: True)
    monkeypatch.setattr(export_artifact, "_live_plan_matches", lambda *args: True)

    loaded, blocker = invocation._load_artifact_lineage(request)

    assert blocker == ""
    assert loaded["artifact"] == artifact
    assert loaded["export_artifact_receipt"] == receipt


def test_confirmed_invocation_writes_one_redacted_immutable_receipt(stubbed_lineage: Path) -> None:
    plan = _plan()

    recorded = invocation.record_safe_delta_runtime_invocation(
        plan,
        provided_fingerprint=plan["invocation_fingerprint"],
        confirmed=True,
        authority=_authority(),
    )

    assert recorded["ok"] is True
    assert recorded["status"] == "runtime_invocation_completed"
    assert recorded["writes_receipt"] is True
    paths = list(stubbed_lineage.glob("*.json"))
    assert len(paths) == 1
    receipt = json.loads(paths[0].read_text(encoding="utf-8"))
    assert set(receipt) == invocation._RECEIPT_FIELDS
    assert receipt["invocation_result"]["eligible_for_core_review"] is True
    assert receipt["governance"] == invocation.GOVERNANCE
    serialized = paths[0].read_text(encoding="utf-8")
    assert "raw_private" not in serialized
    assert "tenant-" not in serialized
    assert "secret" not in serialized


def test_exact_replay_is_idempotent_and_conflict_fails_closed(stubbed_lineage: Path) -> None:
    plan = _plan()
    first = invocation.record_safe_delta_runtime_invocation(
        plan,
        provided_fingerprint=plan["invocation_fingerprint"],
        confirmed=True,
        authority=_authority(),
    )
    replay = invocation.record_safe_delta_runtime_invocation(
        plan,
        provided_fingerprint=plan["invocation_fingerprint"],
        confirmed=True,
        authority=_authority(),
    )
    path = next(stubbed_lineage.glob("*.json"))
    receipt = json.loads(path.read_text(encoding="utf-8"))
    receipt["actor"] = "conflicting-actor"
    receipt["receipt_fingerprint"] = invocation._fingerprint_without(receipt, "receipt_fingerprint")
    path.write_text(json.dumps(receipt), encoding="utf-8")
    conflict = invocation.record_safe_delta_runtime_invocation(
        plan,
        provided_fingerprint=plan["invocation_fingerprint"],
        confirmed=True,
        authority=_authority(),
    )

    assert first["writes_receipt"] is True
    assert replay["status"] == "already_completed"
    assert replay["writes_receipt"] is False
    assert conflict["error"] == "safe_delta_runtime_invocation_conflict"


def test_final_under_lock_revalidation_denies_lineage_drift(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls = 0

    def load(request: dict[str, str]) -> tuple[dict[str, Any], str]:
        nonlocal calls
        calls += 1
        return (_lineage(), "") if calls == 1 else ({}, "safe_delta_runtime_invocation_artifact_tampered_or_drifted")

    monkeypatch.setattr(invocation, "_load_artifact_lineage", load)
    monkeypatch.setattr(invocation, "_reload_authority", lambda plan: _authority())
    monkeypatch.setattr(invocation, "_base_lineage", lambda request: _lineage())
    monkeypatch.setattr(
        invocation,
        "_receipt_directory",
        lambda lineage, *, create: _directory(tmp_path / "zi", create=create),
    )
    plan = _plan()

    result = invocation.record_safe_delta_runtime_invocation(
        plan,
        provided_fingerprint=plan["invocation_fingerprint"],
        confirmed=True,
        authority=_authority(),
    )

    assert result["error"] == "safe_delta_runtime_invocation_lineage_drift"
    assert not tmp_path.joinpath("zi").exists()


def test_post_publication_lineage_drift_quarantines_receipt_and_replay_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls = 0
    receipt_directory = tmp_path / "zi"

    def load(request: dict[str, str]) -> tuple[dict[str, Any], str]:
        nonlocal calls
        calls += 1
        if calls <= 3:
            return _lineage(), ""
        return {}, "safe_delta_runtime_invocation_artifact_tampered_or_drifted"

    monkeypatch.setattr(invocation, "_load_artifact_lineage", load)
    monkeypatch.setattr(invocation, "_reload_authority", lambda plan: _authority())
    monkeypatch.setattr(invocation, "_base_lineage", lambda request: _lineage())
    monkeypatch.setattr(
        invocation,
        "_receipt_directory",
        lambda lineage, *, create: _directory(receipt_directory, create=create),
    )
    plan = _plan()

    result = invocation.record_safe_delta_runtime_invocation(
        plan,
        provided_fingerprint=plan["invocation_fingerprint"],
        confirmed=True,
        authority=_authority(),
    )
    receipt_path = next(receipt_directory.glob("*.json"))
    preserved_bytes = receipt_path.read_bytes()
    readback = invocation.safe_delta_runtime_invocations_readback(
        copy_id="managed-copy-001",
        provisioning_receipt_id="provision-001",
        isolation_verification_receipt_id="isolation-001",
        invocation_fingerprint=plan["invocation_fingerprint"],
    )
    replay = invocation.record_safe_delta_runtime_invocation(
        plan,
        provided_fingerprint=plan["invocation_fingerprint"],
        confirmed=True,
        authority=_authority(),
    )

    assert calls >= 4
    assert result["ok"] is False
    assert result["status"] == "cleanup_required"
    assert result["error"] == "safe_delta_runtime_invocation_post_write_lineage_drift"
    assert result["writes_receipt"] is True
    assert result["quarantined_receipt_preserved"] is True
    assert result["quarantined_receipt_id"]
    assert result["quarantined_receipt_fingerprint"]
    assert result["quarantined_receipt_preservation_status"] == "exact_receipt_preserved"
    assert receipt_path.read_bytes() == preserved_bytes
    assert readback["valid_count"] == 0
    assert replay["ok"] is False
    assert replay["status"] == "blocked"
    assert receipt_path.read_bytes() == preserved_bytes
    assert list(receipt_directory.glob("*.json")) == [receipt_path]


@pytest.mark.parametrize(
    ("published_bytes", "path_exists"),
    [
        (None, False),
        (b'{"different":"receipt"}\n', True),
        (b"{invalid-json", True),
    ],
)
def test_post_write_unverified_observation_does_not_claim_preserved_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    published_bytes: bytes | None,
    path_exists: bool,
) -> None:
    receipt_directory = tmp_path / "zi"
    monkeypatch.setattr(invocation, "_load_artifact_lineage", lambda request: (_lineage(), ""))
    monkeypatch.setattr(invocation, "_reload_authority", lambda plan: _authority())
    monkeypatch.setattr(
        invocation,
        "_receipt_directory",
        lambda lineage, *, create: _directory(receipt_directory, create=create),
    )

    def publish(path: Path, content: bytes) -> None:
        if published_bytes is not None:
            path.write_bytes(published_bytes)

    monkeypatch.setattr(invocation, "_publish_exclusive", publish)
    plan = _plan()

    result = invocation.record_safe_delta_runtime_invocation(
        plan,
        provided_fingerprint=plan["invocation_fingerprint"],
        confirmed=True,
        authority=_authority(),
    )

    assert result["ok"] is False
    assert result["status"] == "cleanup_required"
    assert result["error"] == "safe_delta_runtime_invocation_write_verification_failed_after_publication"
    assert result["writes_receipt"] is False
    assert result["quarantined_receipt_preserved"] is False
    assert result["quarantined_receipt_id"] == ""
    assert result["quarantined_receipt_fingerprint"] == ""
    assert result["quarantined_receipt_preservation_status"] == "preservation_unverified"
    assert bool(list(receipt_directory.glob("*.json"))) is path_exists


def test_unscoped_api_denial_precedes_lineage_and_filesystem_effects(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", "{}")
    monkeypatch.setattr(
        "francis.api.routes.managed_copies.managed_copy_safe_delta_runtime_invocation_snapshot",
        lambda *args, **kwargs: pytest.fail("invocation handler must not run"),
    )

    response = TestClient(create_app()).post(
        "/managed-copies/safe-delta-runtime-invocation",
        json={"request_actor": "unscoped", "unexpected": "secret"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["error"] == "api_permission_denied"
    assert body["required_scope"] == invocation.WRITE_SCOPE
    assert "secret" not in response.text
    assert not tmp_path.joinpath("data").exists()


def test_scoped_api_plan_write_and_readback_round_trip(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    actor = "stage18.safe-delta-invoker"
    receipt_directory = tmp_path / "tenant-receipts" / "zi"
    lineage = _lineage()
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({actor: [invocation.PREFLIGHT_SCOPE, invocation.WRITE_SCOPE]}),
    )
    registry = PilotScopeLeaseRegistry(clock_ms=lambda: 1_000)
    registry.issue(
        PilotScopeLease(
            lease_id="lease-safe-delta-001",
            actor_id=actor,
            package_id="package-safe-delta-001",
            package_fingerprint=_hash("7"),
            pilot_run_id="run-safe-delta-001",
            bindings=invocation.lease_bindings(),
            issued_at_ms=900,
            expires_at_ms=10_000,
            runtime_nonce="runtime-nonce-safe-delta",
            operator_decision_fingerprint=_hash("8"),
        )
    )
    monkeypatch.setattr(managed_copy_pilot_runtime, "PILOT_RUNTIME_LEASES", registry)
    monkeypatch.setattr("francis.api.routes.managed_copies.PILOT_RUNTIME_LEASES", registry)
    monkeypatch.setattr(invocation, "_load_artifact_lineage", lambda request: (lineage, ""))
    monkeypatch.setattr(invocation, "_base_lineage", lambda request: lineage)
    monkeypatch.setattr(
        invocation,
        "_receipt_directory",
        lambda current, *, create: _directory(receipt_directory, create=create),
    )
    client = TestClient(create_app())

    planned = client.post("/managed-copies/safe-delta-runtime-invocation-plan", json=_payload()).json()
    write_payload = _payload(
        dry_run=False,
        invocation_fingerprint=planned["invocation_fingerprint"],
        confirm_runtime_invocation=True,
    )
    recorded = client.post("/managed-copies/safe-delta-runtime-invocation", json=write_payload).json()
    readback = client.get(
        "/managed-copies/safe-delta-runtime-invocation",
        params={
            "copy_id": "managed-copy-001",
            "provisioning_receipt_id": "provision-001",
            "isolation_verification_receipt_id": "isolation-001",
            "invocation_fingerprint": planned["invocation_fingerprint"],
        },
    ).json()

    assert planned["ok"] is True
    assert planned["required_scope"] == invocation.PREFLIGHT_SCOPE
    assert recorded["ok"] is True
    assert recorded["required_scope"] == invocation.WRITE_SCOPE
    assert recorded["writes_receipt"] is True
    assert readback["valid_count"] == 1
    assert readback["latest_valid_receipt"]["receipt_id"] == recorded["receipt_id"]

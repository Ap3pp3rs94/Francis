from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from francis import managed_copy_runtime_evidence as runtime_evidence


def _hash(seed: str) -> str:
    import hashlib

    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _payload(*, requirement_id: str = runtime_evidence.COPY_CREATION_REQUIREMENT) -> dict[str, object]:
    return {
        "request_actor": "stage18.test-writer",
        "requirement_id": requirement_id,
        "proof_kind": runtime_evidence.COPY_CREATION_PROOF_KIND,
        "source_receipt_id": "fixture-runtime-source-1",
        "source_receipt_fingerprint": _hash("source"),
        "trace_id": "trace-stage18-runtime-evidence-test",
        "dry_run": True,
        "record_fingerprint": "",
        "confirm_runtime_evidence": False,
    }


def _fixture_source(_: str, __: str) -> dict[str, object]:
    return {
        "valid": True,
        "blocker": "",
        "evidence_class": "fixture_software_only",
        "source_lineage_hash": _hash("lineage"),
        "current_state_hash": _hash("state"),
    }


def _record_payload() -> dict[str, object]:
    payload = _payload()
    plan = runtime_evidence.plan_runtime_evidence(
        payload,
        actor="stage18.test-writer",
        stage17_closed=True,
        source_verifier=_fixture_source,
    )
    assert plan["ok"] is True
    payload.update(
        dry_run=False,
        record_fingerprint=plan["record_fingerprint"],
        confirm_runtime_evidence=True,
    )
    return payload


@pytest.fixture
def isolated_data(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    root = tmp_path / "francis-data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(root))
    return root


def test_production_source_verifier_fails_closed_without_startup_receipt(isolated_data: Path) -> None:
    result = runtime_evidence.plan_runtime_evidence(
        _payload(),
        actor="stage18.test-writer",
        stage17_closed=True,
    )

    assert result["ok"] is False
    assert result["error"] == runtime_evidence.COPY_CREATION_SOURCE_MISSING
    assert not isolated_data.exists()


@pytest.mark.parametrize("blocker", ["canonical_source_receipt_missing", "canonical_source_hash_mismatch"])
def test_invalid_canonical_source_result_fails_closed(isolated_data: Path, blocker: str) -> None:
    def invalid_source(_: str, __: str) -> dict[str, object]:
        return {
            "valid": False,
            "blocker": blocker,
            "evidence_class": "canonical_runtime",
            "source_lineage_hash": "",
            "current_state_hash": "",
        }

    result = runtime_evidence.plan_runtime_evidence(
        _payload(),
        actor="stage18.test-writer",
        stage17_closed=True,
        source_verifier=invalid_source,
    )

    assert result["ok"] is False
    assert result["error"] == blocker
    assert not isolated_data.exists()


@pytest.mark.parametrize(
    ("change", "error"),
    [
        ({"requirement_id": "unknown"}, "stage18_runtime_evidence_requirement_unknown"),
        (
            {"requirement_id": "sla_runtime_proof"},
            "stage18_runtime_evidence_requirement_not_supported",
        ),
        ({"proof_kind": "wrong"}, "stage18_runtime_evidence_proof_kind_mismatch"),
        ({"dry_run": 1}, "stage18_runtime_evidence_dry_run_invalid"),
        ({"confirm_runtime_evidence": 1}, "stage18_runtime_evidence_confirmation_invalid"),
        ({"unexpected": "field"}, "stage18_runtime_evidence_payload_schema_invalid"),
    ],
)
def test_payload_and_requirement_contracts_fail_closed(
    isolated_data: Path,
    change: dict[str, object],
    error: str,
) -> None:
    payload = _payload()
    payload.update(change)

    result = runtime_evidence.plan_runtime_evidence(
        payload,
        actor="stage18.test-writer",
        stage17_closed=True,
        source_verifier=_fixture_source,
    )

    assert result["ok"] is False
    assert error in result["blockers"]
    assert not isolated_data.exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("trace_id", "../../tenant/private.json"),
        ("source_receipt_id", "C:\\secrets\\credential.txt"),
        ("trace_id", "trace\nsecret"),
        ("request_actor", "stage18 writer"),
        ("record_fingerprint", 1),
        ("trace_id", "password:SuperSecret123"),
        ("source_receipt_id", "token:abcdef123456"),
    ],
)
def test_persisted_identifiers_reject_paths_control_text_and_wrong_types(
    isolated_data: Path,
    field: str,
    value: object,
) -> None:
    payload = _payload()
    payload[field] = value

    result = runtime_evidence.plan_runtime_evidence(
        payload,
        actor="stage18.test-writer",
        stage17_closed=True,
        source_verifier=_fixture_source,
    )

    assert result["ok"] is False
    assert not isolated_data.exists()


def test_stage17_prerequisite_failure_creates_no_receipt(isolated_data: Path) -> None:
    result = runtime_evidence.record_runtime_evidence(
        _payload(),
        actor="stage18.test-writer",
        stage17_closed=False,
        source_verifier=_fixture_source,
    )

    assert result["ok"] is False
    assert result["error"] == "stage17_prerequisite_not_closed"
    assert not isolated_data.exists()


def test_fixture_lineage_records_one_immutable_software_only_receipt(isolated_data: Path) -> None:
    result = runtime_evidence.record_runtime_evidence(
        _record_payload(),
        actor="stage18.test-writer",
        stage17_closed=True,
        source_verifier=_fixture_source,
    )

    assert result["ok"] is True
    assert result["status"] == "recorded"
    assert result["writes_receipt"] is True
    assert result["receipt_ready"] is False
    receipts = runtime_evidence.load_runtime_evidence_receipts()
    assert receipts == [result["receipt"]]
    receipt = receipts[0]
    assert receipt["evidence_class"] == "fixture_software_only"
    assert runtime_evidence.receipt_satisfies_runtime_requirement(receipt) is False
    serialized = json.dumps(receipt)
    assert "evidence_summary" not in serialized
    assert "password" not in serialized
    assert not (isolated_data / "managed_copies" / "tenants").exists()
    assert [path.relative_to(isolated_data).as_posix() for path in isolated_data.rglob("*") if path.is_file()] == [
        f"logs/managed_copies/runtime_evidence/{receipt['receipt_id']}.json"
    ]


def test_copy_creation_source_dispatch_preserves_live_and_startup_verifiers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from francis import managed_copy_container_live_evidence as live_evidence
    from francis import managed_copy_pilot_runtime as pilot_runtime

    calls: list[str] = []
    monkeypatch.setattr(
        live_evidence,
        "verify_server_resolved_lifecycle_source",
        lambda receipt_id, fingerprint: (
            calls.append("lifecycle") or {"receipt_id": receipt_id, "fingerprint": fingerprint}
        ),
    )
    monkeypatch.setattr(
        pilot_runtime,
        "verify_pilot_runtime_source",
        lambda receipt_id, fingerprint: (
            calls.append("startup") or {"receipt_id": receipt_id, "fingerprint": fingerprint}
        ),
    )

    live = runtime_evidence.verify_copy_creation_runtime_source("mclc_" + "a" * 24, "b" * 64)
    startup = runtime_evidence.verify_copy_creation_runtime_source("mcpr_startup_1", "c" * 64)

    assert live["receipt_id"].startswith("mclc_")
    assert startup["receipt_id"] == "mcpr_startup_1"
    assert calls == ["lifecycle", "startup"]


@pytest.mark.parametrize(
    ("reason", "invoke_operation"),
    [
        ("pilot_lease_revocation_pending", False),
        ("pilot_lease_expired", False),
        ("pilot_lease_registry_replaced_during_transaction", True),
    ],
)
def test_runtime_evidence_lease_transaction_fails_closed_and_rolls_back(
    monkeypatch: pytest.MonkeyPatch,
    isolated_data: Path,
    reason: str,
    invoke_operation: bool,
) -> None:
    from francis import managed_copy_pilot_runtime as pilot_runtime

    payload = _record_payload()
    authority = {
        "valid": True,
        "actor_id": "stage18.test-writer",
        "lease_id": "lease-runtime-evidence-1",
        "operation_consumed_binding_count": 2,
        "sequence_prefix_fingerprints": ["a" * 64, "b" * 64],
    }

    def transaction(lease_id: str, **kwargs: Any) -> tuple[bool, str, dict[str, Any]]:
        assert lease_id == authority["lease_id"]
        result = kwargs["operation"](authority) if invoke_operation else {}
        return False, reason, result

    monkeypatch.setattr(pilot_runtime, "execute_pilot_runtime_lease_authority_transaction", transaction)
    result = runtime_evidence.record_runtime_evidence_with_lease_transaction(
        payload,
        actor=authority["actor_id"],
        stage17_closed=True,
        lease_id=authority["lease_id"],
        expected_bindings=(object(), object()),
        expected_authority=authority,
        source_verifier_factory=lambda locked: _fixture_source,
    )

    assert result["ok"] is False
    assert reason in result["error"]
    assert list(runtime_evidence.receipt_directory().glob("*.json")) == []


def test_exact_replay_is_idempotent(isolated_data: Path) -> None:
    payload = _record_payload()
    first = runtime_evidence.record_runtime_evidence(
        payload,
        actor="stage18.test-writer",
        stage17_closed=True,
        source_verifier=_fixture_source,
    )
    second = runtime_evidence.record_runtime_evidence(
        payload,
        actor="stage18.test-writer",
        stage17_closed=True,
        source_verifier=_fixture_source,
    )

    assert first["status"] == "recorded"
    assert second["status"] == "already_recorded"
    assert second["writes_receipt"] is False
    assert len(list(runtime_evidence.receipt_directory().glob("*.json"))) == 1


def test_conflicting_replay_fails_closed(isolated_data: Path) -> None:
    payload = _record_payload()
    first = runtime_evidence.record_runtime_evidence(
        payload,
        actor="stage18.test-writer",
        stage17_closed=True,
        source_verifier=_fixture_source,
    )
    path = runtime_evidence.receipt_directory() / f"{first['receipt_id']}.json"
    stored = json.loads(path.read_text(encoding="utf-8"))
    stored["actor"] = "conflicting.actor"
    path.write_text(json.dumps(stored), encoding="utf-8")

    result = runtime_evidence.record_runtime_evidence(
        payload,
        actor="stage18.test-writer",
        stage17_closed=True,
        source_verifier=_fixture_source,
    )

    assert result["ok"] is False
    assert result["error"] == "stage18_runtime_evidence_conflicting_replay"


def test_final_in_lock_revalidation_prevents_stale_write(isolated_data: Path) -> None:
    calls = 0

    def changing_source(_: str, __: str) -> dict[str, object]:
        nonlocal calls
        calls += 1
        source = _fixture_source("", "")
        if calls > 1:
            source["current_state_hash"] = _hash("changed-state")
        return source

    payload = _payload()
    initial = runtime_evidence.plan_runtime_evidence(
        payload,
        actor="stage18.test-writer",
        stage17_closed=True,
        source_verifier=_fixture_source,
    )
    payload.update(
        dry_run=False,
        record_fingerprint=initial["record_fingerprint"],
        confirm_runtime_evidence=True,
    )
    calls = 0

    result = runtime_evidence.record_runtime_evidence(
        payload,
        actor="stage18.test-writer",
        stage17_closed=True,
        source_verifier=changing_source,
    )

    assert result["ok"] is False
    assert result["error"] == "stage18_runtime_evidence_source_changed_under_lock"
    assert list(runtime_evidence.receipt_directory().glob("*.json")) == []


def test_existing_cross_process_lock_fails_closed_without_receipt(isolated_data: Path) -> None:
    payload = _record_payload()
    runtime_evidence.receipt_directory().mkdir(parents=True)
    (runtime_evidence.receipt_directory() / ".write.lock").write_text("occupied\n", encoding="utf-8")

    result = runtime_evidence.record_runtime_evidence(
        payload,
        actor="stage18.test-writer",
        stage17_closed=True,
        source_verifier=_fixture_source,
    )

    assert result["ok"] is False
    assert result["error"] == "stage18_runtime_evidence_write_lock_unavailable"
    assert list(runtime_evidence.receipt_directory().glob("*.json")) == []


@pytest.mark.parametrize(
    ("tamper_path", "value"),
    [
        (("governance", "marks_stage_closed"), True),
        (("recorded_at_unix_ms",), True),
        (("source_receipt_fingerprint",), "0" * 64),
        (("source_lineage_hash",), "0" * 64),
        (("record_fingerprint",), "0" * 64),
        (("trace_id",), "changed-trace"),
        (("unexpected",), "injected"),
    ],
)
def test_tampered_stored_receipt_is_excluded_from_readback(
    isolated_data: Path,
    tamper_path: tuple[str, ...],
    value: object,
) -> None:
    result = runtime_evidence.record_runtime_evidence(
        _record_payload(),
        actor="stage18.test-writer",
        stage17_closed=True,
        source_verifier=_fixture_source,
    )
    receipt_path = runtime_evidence.receipt_directory() / f"{result['receipt_id']}.json"
    stored = json.loads(receipt_path.read_text(encoding="utf-8"))
    target = stored
    for key in tamper_path[:-1]:
        target = target[key]
    target[tamper_path[-1]] = value
    receipt_path.write_text(json.dumps(stored), encoding="utf-8")

    assert runtime_evidence.load_runtime_evidence_receipts() == []
